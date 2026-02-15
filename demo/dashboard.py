"""Vyapaar MCP — Streamlit Dashboard Demo.

Visual dashboard that showcases all 9 MCP tools in a single-page app.
Run: streamlit run demo/dashboard.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import streamlit as st

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


# ── Async Helper ─────────────────────────────────────────────────
def run_async(coro):
    """Run an async coroutine - handles Streamlit's event loop."""
    try:
        loop = asyncio.get_running_loop()
        # We're in an async context (rare in Streamlit)
        return asyncio.run(coro)
    except RuntimeError:
        # No running loop - safe to use asyncio.run()
        return asyncio.run(coro)


# ── Initialize Clients (cached, persistent) ───────────────────────
@st.cache_resource
def get_postgres():
    """Get PostgreSQL client - singleton."""
    from vyapaar_mcp.db.postgres import PostgresClient
    from vyapaar_mcp.config import load_config
    
    config = load_config()
    postgres = PostgresClient(config.postgres_dsn)
    return postgres, config


@st.cache_resource  
def get_redis():
    """Get Redis client - singleton."""
    from vyapaar_mcp.db.redis_client import RedisClient
    from vyapaar_mcp.config import load_config
    
    config = load_config()
    redis = RedisClient(config.redis_url)
    return redis, config


@st.cache_resource
def get_safe_browsing():
    """Get Safe Browsing client - singleton."""
    from vyapaar_mcp.reputation.safe_browsing import SafeBrowsingChecker
    from vyapaar_mcp.config import load_config
    
    config = load_config()
    return SafeBrowsingChecker(config.google_safe_browsing_key), config


def init_connections():
    """Initialize database connections once."""
    postgres, config = get_postgres()
    redis, _ = get_redis()
    
    # Connect if not already connected
    try:
        run_async(postgres.connect())
    except Exception:
        pass  # Already connected
    
    try:
        run_async(redis.connect())
    except Exception:
        pass  # Already connected
    
    return postgres, redis, config


# ── Page Config ──────────────────────────────────────────────────
st.set_page_config(
    page_title="Vyapaar MCP Dashboard",
    page_icon=":material/account_balance:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────────
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        padding: 1.2rem;
        border-radius: 12px;
        border: 1px solid #0f3460;
        color: white;
    }
    .metric-card h3 { margin: 0; font-size: 0.85rem; color: #a0a0a0; }
    .metric-card .value { font-size: 2rem; font-weight: 700; color: #00d4ff; }
    .status-ok { color: #00e676; }
    .status-error { color: #ff5252; }
    div[data-testid="stMetricValue"] { font-size: 1.8rem; }
</style>
""", unsafe_allow_html=True)

# ── Initialize ───────────────────────────────────────────────────
try:
    postgres, redis, config = init_connections()
    clients_ok = True
except Exception as e:
    st.error(f"Failed to initialize: {e}")
    clients_ok = False

# ── Sidebar ──────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/bank-building.png", width=64)
    st.title("Vyapaar MCP")
    st.caption("Agentic Financial Governance Server")
    st.divider()

    tab_choice = st.radio(
        "Navigate",
        ["Health", "Policies", "Vendor Check", "Budget", "Audit Log", "Metrics"],
    )

    st.divider()
    st.caption("**9 MCP Tools Registered**")
    tools = [
        "handle_razorpay_webhook",
        "poll_razorpay_payouts", 
        "check_vendor_reputation",
        "get_agent_budget",
        "get_audit_log",
        "set_agent_policy",
        "health_check",
        "get_metrics",
        "handle_slack_action",
    ]
    for t in tools:
        st.code(t, language=None)

# ── Main Content ─────────────────────────────────────────────────
if not clients_ok:
    st.error("Failed to initialize database connections")
    st.stop()

# ── Tab: Health ──────────────────────────────────────────────────
if tab_choice == "Health":
    st.header("System Health")
    st.caption("MCP Tool: `health_check()`")

    # Use a form to batch the health check
    if st.button("Run Health Check", type="primary"):
        with st.spinner("Checking systems..."):
            redis_ok = run_async(redis.ping())
            postgres_ok = run_async(postgres.ping())

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Redis", "OK" if redis_ok else "Error")
        col2.metric("PostgreSQL", "OK" if postgres_ok else "Error")
        col3.metric("Slack", "Configured" if config.slack_bot_token else "Not Set")
        col4.metric("Auto-Poll", "On" if config.auto_poll else "Off")

        st.divider()

        col5, col6 = st.columns(2)
        col5.metric("MCP Tools", "9 registered")
        col6.metric("Rate Limit", f"{config.rate_limit_max_requests} req / {config.rate_limit_window_seconds}s")

        if redis_ok and postgres_ok:
            st.success("All systems operational!")
        else:
            st.warning("Some systems degraded")

# ── Tab: Policies ────────────────────────────────────────────────
elif tab_choice == "Policies":
    st.header("Agent Policies")
    st.caption("MCP Tool: `set_agent_policy()`")

    with st.form("policy_form"):
        col1, col2 = st.columns(2)
        agent_id = col1.text_input("Agent ID", value="demo-payments-bot")
        daily_limit_rupees = col2.number_input("Daily Limit (INR)", value=50000, step=1000)

        col3, col4 = st.columns(2)
        per_txn_rupees = col3.number_input("Per-Transaction Limit (INR)", value=10000, step=500)
        approval_above_rupees = col4.number_input("Require Approval Above (INR)", value=5000, step=500)

        allowed = st.text_input("Allowed Domains (comma-separated)", value="google.com, amazon.in")
        blocked = st.text_input("Blocked Domains (comma-separated)", value="sketchy-vendor.xyz")

        submitted = st.form_submit_button("Save Policy", type="primary")

        if submitted:
            from vyapaar_mcp.models import AgentPolicy

            policy = AgentPolicy(
                agent_id=agent_id,
                daily_limit=int(daily_limit_rupees * 100),
                per_txn_limit=int(per_txn_rupees * 100) if per_txn_rupees else None,
                require_approval_above=int(approval_above_rupees * 100) if approval_above_rupees else None,
                allowed_domains=[d.strip() for d in allowed.split(",") if d.strip()],
                blocked_domains=[d.strip() for d in blocked.split(",") if d.strip()],
            )
            saved = run_async(postgres.upsert_agent_policy(policy))
            st.success(f"Policy saved for agent `{saved.agent_id}`")
            st.json(saved.model_dump(mode="json"))

# ── Tab: Vendor Check ────────────────────────────────────────────
elif tab_choice == "Vendor Check":
    st.header("Vendor Reputation")
    st.caption("MCP Tool: `check_vendor_reputation()`")

    safe_browsing, _ = get_safe_browsing()
    
    url = st.text_input("Enter vendor URL to check", value="https://google.com")

    if st.button("Check Reputation", type="primary"):
        with st.spinner(f"Checking {url}..."):
            result = run_async(safe_browsing.check_url(url))

        if result.is_safe:
            st.success(f"SAFE - No threats detected for `{url}`")
        else:
            st.error(f"UNSAFE - Threats detected for `{url}`")
            st.warning(f"Threat types: {', '.join(result.threat_types)}")

        st.json({
            "url": url,
            "safe": result.is_safe,
            "threats": result.threat_types,
            "match_count": len(result.matches),
        })

    st.divider()
    st.caption("**Test URLs:**")
    st.code("https://google.com - Safe\nhttps://amazon.in - Safe")

# ── Tab: Budget ──────────────────────────────────────────────────
elif tab_choice == "Budget":
    st.header("Agent Budget")
    st.caption("MCP Tool: `get_agent_budget()`")

    budget_agent = st.text_input("Agent ID", value="demo-payments-bot", key="budget_agent")

    if st.button("Check Budget", type="primary"):
        with st.spinner("Fetching budget..."):
            policy = run_async(postgres.get_agent_policy(budget_agent))

        if policy is None:
            st.warning(f"No policy found for agent `{budget_agent}`")
        else:
            spent = run_async(redis.get_daily_spend(budget_agent))
            remaining = max(0, policy.daily_limit - spent)
            utilization = (spent / policy.daily_limit * 100) if policy.daily_limit > 0 else 0

            col1, col2, col3 = st.columns(3)
            col1.metric("Daily Limit", f"INR {policy.daily_limit / 100:,.0f}")
            col2.metric("Spent Today", f"INR {spent / 100:,.0f}")
            col3.metric("Remaining", f"INR {remaining / 100:,.0f}")

            st.progress(min(utilization / 100, 1.0), text=f"Utilization: {utilization:.1f}%")

            if utilization > 80:
                st.warning("Budget utilization above 80%!")
            elif utilization > 0:
                st.info(f"Budget healthy - {100 - utilization:.0f}% remaining")
            else:
                st.success("No spending today - full budget available")

# ── Tab: Audit Log ───────────────────────────────────────────────
elif tab_choice == "Audit Log":
    st.header("Audit Trail")
    st.caption("MCP Tool: `get_audit_log()`")

    col1, col2, col3 = st.columns(3)
    audit_agent = col1.text_input("Filter by Agent ID", value="", key="audit_agent")
    audit_payout = col2.text_input("Filter by Payout ID", value="", key="audit_payout")
    audit_limit = col3.number_input("Max entries", value=20, min_value=1, max_value=500)

    if st.button("Fetch Audit Log", type="primary"):
        with st.spinner("Fetching audit log..."):
            entries = run_async(postgres.get_audit_logs(
                agent_id=audit_agent or None,
                payout_id=audit_payout or None,
                limit=audit_limit,
            ))

        if not entries:
            st.info("No audit entries found.")
        else:
            st.success(f"Found {len(entries)} entries")

            rows = []
            for e in entries:
                d = e.model_dump(mode="json")
                rows.append({
                    "Timestamp": str(d.get("created_at", ""))[:19],
                    "Payout ID": d.get("payout_id", "N/A"),
                    "Decision": d.get("decision", "N/A"),
                    "Agent": d.get("agent_id", "N/A"),
                    "Amount": f"INR {d.get('amount', 0) / 100:,.0f}" if d.get("amount") else "N/A",
                    "Reason": d.get("reason_code", "N/A"),
                })

            st.dataframe(rows, use_container_width=True)

# ── Tab: Metrics ─────────────────────────────────────────────────
elif tab_choice == "Metrics":
    st.header("Governance Metrics")
    st.caption("MCP Tool: `get_metrics()`")

    from vyapaar_mcp.observability import metrics

    if st.button("Refresh Metrics", type="primary"):
        snapshot = metrics.snapshot()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Decisions", snapshot.get("decisions_total", 0))
        col2.metric("Approved", snapshot.get("decisions_approved", 0))
        col3.metric("Rejected", snapshot.get("decisions_rejected", 0))
        col4.metric("Held", snapshot.get("decisions_held", 0))

        st.divider()

        col5, col6, col7 = st.columns(3)
        col5.metric("Avg Latency", f"{snapshot.get('avg_latency_ms', 0):.0f} ms")
        col6.metric("Budget Checks", sum(snapshot.get("budget_checks", {}).values()) if isinstance(snapshot.get("budget_checks"), dict) else snapshot.get("budget_checks", 0))
        col7.metric("Reputation Checks", sum(snapshot.get("reputation_checks", {}).values()) if isinstance(snapshot.get("reputation_checks"), dict) else snapshot.get("reputation_checks", 0))

        st.divider()
        st.subheader("Raw Prometheus Text")
        st.code(metrics.render(), language="text")

# ── Footer ───────────────────────────────────────────────────────
st.divider()
st.caption("Vyapaar MCP | FastMCP + Redis + PostgreSQL + Razorpay X + Slack")
