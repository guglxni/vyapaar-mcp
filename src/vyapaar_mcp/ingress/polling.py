"""API Polling Ingress — replaces webhook-based ingress entirely.

Instead of waiting for Razorpay to push webhook events,
this module actively polls the Razorpay Payouts API
(via RazorpayBridge) for new payouts in 'queued' status.

Why this approach?
  1. No public endpoint needed (no ngrok / tunnel / cloudflared)
  2. Works behind NAT / firewalls / 2FA-restricted environments
  3. Razorpay API allows 600 req/min on free tier
  4. 30s polling = ~2880 calls/day (well within limits)
  5. Uses same idempotency layer as webhooks (Redis)
  6. Zero signature verification issues

Architecture:
  PayoutPoller → RazorpayBridge → razorpay SDK → Razorpay API
                                                    ↓
  Governance Engine ← PayoutEntity ← poll_once()
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from vyapaar_mcp.db.redis_client import RedisClient
from vyapaar_mcp.ingress.razorpay_bridge import RazorpayBridge
from vyapaar_mcp.models import PayoutEntity

logger = logging.getLogger(__name__)

# Polling constants
DEFAULT_POLL_INTERVAL = 30  # seconds
MIN_POLL_INTERVAL = 5
MAX_POLL_INTERVAL = 300
MAX_PAYOUTS_PER_PAGE = 100
ERROR_BACKOFF_BASE = 5.0
ERROR_BACKOFF_MAX = 120.0


class PayoutPoller:
    """Polls Razorpay API for new queued payouts.

    Replaces webhook-based ingress completely. Uses the
    RazorpayBridge (wrapping the official razorpay SDK with the
    same tool interfaces as razorpay/razorpay-mcp-server) and
    the same Redis idempotency layer to prevent duplicate processing.
    """

    def __init__(
        self,
        bridge: RazorpayBridge,
        account_number: str,
        redis: RedisClient,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
    ) -> None:
        self._bridge = bridge
        self._account_number = account_number
        self._redis = redis
        self._poll_interval = max(
            MIN_POLL_INTERVAL, min(poll_interval, MAX_POLL_INTERVAL)
        )
        self._running = False
        self._error_count = 0
        self._total_processed = 0
        self._last_poll_at: float | None = None

        # Mask account number in logs
        masked = account_number[-4:].rjust(
            len(account_number), "*"
        )
        logger.info(
            "PayoutPoller initialized (interval=%ds, account=%s)",
            self._poll_interval,
            masked,
        )

    async def fetch_queued_payouts(
        self,
        count: int = MAX_PAYOUTS_PER_PAGE,
        skip: int = 0,
    ) -> list[dict[str, Any]]:
        """Fetch payouts with status=queued from Razorpay API.

        Uses RazorpayBridge.fetch_all_payouts which maps to:
          GET /v1/payouts?account_number={acct}&status=queued

        Returns:
            List of raw payout dicts from the API response.
        """
        data = await self._bridge.fetch_all_payouts(
            account_number=self._account_number,
            count=count,
            skip=skip,
            status="queued",
        )
        items: list[dict[str, Any]] = data.get("items", [])

        logger.debug(
            "Fetched %d queued payouts (skip=%d, total_count=%d)",
            len(items),
            skip,
            data.get("count", 0),
        )
        return items

    async def fetch_all_queued_payouts(self) -> list[dict[str, Any]]:
        """Fetch ALL queued payouts with automatic pagination.

        Iterates through pages until no more results.

        Returns:
            Complete list of queued payouts.
        """
        all_payouts: list[dict[str, Any]] = []
        skip = 0

        while True:
            batch = await self.fetch_queued_payouts(
                count=MAX_PAYOUTS_PER_PAGE, skip=skip
            )
            if not batch:
                break
            all_payouts.extend(batch)
            if len(batch) < MAX_PAYOUTS_PER_PAGE:
                break  # Last page
            skip += MAX_PAYOUTS_PER_PAGE

        return all_payouts

    def convert_to_payout_entity(
        self, raw_payout: dict[str, Any]
    ) -> PayoutEntity:
        """Convert a raw Razorpay API payout response to PayoutEntity.

        The API response format matches what the Go MCP server's
        fetch_all_payouts returns. We normalize into our Pydantic model.
        """
        return PayoutEntity(
            id=raw_payout["id"],
            entity=raw_payout.get("entity", "payout"),
            fund_account_id=raw_payout.get("fund_account_id"),
            amount=raw_payout["amount"],
            currency=raw_payout.get("currency", "INR"),
            notes=raw_payout.get("notes", {}),
            fees=raw_payout.get("fees"),
            tax=raw_payout.get("tax"),
            status=raw_payout["status"],
            purpose=raw_payout.get("purpose"),
            mode=raw_payout.get("mode"),
            reference_id=raw_payout.get("reference_id"),
            created_at=raw_payout.get("created_at"),
        )

    async def poll_once(
        self,
    ) -> list[tuple[PayoutEntity, str, str | None]]:
        """Execute a single poll cycle.

        Steps:
        1. Fetch all queued payouts via RazorpayBridge
        2. Deduplicate against Redis (same as webhook idempotency)
        3. Convert new payouts to PayoutEntity
        4. Return list of (payout, agent_id, vendor_url) tuples

        Returns:
            List of new (not-yet-processed) payout tuples.
        """
        self._last_poll_at = time.time()

        # Step 1: Fetch via bridge
        try:
            raw_payouts = await self.fetch_all_queued_payouts()
            self._error_count = 0  # Reset on success
        except Exception as e:
            self._error_count += 1
            logger.error(
                "Razorpay API poll error (attempt %d): %s",
                self._error_count,
                e,
            )
            return []

        if not raw_payouts:
            logger.debug("No queued payouts found")
            return []

        # Step 2 & 3: Deduplicate + Convert
        new_payouts: list[tuple[PayoutEntity, str, str | None]] = []

        for raw in raw_payouts:
            payout_id = raw.get("id", "")
            idempotency_key = f"poll:payout.queued:{payout_id}"

            # Check if already processed (same Redis layer as webhooks)
            is_new = await self._redis.check_idempotency(
                idempotency_key
            )
            if not is_new:
                logger.debug(
                    "Skipping already-processed payout: %s",
                    payout_id,
                )
                continue

            # Convert
            payout = self.convert_to_payout_entity(raw)

            # Extract agent_id and vendor_url from notes
            notes = raw.get("notes", {})
            agent_id = notes.get("agent_id", "unknown")
            vendor_url = notes.get("vendor_url") or None

            new_payouts.append((payout, agent_id, vendor_url))
            self._total_processed += 1

        if new_payouts:
            logger.info(
                "🔍 Poll found %d NEW payouts (of %d total queued)",
                len(new_payouts),
                len(raw_payouts),
            )

        return new_payouts

    async def run_continuous(
        self,
        on_payout: Any = None,
    ) -> None:
        """Run the poller in a continuous loop.

        Args:
            on_payout: Async callback for each new payout tuple.
                       Signature: async def(payout, agent_id, vendor_url)
        """
        self._running = True
        logger.info(
            "🔄 PayoutPoller starting continuous poll "
            "(interval=%ds)",
            self._poll_interval,
        )

        while self._running:
            try:
                new_payouts = await self.poll_once()

                if on_payout and new_payouts:
                    for payout, agent_id, vendor_url in new_payouts:
                        try:
                            await on_payout(
                                payout, agent_id, vendor_url
                            )
                        except Exception as e:
                            logger.error(
                                "Payout callback error for %s: %s",
                                payout.id,
                                e,
                            )

            except Exception as e:
                logger.error("Poll loop error: %s", e)

            # Wait with backoff
            interval = self.get_backoff_interval()
            await asyncio.sleep(interval)

    def stop(self) -> None:
        """Signal the continuous poller to stop."""
        self._running = False
        logger.info(
            "PayoutPoller stopped (total processed: %d)",
            self._total_processed,
        )

    def get_backoff_interval(self) -> float:
        """Calculate poll interval with exponential backoff on errors."""
        if self._error_count == 0:
            return float(self._poll_interval)

        backoff = min(
            ERROR_BACKOFF_BASE * (2 ** (self._error_count - 1)),
            ERROR_BACKOFF_MAX,
        )
        return backoff

    @property
    def stats(self) -> dict[str, Any]:
        """Return poller statistics."""
        return {
            "running": self._running,
            "poll_interval_seconds": self._poll_interval,
            "error_count": self._error_count,
            "total_processed": self._total_processed,
            "last_poll_at": self._last_poll_at,
            "current_backoff": self.get_backoff_interval(),
        }
