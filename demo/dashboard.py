"""Vyapaar MCP — Streamlit Dashboard Demo.

Enhanced Visual Dashboard with Modern Streamlit Design Patterns.
Run: streamlit run demo/dashboard.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from datetime import datetime

import streamlit as st
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


# ── Async Helper ─────────────────────────────────────────────────
def run_async(coro):
    """Run an async coroutine - handles Streamlit's event loop."""
    try:
        return asyncio.run(coro)
    except RuntimeError:
        # Fallback for nested event loops
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(coro)


# ── Initialize Clients (cached, persistent) ───────────────────────
@st.cache_resource
def get_clients():
    """Initialize database and API clients as singletons."""
    from vyapaar_mcp.db.postgres import PostgresClient
    from vyapaar_mcp.db.redis_client import RedisClient
    from vyapaar_mcp.reputation.safe_browsing import SafeBrowsingChecker
    from vyapaar_mcp.config import load_config
    
    config = load_config()
    postgres = PostgresClient(config.postgres_dsn)
    redis = RedisClient(config.redis_url)
    safe_browsing = SafeBrowsingChecker(config.google_safe_browsing_key)
    
    # Connect
    run_async(postgres.connect())
    run_async(redis.connect())
    
    return postgres, redis, safe_browsing, config


# ── Page Config ──────────────────────────────────────────────────
st.set_page_config(
    page_title="Vyapaar Command Center",
    page_icon=":material/security:",
    layout="wide",
)

# ── Sidebar ──────────────────────────────────────────────────────
with st.sidebar:
    st.title("Vyapaar MCP", anchor=False)
    st.caption("Agentic Financial Governance Server")
    
    navigation = st.segmented_control(
        "Navigation",
        options=["Command", "Governance", "Research", "Metrics"],
        default="Command",
        selection_mode="single",
        label_visibility="collapsed"
    )
    
    st.space("large")
    
    with st.container(border=True):
        st.markdown("**Core Capabilities**")
        st.caption("9 MCP Tools Registered")
        tools = [
            "razorpay_webhook", "poll_payouts", "vendor_reputation",
            "agent_budget", "audit_log", "agent_policy",
            "health_check", "get_metrics", "slack_action"
        ]
        for t in tools:
            st.markdown(f":material/check_circle: :orange-badge[{t}]")

# ── Header ───────────────────────────────────────────────────────
postgres, redis, safe_browsing, config = get_clients()

col_logo, col_title = st.columns([0.1, 0.9])
with col_logo:
    st.image("https://img.icons8.com/fluency/96/shield.png", width=64)
with col_title:
    st.title("Autonomous Fintech Firewall", anchor=False)
    st.caption(f"CFO for the Agentic Economy • Connected to {config.postgres_dsn.split('@')[-1]}")

# ── Main Dashboard ───────────────────────────────────────────────

# 1. COMMAND VIEW
if navigation == "Command":
    st.subheader("System Command", anchor=False, icon=":material/terminal:")
    
    with st.container(border=True):
        col1, col2, col3, col4 = st.columns(4)
        
        # Live Health Check
        redis_ok = run_async(redis.ping())
        postgres_ok = run_async(postgres.ping())
        
        col1.metric("Redis State", "Active" if redis_ok else "Down", 
                   delta="Connected" if redis_ok else "Error", 
                   delta_color="normal" if redis_ok else "inverse")
        
        col2.metric("Ledger State", "Active" if postgres_ok else "Down",
                   delta="PostgreSQL" if postgres_ok else "Error",
                   delta_color="normal" if postgres_ok else "inverse")
        
        col3.metric("Slack Ingress", "Enabled" if config.slack_bot_token else "Disabled",
                   icon=":material/chat:" if config.slack_bot_token else ":material/chat_off:")
        
        col4.metric("API Polling", "Active" if config.auto_poll else "Standby",
                   delta=f"Int: {config.poll_interval}s", icon=":material/sync:")

    st.space("medium")
    
    # Audit Stream
    st.subheader("Live Decision Stream", anchor=False, icon=":material/stream:")
    entries = run_async(postgres.get_audit_logs(limit=10))
    
    if entries:
        df = pd.DataFrame([e.model_dump(mode="json") for e in entries])
        st.dataframe(
            df,
            column_config={
                "created_at": st.column_config.DatetimeColumn("Timestamp", format="D MMM, HH:mm:ss"),
                "payout_id": st.column_config.TextColumn("Payout ID"),
                "decision": st.column_config.SelectboxColumn("Decision", options=["APPROVED", "REJECTED", "HELD"]),
                "amount": st.column_config.NumberColumn("Amount (Paise)", format="₹%d"),
                "agent_id": "Agent",
                "reason_code": "Policy Result",
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("No activity detected in the last 24 hours.", icon=":material/history:")

# 2. GOVERNANCE VIEW
elif navigation == "Governance":
    tab_policy, tab_budget = st.tabs(["Agent Policies", "Budget Enforcement"])
    
    with tab_policy:
        st.subheader("Policy Configuration", anchor=False, icon=":material/policy:")
        with st.form("policy_editor", border=True):
            col1, col2 = st.columns(2)
            agent_id = col1.text_input("Agent Identity", value="demo-payments-bot", help="Unique ID for the AI Agent")
            daily_limit = col2.number_input("Daily Spend Limit (INR)", value=5000, step=500)
            
            col3, col4 = st.columns(2)
            per_txn = col3.number_input("Max Per Transaction (INR)", value=1000, step=100)
            approval = col4.number_input("Slack Approval Trigger (INR)", value=500, step=100)
            
            allowed = st.text_area("Domain Whitelist", value="google.com, stripe.com", help="Comma-separated domains")
            
            if st.form_submit_button("Update Policy", type="primary", icon=":material/save:"):
                from vyapaar_mcp.models import AgentPolicy
                new_policy = AgentPolicy(
                    agent_id=agent_id,
                    daily_limit=int(daily_limit * 100),
                    per_txn_limit=int(per_txn * 100),
                    require_approval_above=int(approval * 100),
                    allowed_domains=[d.strip() for d in allowed.split(",") if d.strip()]
                )
                run_async(postgres.upsert_agent_policy(new_policy))
                st.toast(f"Policy updated for {agent_id}", icon=":material/check_circle:")

    with tab_budget:
        st.subheader("Real-time Budget Meter", anchor=False, icon=":material/account_balance_wallet:")
        b_agent = st.text_input("Lookup Agent", value="demo-payments-bot")
        policy = run_async(postgres.get_agent_policy(b_agent))
        
        if policy:
            spent = run_async(redis.get_daily_spend(b_agent))
            rem = max(0, policy.daily_limit - spent)
            util = (spent / policy.daily_limit * 100) if policy.daily_limit > 0 else 0
            
            with st.container(border=True):
                c1, c2, c3 = st.columns(3)
                c1.metric("Allowance", f"₹{policy.daily_limit/100:,.0f}")
                c2.metric("Burned", f"₹{spent/100:,.0f}", delta=f"{util:.1f}%", delta_color="inverse")
                c3.metric("Available", f"₹{rem/100:,.0f}", icon=":material/savings:")
                
                st.progress(min(util/100, 1.0), text=f"Limit Utilization: {util:.1f}%")
        else:
            st.warning("No governing policy found for this identity.")

# 3. RESEARCH VIEW
elif navigation == "Research":
    st.subheader("Intelligence Tools", anchor=False, icon=":material/query_stats:")
    
    col_v, col_e = st.columns(2)
    
    with col_v:
        with st.container(border=True):
            st.markdown("**Safe Browsing Lookup**")
            url_check = st.text_input("Target URL", value="https://google.com")
            if st.button("Analyze Threats", icon=":material/search:"):
                res = run_async(safe_browsing.check_url(url_check))
                if res.is_safe:
                    st.success("CLEAN: No malicious patterns detected.", icon=":material/verified_user:")
                else:
                    st.error(f"DANGER: {', '.join(res.threat_types)}", icon=":material/report_problem:")

    with col_e:
        with st.container(border=True):
            st.markdown("**Legal Entity Verification (GLEIF)**")
            v_name = st.text_input("Vendor Name", value="Razorpay")
            if st.button("Verify Identity", icon=":material/business:"):
                from vyapaar_mcp.reputation.gleif import GLEIFChecker
                # Note: We reuse safe_browsing's internal logic for async fetching if needed
                # but better to use the GLEIFChecker directly
                checker = GLEIFChecker(config.gleif_api_url, redis=redis)
                res = run_async(checker.search_entity(v_name))
                if res.is_verified:
                    st.success(f"VERIFIED: {res.best_match.legal_name}", icon=":material/check_circle:")
                    st.json(res.best_match.model_dump())
                else:
                    st.warning("UNVERIFIED: No issued LEI found.")

# 4. METRICS VIEW
elif navigation == "Metrics":
    st.subheader("Operational Analytics", anchor=False, icon=":material/analytics:")
    from vyapaar_mcp.observability import metrics as governance_metrics
    
    snapshot = governance_metrics.snapshot()
    
    with st.container(border=True):
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Decisions", snapshot.get("decisions_total", 0))
        m2.metric("Approvals", snapshot.get("decisions_approved", 0), icon=":material/done_all:")
        m3.metric("Rejected", snapshot.get("decisions_rejected", 0), icon=":material/block:")
        m4.metric("Held/Manual", snapshot.get("decisions_held", 0), icon=":material/pause_circle:")
        
    st.space("medium")
    
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.markdown("**Latency Performance**")
            st.metric("Avg Processing Time", f"{snapshot.get('avg_latency_ms', 0):.1f} ms", 
                      delta="Real-time", icon=":material/speed:")
    
    with c2:
        with st.container(border=True):
            st.markdown("**Intelligence Hits**")
            checks = snapshot.get("reputation_checks", 0)
            total_checks = sum(checks.values()) if isinstance(checks, dict) else checks
            st.metric("Reputation Lookups", total_checks, icon=":material/travel_explore:")

    with st.expander("Exposition: Prometheus Raw Data", icon=":material/code:"):
        st.code(governance_metrics.render(), language="text")

# ── Footer ───────────────────────────────────────────────────────
st.space("large")
st.caption("Vyapaar Security Engine • v1.26.0 • Fully Autonomous Mode Enabled")
