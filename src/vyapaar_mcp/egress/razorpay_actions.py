"""Razorpay X payout actions — approve/reject/cancel payouts.

Uses the Razorpay Python SDK for authenticated API calls.
Implements retry with exponential backoff for 5xx errors.
"""

from __future__ import annotations

import asyncio
import base64
import logging

import httpx
import razorpay

from vyapaar_mcp.resilience import CircuitBreaker

logger = logging.getLogger(__name__)

# Retry configuration per SPEC §14.3
MAX_RETRIES = 3
BASE_DELAY = 1.0
MAX_DELAY = 30.0
BACKOFF_MULTIPLIER = 2.0


class RazorpayActions:
    """Razorpay X payout approve/reject actions."""

    def __init__(
        self,
        key_id: str,
        key_secret: str,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        self._client = razorpay.Client(auth=(key_id, key_secret))
        self._key_id = key_id
        self._key_secret = key_secret
        self._circuit = circuit_breaker or CircuitBreaker(
            "razorpay", failure_threshold=5, recovery_timeout=30.0
        )
        logger.info("Razorpay client initialized")

    async def _retry_with_backoff(
        self,
        operation: str,
        func: object,
        *args: object,
    ) -> dict[str, object]:
        """Execute a Razorpay API call with exponential backoff retry.

        Retries on 5xx errors. Does NOT retry on 4xx (client errors).
        """
        last_error: Exception | None = None
        delay = BASE_DELAY

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # Razorpay SDK is synchronous — run in thread pool
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(None, func, *args)  # type: ignore[arg-type]
                logger.info(
                    "%s succeeded on attempt %d for args: %s",
                    operation, attempt, args,
                )
                return result  # type: ignore[return-value]

            except razorpay.errors.ServerError as e:
                last_error = e
                logger.warning(
                    "%s failed (attempt %d/%d): %s — retrying in %.1fs",
                    operation, attempt, MAX_RETRIES, e, delay,
                )
                await asyncio.sleep(delay)
                delay = min(delay * BACKOFF_MULTIPLIER, MAX_DELAY)

            except razorpay.errors.BadRequestError as e:
                # 4xx — don't retry
                logger.error("%s failed with client error: %s", operation, e)
                raise

            except Exception as e:
                last_error = e
                logger.error("%s unexpected error: %s", operation, e)
                if attempt == MAX_RETRIES:
                    raise
                await asyncio.sleep(delay)
                delay = min(delay * BACKOFF_MULTIPLIER, MAX_DELAY)

        raise RuntimeError(
            f"{operation} failed after {MAX_RETRIES} attempts: {last_error}"
        )

    async def approve_payout(self, payout_id: str) -> dict[str, object]:
        """Approve a queued payout on Razorpay X.

        Calls: POST /v1/payouts/{payout_id}/approve
        Protected by circuit breaker.
        """
        logger.info("Approving payout: %s", payout_id)
        return await self._circuit.call(
            self._retry_with_backoff,
            "approve_payout",
            self._approve_payout_sync,
            payout_id,
        )

    def _approve_payout_sync(self, payout_id: str) -> dict[str, object]:
        """Synchronous Razorpay approve call (run in thread pool)."""
        auth_str = base64.b64encode(
            f"{self._key_id}:{self._key_secret}".encode()
        ).decode()
        resp = httpx.post(
            f"https://api.razorpay.com/v1/payouts/{payout_id}/approve",
            headers={
                "Authorization": f"Basic {auth_str}",
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore[return-value]

    async def reject_payout(self, payout_id: str, reason: str) -> dict[str, object]:
        """Cancel/reject a queued payout on Razorpay X.

        Calls: PATCH /v1/payouts/{payout_id}/cancel
        Protected by circuit breaker.
        """
        logger.info("Rejecting payout: %s — reason: %s", payout_id, reason)
        return await self._circuit.call(
            self._retry_with_backoff,
            "reject_payout",
            self._approve_or_cancel,
            payout_id,
            reason,
        )

    def _approve_or_cancel(self, payout_id: str, reason: str = "") -> dict[str, object]:
        """Synchronous Razorpay cancel call (run in thread pool)."""
        try:
            # Try SDK cancel method
            result: dict[str, object] = self._client.payout.cancel(  # type: ignore[attr-defined]
                payout_id,
                {"remarks": f"REJECTED by Vyapaar MCP: {reason}"},
            )
            return result
        except AttributeError:
            # Fallback: use general HTTP
            auth_str = base64.b64encode(
                f"{self._key_id}:{self._key_secret}".encode()
            ).decode()
            resp = httpx.patch(
                f"https://api.razorpay.com/v1/payouts/{payout_id}/cancel",
                headers={
                    "Authorization": f"Basic {auth_str}",
                    "Content-Type": "application/json",
                },
                json={"remarks": f"REJECTED by Vyapaar MCP: {reason}"},
            )
            resp.raise_for_status()
            return resp.json()  # type: ignore[return-value]

    async def ping(self) -> bool:
        """Check if Razorpay API is reachable."""
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                self._client.payment.all,  # type: ignore[attr-defined]
                {"count": 1},
            )
            return True
        except Exception:
            return False
