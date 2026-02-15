"""Vyapaar MCP Server — FastMCP entrypoint with SSE transport.

Registers all governance tools and manages the lifecycle of
Redis, PostgreSQL, and external API clients.

Deployment: Designed for Archestra platform with SSE transport,
Vault-backed secrets, and Prometheus observability.
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from vyapaar_mcp.audit.logger import log_decision
from vyapaar_mcp.config import VyapaarConfig, load_config
from vyapaar_mcp.db.postgres import PostgresClient
from vyapaar_mcp.db.redis_client import RedisClient
from vyapaar_mcp.egress.ntfy_notifier import NtfyNotifier, notify_with_fallback
from vyapaar_mcp.egress.razorpay_actions import RazorpayActions
from vyapaar_mcp.egress.slack_notifier import SlackNotifier
from vyapaar_mcp.governance.engine import GovernanceEngine
from vyapaar_mcp.reputation.anomaly import TransactionAnomalyScorer
from vyapaar_mcp.reputation.gleif import GLEIFChecker
from vyapaar_mcp.ingress.polling import PayoutPoller
from vyapaar_mcp.ingress.razorpay_bridge import RazorpayBridge
from vyapaar_mcp.ingress.webhook import (
    extract_webhook_id,
    parse_webhook_event,
    verify_razorpay_signature,
)
from vyapaar_mcp.models import (
    AgentPolicy,
    BudgetStatus,
    Decision,
    HealthStatus,
    ReasonCode,
)
from vyapaar_mcp.llm import AzureOpenAIClient, SecurityLLMClient
from vyapaar_mcp.llm.security_validator import ToolCallValidator
from vyapaar_mcp.observability import metrics
from vyapaar_mcp.reputation.safe_browsing import SafeBrowsingChecker
from vyapaar_mcp.resilience import CircuitBreaker, CircuitOpenError

# ================================================================
# Logging Setup
# ================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("vyapaar_mcp")

# ================================================================
# Global State (initialized in lifespan)
# ================================================================

_config: VyapaarConfig | None = None
_redis: RedisClient | None = None
_postgres: PostgresClient | None = None
_safe_browsing: SafeBrowsingChecker | None = None
_razorpay: RazorpayActions | None = None
_razorpay_bridge: RazorpayBridge | None = None
_slack: SlackNotifier | None = None
_poller: PayoutPoller | None = None
_governance: GovernanceEngine | None = None
_poll_task: asyncio.Task[None] | None = None
_start_time: float = time.time()
_cb_razorpay: CircuitBreaker | None = None
_cb_safe_browsing: CircuitBreaker | None = None
_cb_gleif: CircuitBreaker | None = None
_gleif: GLEIFChecker | None = None
_anomaly_scorer: TransactionAnomalyScorer | None = None
_ntfy: NtfyNotifier | None = None
_azure_llm: AzureOpenAIClient | None = None
_security_llm: SecurityLLMClient | None = None
_tool_validator: ToolCallValidator | None = None


def _require(**services: Any) -> None:
    """Validate that required server components are initialized.

    Raises RuntimeError instead of using assert (which is stripped
    with ``python -O``).
    """
    missing = [name for name, obj in services.items() if obj is None]
    if missing:
        raise RuntimeError(
            f"Server not initialised — missing: {', '.join(missing)}. "
            "Ensure startup() completed successfully."
        )


# ================================================================
# FastMCP Server
# ================================================================


@asynccontextmanager
async def _lifespan(server: FastMCP):
    """FastMCP lifespan context manager — runs startup/shutdown."""
    await _startup()
    try:
        yield
    finally:
        await _shutdown()


mcp = FastMCP(
    "vyapaar-mcp",
    instructions=(
        "Agentic Financial Governance Server — "
        "The CFO for the Agentic Economy. "
        "Enforces spending policies, checks vendor reputation, "
        "and audits every AI agent transaction via Razorpay X."
    ),
    lifespan=_lifespan,
    sse_path="/sse",
    message_path="/messages/",
)


@mcp.custom_route("/health", methods=["GET"])
async def health_endpoint(request: Request) -> JSONResponse:
    """HTTP Health Check for Archestra/Load Balancers."""
    return JSONResponse({"status": "ok", "service": "vyapaar-mcp"})


# ================================================================
# Lifecycle
# ================================================================


async def _startup() -> None:
    """Initialize all services on server start."""
    global _config, _redis, _postgres, _safe_browsing, \
        _razorpay, _razorpay_bridge, _slack, _poller, \
        _governance, _poll_task, _start_time, \
        _cb_razorpay, _cb_safe_browsing, _cb_gleif, \
        _gleif, _anomaly_scorer, _ntfy, \
        _azure_llm, _security_llm, _tool_validator

    _start_time = time.time()
    _config = load_config()

    logger.info("=" * 60)
    logger.info("  VYAPAAR MCP — Starting up...")
    logger.info("=" * 60)

    # Redis
    _redis = RedisClient(url=_config.redis_url)
    try:
        await _redis.connect()
        logger.info("✅ Redis connected")
    except Exception as e:
        logger.error("❌ Redis connection failed: %s", e)

    # PostgreSQL
    _postgres = PostgresClient(dsn=_config.postgres_dsn)
    try:
        await _postgres.connect()
        await _postgres.run_migrations()
        logger.info("✅ PostgreSQL connected + migrations complete")
    except Exception as e:
        logger.error("❌ PostgreSQL connection failed: %s", e)

    # Google Safe Browsing
    _cb_safe_browsing = CircuitBreaker(
        "safe-browsing",
        failure_threshold=_config.circuit_breaker_failure_threshold,
        recovery_timeout=float(_config.circuit_breaker_recovery_timeout),
    )
    _safe_browsing = SafeBrowsingChecker(
        api_key=_config.google_safe_browsing_key,
        api_url=_config.safe_browsing_api_url,
        redis=_redis,
        circuit_breaker=_cb_safe_browsing,
    )
    logger.info("✅ Safe Browsing checker initialized (circuit breaker enabled)")

    # Razorpay Actions (egress — approve/reject)
    _cb_razorpay = CircuitBreaker(
        "razorpay",
        failure_threshold=_config.circuit_breaker_failure_threshold,
        recovery_timeout=float(_config.circuit_breaker_recovery_timeout),
    )
    _razorpay = RazorpayActions(
        key_id=_config.razorpay_key_id,
        key_secret=_config.razorpay_key_secret,
        circuit_breaker=_cb_razorpay,
    )
    logger.info("✅ Razorpay egress client initialized (circuit breaker enabled)")

    # Razorpay Bridge (ingress — API calls, same as official MCP server)
    _razorpay_bridge = RazorpayBridge(
        key_id=_config.razorpay_key_id,
        key_secret=_config.razorpay_key_secret,
    )
    logger.info(
        "✅ RazorpayBridge initialized "
        "(mirrors razorpay/razorpay-mcp-server tools)"
    )

    # Slack Notifier (human-in-the-loop)
    if _config.slack_bot_token and _config.slack_channel_id:
        _slack = SlackNotifier(
            bot_token=_config.slack_bot_token,
            channel_id=_config.slack_channel_id,
        )
        logger.info("✅ Slack notifier initialized (channel=%s)", _config.slack_channel_id)
    else:
        logger.warning(
            "⚠️  Slack not configured — HELD payouts will not trigger approval requests. "
            "Set VYAPAAR_SLACK_BOT_TOKEN and VYAPAAR_SLACK_CHANNEL_ID in .env"
        )

    # Payout Poller (replaces webhooks)
    if _config.razorpay_account_number:
        _poller = PayoutPoller(
            bridge=_razorpay_bridge,
            account_number=_config.razorpay_account_number,
            redis=_redis,
            poll_interval=_config.poll_interval,
        )
        logger.info(
            "✅ PayoutPoller ready "
            "(interval=%ds, replaces webhook ingress)",
            _config.poll_interval,
        )
    else:
        logger.warning(
            "⚠️  VYAPAAR_RAZORPAY_ACCOUNT_NUMBER not set — "
            "automatic polling disabled. "
            "Use poll_razorpay_payouts tool manually."
        )

    # Governance Engine
    _governance = GovernanceEngine(
        redis=_redis,
        postgres=_postgres,
        safe_browsing=_safe_browsing,
        rate_limit_max=_config.rate_limit_max_requests,
        rate_limit_window=_config.rate_limit_window_seconds,
    )
    logger.info(
        "✅ Governance engine ready "
        "(rate limit: %d req / %ds window)",
        _config.rate_limit_max_requests,
        _config.rate_limit_window_seconds,
    )

    # GLEIF Vendor Verification (FOSS)
    _cb_gleif = CircuitBreaker(
        "gleif",
        failure_threshold=_config.circuit_breaker_failure_threshold,
        recovery_timeout=float(_config.circuit_breaker_recovery_timeout),
    )
    _gleif = GLEIFChecker(
        api_url=_config.gleif_api_url,
        redis=_redis,
        circuit_breaker=_cb_gleif,
    )
    logger.info("✅ GLEIF vendor verification initialized (circuit breaker enabled)")

    # Transaction Anomaly Scorer (FOSS — scikit-learn IsolationForest)
    _anomaly_scorer = TransactionAnomalyScorer(
        redis=_redis,
        risk_threshold=_config.anomaly_risk_threshold,
    )
    logger.info(
        "✅ Transaction anomaly scorer initialized "
        "(threshold=%.2f)",
        _config.anomaly_risk_threshold,
    )

    # ntfy Notifier (FOSS — Slack fallback)
    if _config.ntfy_topic:
        _ntfy = NtfyNotifier(
            topic=_config.ntfy_topic,
            server_url=_config.ntfy_url,
            auth_token=_config.ntfy_auth_token or None,
        )
        logger.info(
            "✅ ntfy notifier initialized (topic=%s, server=%s)",
            _config.ntfy_topic,
            _config.ntfy_url,
        )
    else:
        logger.info(
            "ℹ️  ntfy not configured — set VYAPAAR_NTFY_TOPIC to enable push fallback"
        )

    # Azure OpenAI Client (Microsoft AI Foundry)
    _azure_llm = AzureOpenAIClient(_config)
    try:
        await _azure_llm.initialize()
        if _azure_llm.is_configured:
            logger.info(
                "✅ Azure OpenAI initialized (deployment=%s, guardrails=%s)",
                _config.azure_openai_deployment,
                _config.azure_guardrails_enabled,
            )
        else:
            logger.info(
                "ℹ️  Azure OpenAI not configured — "
                "set VYAPAAR_AZURE_OPENAI_ENDPOINT and VYAPAAR_AZURE_OPENAI_API_KEY"
            )
    except Exception as e:
        logger.warning("⚠️  Azure OpenAI initialization skipped: %s", e)

    # Security LLM / Dual LLM Quarantine Pattern
    _tool_validator = ToolCallValidator(_config)
    try:
        await _tool_validator.initialize()
        if _tool_validator.is_configured:
            logger.info(
                "✅ Dual LLM quarantine initialized (security_llm=%s, strict=%s)",
                _config.security_llm_url,
                _config.quarantine_strict,
            )
            logger.info(
                "   Taint sources: %s",
                _config.taint_sources.replace(",", ", ")
            )
            logger.info(
                "   Dual-LLM tools: %s",
                _config.dual_llm_tools.replace(",", ", ")
            )
        else:
            logger.info(
                "ℹ️  Dual LLM quarantine not configured — "
                "set VYAPAAR_SECURITY_LLM_URL to enable"
            )
    except Exception as e:
        logger.warning("⚠️  Dual LLM quarantine initialization skipped: %s", e)

    # Auto-polling (background task)
    if _config.auto_poll and _poller and _governance and _razorpay and _postgres:
        async def _auto_poll_callback(
            payout: Any, agent_id: str, vendor_url: str | None
        ) -> None:
            """Process a polled payout through governance."""
            _require(governance=_governance, razorpay=_razorpay, postgres=_postgres)

            result = await _governance.evaluate(payout, agent_id, vendor_url)
            metrics.record_decision(result)

            vendor_name: str | None = None
            if hasattr(payout, 'fund_account') and payout.fund_account and payout.fund_account.contact:
                vendor_name = payout.fund_account.contact.name

            await log_decision(_postgres, result, vendor_name=vendor_name, vendor_url=vendor_url)

            try:
                if result.decision == Decision.APPROVED:
                    await _razorpay.approve_payout(payout.id)
                elif result.decision == Decision.REJECTED:
                    await _razorpay.reject_payout(
                        payout.id,
                        f"{result.reason_code.value}: {result.reason_detail}",
                    )
            except Exception as e:
                logger.error("Auto-poll action failed for %s: %s", payout.id, e)
                if result.decision == Decision.APPROVED and _redis:
                    await _redis.rollback_budget(result.agent_id, result.amount)
                    logger.warning("Budget rolled back for %s: %d paise", result.agent_id, result.amount)

            await notify_with_fallback(_slack, _ntfy, result, vendor_name=vendor_name, vendor_url=vendor_url)

        _poll_task = asyncio.create_task(
            _poller.run_continuous(on_payout=_auto_poll_callback)
        )
        logger.info(
            "🔄 Auto-polling ENABLED (interval=%ds)",
            _config.poll_interval,
        )

    logger.info("=" * 60)
    logger.info("  VYAPAAR MCP — Ready to govern! 🛡️")
    logger.info("  Mode: API Polling (no webhook/tunnel needed)")
    logger.info("  Sidecar: razorpay/mcp (all toolsets enabled)")
    logger.info("=" * 60)


async def _shutdown() -> None:
    """Cleanup on server shutdown."""
    logger.info("Vyapaar MCP shutting down...")
    if _poll_task and not _poll_task.done():
        _poll_task.cancel()
    if _poller:
        _poller.stop()
    if _slack:
        await _slack.close()
    if _ntfy:
        await _ntfy.close()
    if _gleif:
        await _gleif.close()
    if _safe_browsing:
        await _safe_browsing.close()
    if _azure_llm:
        await _azure_llm.close()
    if _tool_validator:
        await _tool_validator.close()
    if _redis:
        await _redis.disconnect()
    if _postgres:
        await _postgres.disconnect()
    logger.info("Vyapaar MCP shutdown complete")


# ================================================================
# MCP Tools
# ================================================================


@mcp.tool()
async def handle_razorpay_webhook(
    payload: str,
    signature: str,
) -> dict[str, Any]:
    """Receive and process a Razorpay X webhook event (payout.queued).

    This is the main ingress point. It verifies the webhook signature,
    checks idempotency, runs the governance pipeline, and either
    approves or rejects the payout on Razorpay.

    Args:
        payload: Raw JSON body of the Razorpay webhook.
        signature: Value of the X-Razorpay-Signature header.

    Returns:
        Decision result with payout_id, decision, and reason.
    """
    _require(config=_config, redis=_redis, postgres=_postgres, governance=_governance, razorpay=_razorpay)

    payload_bytes = payload.encode("utf-8")

    # --- Step 1: Verify Signature ---
    if not verify_razorpay_signature(payload_bytes, signature, _config.razorpay_webhook_secret):
        logger.warning("REJECTED: Invalid webhook signature")
        return {
            "decision": Decision.REJECTED.value,
            "reason": ReasonCode.INVALID_SIGNATURE.value,
            "detail": "Webhook signature verification failed (401)",
        }

    # --- Step 2: Parse Event ---
    try:
        event = parse_webhook_event(payload_bytes)
    except ValueError as e:
        return {
            "decision": Decision.REJECTED.value,
            "reason": "PARSE_ERROR",
            "detail": str(e),
        }

    # --- Step 3: Only handle payout.queued ---
    if event.event != "payout.queued":
        return {
            "decision": "SKIPPED",
            "reason": "UNSUPPORTED_EVENT",
            "detail": f"Event '{event.event}' is not handled. Only 'payout.queued' is supported.",
        }

    # --- Step 4: Idempotency Check ---
    webhook_id = extract_webhook_id(event)
    is_new = await _redis.check_idempotency(webhook_id)
    if not is_new:
        logger.info("Idempotent skip: webhook %s already processed", webhook_id)
        return {
            "decision": "SKIPPED",
            "reason": ReasonCode.IDEMPOTENT_SKIP.value,
            "detail": f"Webhook '{webhook_id}' already processed",
        }

    # --- Step 5: Extract context ---
    payout = event.payload.payout.entity
    notes = payout.get_notes()
    agent_id = notes.agent_id
    vendor_url = notes.vendor_url or None
    vendor_name: str | None = None

    # Try to get vendor name from fund account contact
    if payout.fund_account and payout.fund_account.contact:
        vendor_name = payout.fund_account.contact.name

    # --- Step 6: Run Governance ---
    result = await _governance.evaluate(payout, agent_id, vendor_url)
    metrics.record_decision(result)

    # --- Step 7: Write Audit Log ---
    await log_decision(_postgres, result, vendor_name=vendor_name, vendor_url=vendor_url)

    # --- Step 8: Execute Decision on Razorpay ---
    try:
        if result.decision == Decision.APPROVED:
            await _razorpay.approve_payout(payout.id)
        elif result.decision == Decision.REJECTED:
            await _razorpay.reject_payout(
                payout.id,
                f"{result.reason_code.value}: {result.reason_detail}",
            )
        # HELD payouts are not auto-actioned (waiting for human approval)
    except Exception as e:
        logger.error("Razorpay action failed for %s: %s", payout.id, e)
        if result.decision == Decision.APPROVED:
            await _redis.rollback_budget(result.agent_id, result.amount)
            logger.warning("Budget rolled back for %s: %d paise", result.agent_id, result.amount)

    # --- Step 9: Notification (Slack + ntfy fallback) ---
    await notify_with_fallback(_slack, _ntfy, result, vendor_name=vendor_name, vendor_url=vendor_url)

    return {
        "payout_id": result.payout_id,
        "decision": result.decision.value,
        "reason": result.reason_code.value,
        "detail": result.reason_detail,
        "amount_paise": result.amount,
        "agent_id": result.agent_id,
        "processing_ms": result.processing_ms,
    }


@mcp.tool()
async def poll_razorpay_payouts(
    account_number: str = "",
) -> dict[str, Any]:
    """Poll Razorpay API for queued payouts and run governance.

    This replaces webhook-based ingress entirely. No tunnel, no
    ngrok, no public endpoint needed.

    Uses the same API as the official razorpay/razorpay-mcp-server's
    fetch_all_payouts tool, combined with Vyapaar's governance engine.

    Args:
        account_number: RazorpayX account number. If empty, uses
                       the configured VYAPAAR_RAZORPAY_ACCOUNT_NUMBER.

    Returns:
        Summary of payouts found and governance decisions made.
    """
    _require(config=_config, redis=_redis, razorpay_bridge=_razorpay_bridge, governance=_governance, razorpay=_razorpay, postgres=_postgres)

    acct = account_number or _config.razorpay_account_number
    if not acct:
        return {
            "error": (
                "No account number provided. Set "
                "VYAPAAR_RAZORPAY_ACCOUNT_NUMBER in .env "
                "or pass account_number parameter."
            ),
        }

    # Create a one-shot poller
    poller = PayoutPoller(
        bridge=_razorpay_bridge,
        account_number=acct,
        redis=_redis,
        poll_interval=_config.poll_interval,
    )

    # Poll once
    new_payouts = await poller.poll_once()

    if not new_payouts:
        return {
            "status": "ok",
            "message": "No new queued payouts found",
            "payouts_found": 0,
            "poller_stats": poller.stats,
        }

    # Process each payout through governance
    results: list[dict[str, Any]] = []
    for payout, agent_id, vendor_url in new_payouts:
        # Run governance
        result = await _governance.evaluate(
            payout, agent_id, vendor_url
        )
        metrics.record_decision(result)

        # Audit log
        vendor_name: str | None = None
        if (
            payout.fund_account
            and payout.fund_account.contact
        ):
            vendor_name = payout.fund_account.contact.name

        await log_decision(
            _postgres,
            result,
            vendor_name=vendor_name,
            vendor_url=vendor_url,
        )

        # Execute decision on Razorpay
        try:
            if result.decision == Decision.APPROVED:
                await _razorpay.approve_payout(payout.id)
            elif result.decision == Decision.REJECTED:
                await _razorpay.reject_payout(
                    payout.id,
                    f"{result.reason_code.value}: "
                    f"{result.reason_detail}",
                )
        except Exception as e:
            logger.error(
                "Razorpay action failed for %s: %s",
                payout.id,
                e,
            )
            if result.decision == Decision.APPROVED:
                await _redis.rollback_budget(result.agent_id, result.amount)
                logger.warning("Budget rolled back for %s: %d paise", result.agent_id, result.amount)

        # Notification (Slack + ntfy fallback)
        await notify_with_fallback(_slack, _ntfy, result, vendor_name=vendor_name, vendor_url=vendor_url)

        results.append({
            "payout_id": result.payout_id,
            "decision": result.decision.value,
            "reason": result.reason_code.value,
            "detail": result.reason_detail,
            "amount_paise": result.amount,
            "agent_id": result.agent_id,
        })

    return {
        "status": "ok",
        "payouts_found": len(new_payouts),
        "decisions": results,
        "poller_stats": poller.stats,
    }


@mcp.tool()
async def check_vendor_reputation(url: str) -> dict[str, Any]:
    """Check a URL against Google Safe Browsing v4 threat lists.

    Returns whether the URL is safe and any detected threats.

    Args:
        url: The vendor URL or domain to check.

    Returns:
        Safety result with threat details.
    """
    _require(safe_browsing=_safe_browsing)

    result = await _safe_browsing.check_url(url)
    return {
        "url": url,
        "safe": result.is_safe,
        "threats": result.threat_types,
        "match_count": len(result.matches),
    }


@mcp.tool()
async def get_agent_budget(agent_id: str) -> dict[str, Any]:
    """Get current daily spend and remaining budget for an agent.

    Args:
        agent_id: The unique identifier of the AI agent.

    Returns:
        Budget status with daily limit, spent today, and remaining.
    """
    _require(redis=_redis, postgres=_postgres)

    policy = await _postgres.get_agent_policy(agent_id)
    if policy is None:
        return {"error": f"No policy found for agent '{agent_id}'"}

    spent_today = await _redis.get_daily_spend(agent_id)
    remaining = max(0, policy.daily_limit - spent_today)

    status = BudgetStatus(
        agent_id=agent_id,
        daily_limit=policy.daily_limit,
        spent_today=spent_today,
        remaining=remaining,
    )
    return status.model_dump()


@mcp.tool()
async def get_audit_log(
    agent_id: str = "",
    payout_id: str = "",
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Retrieve spending audit trail with optional filtering.

    Args:
        agent_id: Filter by agent ID (optional).
        payout_id: Filter by payout ID (optional).
        limit: Maximum number of entries to return (default 50).

    Returns:
        List of audit log entries.
    """
    _require(postgres=_postgres)

    # Clamp limit to prevent excessive queries
    limit = max(1, min(limit, 500))

    entries = await _postgres.get_audit_logs(
        agent_id=agent_id or None,
        payout_id=payout_id or None,
        limit=limit,
    )
    return [entry.model_dump(mode="json") for entry in entries]


@mcp.tool()
async def set_agent_policy(
    agent_id: str,
    daily_limit: int = 500000,
    per_txn_limit: int | None = None,
    require_approval_above: int | None = None,
    allowed_domains: list[str] | None = None,
    blocked_domains: list[str] | None = None,
) -> dict[str, Any]:
    """Create or update spending policies for a specific agent.

    All amounts are in paise (₹500 = 50000 paise).

    Args:
        agent_id: The unique identifier of the AI agent.
        daily_limit: Maximum daily spend in paise (default ₹5,000).
        per_txn_limit: Maximum single transaction in paise (optional).
        require_approval_above: Trigger human approval above this amount (optional).
        allowed_domains: Whitelist of allowed vendor domains (optional).
        blocked_domains: Blacklist of blocked vendor domains (optional).

    Returns:
        The created/updated policy.
    """
    _require(postgres=_postgres)

    policy = AgentPolicy(
        agent_id=agent_id,
        daily_limit=daily_limit,
        per_txn_limit=per_txn_limit,
        require_approval_above=require_approval_above,
        allowed_domains=allowed_domains or [],
        blocked_domains=blocked_domains or [],
    )

    saved = await _postgres.upsert_agent_policy(policy)
    return {"status": "ok", "policy": saved.model_dump(mode="json")}


@mcp.tool()
async def health_check() -> dict[str, Any]:
    """Check health of all dependent services.

    Returns status of Redis, PostgreSQL, and Razorpay connectivity,
    plus server uptime and circuit breaker states.
    """
    redis_ok = await _redis.ping() if _redis else False
    postgres_ok = await _postgres.ping() if _postgres else False
    razorpay_ok = await _razorpay.ping() if _razorpay else False

    status = HealthStatus(
        redis="ok" if redis_ok else "error",
        postgres="ok" if postgres_ok else "error",
        razorpay="ok" if razorpay_ok else "error",
        uptime_seconds=int(time.time() - _start_time),
    )

    result = status.model_dump()
    # Include circuit breaker snapshots
    if _cb_razorpay is not None:
        result["circuit_breaker_razorpay"] = _cb_razorpay.snapshot()
    if _cb_safe_browsing is not None:
        result["circuit_breaker_safe_browsing"] = _cb_safe_browsing.snapshot()
    if _cb_gleif is not None:
        result["circuit_breaker_gleif"] = _cb_gleif.snapshot()
    return result


@mcp.tool()
async def get_metrics() -> dict[str, Any]:
    """Get Prometheus-compatible governance metrics.

    Returns operational metrics including decision counts,
    budget checks, reputation checks, latency, and uptime.
    Use the 'format' field for raw Prometheus text exposition.

    Returns:
        Metrics snapshot as JSON, plus raw Prometheus text.
    """
    snapshot = metrics.snapshot()
    snapshot["prometheus_text"] = metrics.render()
    return snapshot


@mcp.tool()
async def handle_slack_action(
    action_id: str,
    payout_id: str,
    user_name: str = "unknown",
    channel: str | None = None,
    message_ts: str | None = None,
) -> dict[str, Any]:
    """Process a Slack interactive button callback (approve / reject).

    This is the human-in-the-loop handler: when a reviewer clicks
    ✅ Approve or ❌ Reject in Slack, call this tool with the payload.

    Args:
        action_id: Either "approve_payout" or "reject_payout".
        payout_id: The Razorpay payout ID (e.g. "pout_...").
        user_name: Slack username of the reviewer.
        channel: Slack channel ID (for updating the message).
        message_ts: Slack message timestamp (for updating the message).

    Returns:
        Result of the approve/reject action plus message update status.
    """
    _require(razorpay=_razorpay)

    if action_id == "approve_payout":
        result = await _razorpay.approve_payout(payout_id)
        action_label = "approved"
    elif action_id == "reject_payout":
        result = await _razorpay.reject_payout(payout_id)
        action_label = "rejected"

        # --- Budget Rollback for HELD payouts ---
        # If a payout was HELD, its budget was already deducted.
        # When rejecting it, we MUST roll back the budget in Redis.
        if _postgres and _redis:
            audit_logs = await _postgres.get_audit_logs(payout_id=payout_id, limit=1)
            if audit_logs:
                log = audit_logs[0]
                if log.decision == Decision.HELD:
                    await _redis.rollback_budget(log.agent_id, log.amount)
                    logger.info(
                        "Budget rolled back via Slack action: agent=%s amount=%d",
                        log.agent_id, log.amount,
                    )
    else:
        return {"error": f"Unknown action: {action_id}"}

    logger.info(
        "Slack action: %s %s payout %s",
        user_name, action_label, payout_id,
    )

    # Update the Slack message to reflect the decision
    message_updated = False
    if _slack and channel and message_ts:
        try:
            await _slack.update_approval_message(
                channel=channel,
                message_ts=message_ts,
                payout_id=payout_id,
                action="approve" if action_id == "approve_payout" else "reject",
                user_name=user_name,
            )
            message_updated = True
        except Exception as exc:
            logger.warning("Failed to update Slack message: %s", exc)

    if _postgres:
        logger.info(
            "Audit: slack:%s %s payout %s",
            user_name, action_label, payout_id,
        )

    return {
        "status": "ok",
        "action": action_label,
        "payout_id": payout_id,
        "reviewer": user_name,
        "message_updated": message_updated,
        **result,
    }


# ================================================================
# FOSS Integration Tools
# ================================================================


@mcp.tool()
async def verify_vendor_entity(
    vendor_name: str,
    lei: str = "",
) -> dict[str, Any]:
    """Verify a vendor's legal entity via GLEIF (Global LEI Foundation).

    Checks if the vendor is a registered legal entity with a valid LEI
    (Legal Entity Identifier). Uses the free GLEIF API — no API key needed.

    Can search by legal name or look up a specific LEI code directly.

    Args:
        vendor_name: Legal name of the vendor entity to verify.
        lei: Optional 20-character LEI code for direct lookup.

    Returns:
        Verification result with entity details, LEI, jurisdiction,
        and registration status (ISSUED = valid, LAPSED = expired).
    """
    _require(gleif=_gleif)

    if lei and len(lei) == 20:
        result = await _gleif.lookup_lei(lei)
    else:
        result = await _gleif.search_entity(vendor_name)

    response = result.to_dict()
    response["verified"] = result.is_verified
    metrics.record_gleif_check(verified=result.is_verified)
    return response


@mcp.tool()
async def score_transaction_risk(
    amount: int,
    agent_id: str,
) -> dict[str, Any]:
    """Score a transaction for anomaly risk using ML (IsolationForest).

    Analyses the transaction against the agent's historical patterns
    to detect anomalies. Uses scikit-learn's IsolationForest algorithm.

    Features analysed: amount (log-scaled), time of day, day of week,
    and deviation from the agent's typical spending pattern.

    The model auto-trains from Redis-stored transaction history.
    Needs ≥10 historical transactions before producing confident scores.

    Args:
        amount: Transaction amount in paise (₹500 = 50000).
        agent_id: The AI agent initiating the transaction.

    Returns:
        Risk assessment with score (0.0=normal, 1.0=anomalous),
        whether it's flagged as anomalous, feature breakdown,
        and model training status.
    """
    _require(anomaly_scorer=_anomaly_scorer)

    score = await _anomaly_scorer.score_transaction(amount=amount, agent_id=agent_id)
    metrics.record_anomaly_check(
        anomalous=score.is_anomalous,
        model_trained=score.model_trained,
    )
    return score.to_dict()


@mcp.tool()
async def get_agent_risk_profile(
    agent_id: str,
) -> dict[str, Any]:
    """Get the transaction risk profile for an agent.

    Returns statistics about the agent's historical transaction patterns
    including amount distribution, most active hours, and total transactions.

    Useful for understanding what "normal" looks like for an agent before
    reviewing anomaly scores.

    Args:
        agent_id: The AI agent to profile.

    Returns:
        Transaction statistics and spending patterns.
    """
    _require(anomaly_scorer=_anomaly_scorer)

    return await _anomaly_scorer.get_agent_profile(agent_id)


# ================================================================
# Azure AI Foundry & Security Tools
# ================================================================


@mcp.tool()
async def check_context_taint() -> dict[str, Any]:
    """Check if current execution context is tainted by untrusted data.
    
    The Dual LLM quarantine pattern tracks when tools that ingest external
    data (webhooks, Safe Browsing, GLEIF) have been called. Once tainted,
    certain high-privilege tools are blocked to prevent prompt injection.
    
    Returns:
        Taint status, sources that caused tainting, and affected tools.
    """
    _require(tool_validator=_tool_validator)
    
    return {
        "context_tainted": _tool_validator.is_tainted,
        "taint_sources": _tool_validator._taint_sources,
        "dual_llm_tools": _tool_validator._dual_llm_tools,
        "security_llm_configured": _tool_validator.is_configured,
    }


@mcp.tool()
async def validate_tool_call_security(
    tool_name: str,
    parameters: dict[str, Any],
    agent_id: str = "default",
) -> dict[str, Any]:
    """Validate a tool call through the Dual LLM security layer.
    
    When context is tainted, this routes to the security LLM which validates
    the operation WITHOUT access to conversation context (quarantine pattern).
    
    Args:
        tool_name: Name of tool to call.
        parameters: Parameters for the tool call.
        agent_id: Agent requesting the operation.
        
    Returns:
        Validation result with approve/deny decision and reasoning.
    """
    _require(
        tool_validator=_tool_validator,
        postgres=_postgres,
    )
    
    # Get current governance policy for context
    policy = await _postgres.get_agent_policy(agent_id)
    governance_policy = {
        "agent_id": agent_id,
        "daily_limit": str(policy.daily_limit) if policy else None,
        "per_txn_limit": str(policy.per_txn_limit) if policy else None,
        "requires_approval_above": str(policy.require_approval_above) if policy else None,
    }
    
    from vyapaar_mcp.llm.security_validator import ToolCallRequest
    
    result = await _tool_validator.validate(
        tool_name=tool_name,
        parameters=parameters,
        agent_id=agent_id,
        governance_policy=governance_policy,
    )
    
    return {
        "approved": result.approved,
        "reason": result.reason,
        "risk_score": result.risk_score,
        "mitigation": result.mitigation,
        "context_tainted": _tool_validator.is_tainted,
    }


@mcp.tool()
async def azure_chat(
    message: str,
    system_prompt: str = "You are a helpful assistant.",
    temperature: float = 0.7,
    max_tokens: int = 1000,
) -> dict[str, Any]:
    """Send a chat completion request to Azure OpenAI (AI Foundry).
    
    Security note: This tool marks context as TAINTED because LLM responses
    can contain injected content. Subsequent high-privilege tool calls
    require Dual LLM validation or are blocked.
    
    Args:
        message: User message to send.
        system_prompt: System prompt/context for the LLM.
        temperature: Sampling temperature (0-2, default 0.7).
        max_tokens: Maximum tokens to generate.
        
    Returns:
        LLM response text and token usage.
    """
    _require(azure_llm=_azure_llm, tool_validator=_tool_validator)
    
    if not _azure_llm.is_configured:
        return {
            "error": "Azure OpenAI not configured",
            "config_required": [
                "VYAPAAR_AZURE_OPENAI_ENDPOINT",
                "VYAPAAR_AZURE_OPENAI_API_KEY",
            ],
        }
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message},
    ]
    
    response, status = await _azure_llm.chat_completion(
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    
    if response is None:
        return {
            "error": status,
            "hint": "Create deployment at https://ai.azure.com → Deployments → Create deployment",
        }
    
    # Taint context: LLM responses are untrusted
    _tool_validator.mark_taint("azure_chat")
    
    return {
        "response": response,
        "context_note": "Response may be tainted - subsequent critical tools require validation",
    }


@mcp.tool()
async def get_archestra_status() -> dict[str, Any]:
    """Get Archestra deterministic policy enforcement status.
    
    Returns current configuration for the security proxy layer that
    enforces hard boundaries on tool access (vs probabilistic guardrails).
    
    Returns:
        Archestra config, taint tracking status, and policy tiers.
    """
    _require(config=_config, tool_validator=_tool_validator)
    
    return {
        "archestra_enabled": _config.archestra_enabled,
        "archestra_url": _config.archestra_url,
        "policy_set_id": _config.archestra_policy_set_id,
        "security_llm": {
            "url": _config.security_llm_url,
            "model": _config.security_llm_model,
            "configured": _tool_validator.is_configured if _tool_validator else False,
        },
        "dual_llm_config": {
            "taint_sources": _config.taint_sources.split(",") if _config.taint_sources else [],
            "dual_llm_tools": _config.dual_llm_tools.split(",") if _config.dual_llm_tools else [],
            "quarantine_strict": _config.quarantine_strict,
            "audit_logging": _config.quarantine_audit_log,
        },
        "azure_guardrails": {
            "enabled": _config.azure_guardrails_enabled,
            "severity": _config.azure_guardrails_severity,
        },
    }


# ================================================================
# Server Runner
# ================================================================


async def run_server() -> None:
    """Start the Vyapaar MCP server.

    When run directly, lifespan is handled by FastMCP automatically.
    """
    await mcp.run_stdio_async()


def run_server_sync() -> None:
    """Synchronous entrypoint with custom SSE path handling."""
    import os
    import uvicorn
    from starlette.applications import Starlette
    from starlette.routing import Mount, Route
    from mcp.server.sse import SseServerTransport

    transport_name = os.environ.get("VYAPAAR_TRANSPORT", "stdio")
    
    if transport_name == "sse":
        host = os.environ.get("VYAPAAR_HOST", "0.0.0.0")
        port = int(os.environ.get("VYAPAAR_PORT", "8000"))
        
        # Manually create the transport to use /sse for both
        sse = SseServerTransport("/sse")
        
        async def sse_app_unified(request: Request):
            scope, receive, send = request.scope, request.receive, request._send
            if scope["method"] == "GET":
                async with sse.connect_sse(scope, receive, send) as streams:
                    await mcp._mcp_server.run(
                        streams[0],
                        streams[1],
                        mcp._mcp_server.create_initialization_options()
                    )
                # connect_sse already sends the response, don't return another one
                return None
            elif scope["method"] == "POST":
                await sse.handle_post_message(scope, receive, send)
                return None
            return Response("Method Not Allowed", status_code=405)

        starlette_app = Starlette(
            debug=True,
            routes=[
                Route("/sse", endpoint=sse_app_unified, methods=["GET", "POST"]),
                Route("/health", endpoint=health_endpoint, methods=["GET"]),
            ]
        )
        
        # Add custom routes from mcp
        starlette_app.routes.extend(mcp._custom_starlette_routes)
        
        uvicorn.run(starlette_app, host=host, port=port)
    else:
        mcp.run(transport=transport_name)


# Allow direct execution
if __name__ == "__main__":
    run_server_sync()
