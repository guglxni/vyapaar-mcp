#!/usr/bin/env python3
"""Script to add 12 MCP Tool Case Studies to dashboard."""

# Read the dashboard file
with open('demo/dashboard.py', 'r') as f:
    content = f.read()

# Find and replace the E2E Demos section header
old_header = '''# ── Tab: E2E Demos ─────────────────────────────────────────────────
elif tab_choice == "🎬 E2E Demos":
    st.header("🎬 End-to-End Scenario Demos")
    st.caption("Interactive demonstrations of Vyapaar MCP workflows")'''

new_header = r'''# ── Tab: E2E Demos ─────────────────────────────────────────────────
elif tab_choice == "🎬 E2E Demos":
    st.header("🎬 MCP Tool Case Studies")
    st.caption("12 Interactive walkthroughs - one for each MCP tool")

    # Tool Case Studies - 12 comprehensive demos
    tool_case_studies = {
        "handle_razorpay_webhook": {
            "tool": "handle_razorpay_webhook",
            "name": "Handle Razorpay Webhook",
            "icon": "📦",
            "description": "Process incoming payment webhooks from Razorpay",
            "what_it_does": "Receives and validates payment notifications from Razorpay, runs them through the governance pipeline, and returns approval/rejection decisions.",
            "use_cases": ["Payment successful - auto-approve", "Payment failed - alert", "Refund request - verify", "Dispute opened - escalate"],
            "steps": [
                {"step": "1. Receive", "action": "Webhook POST received", "detail": "Validate signature & parse payload"},
                {"step": "2. Enrich", "action": "Fetch additional data", "detail": "Get agent policy, budget status"},
                {"step": "3. Evaluate", "action": "Run governance checks", "detail": "Budget, policy, reputation checks"},
                {"step": "4. Decide", "action": "Make decision", "detail": "APPROVE / REJECT / HOLD"},
                {"step": "5. Respond", "action": "Send response", "detail": "Acknowledge webhook"},
                {"step": "6. Log", "action": "Record decision", "detail": "Write to audit trail"},
            ],
            "example_payload": {"event": "payment.captured", "payload": {"id": "pay_123abc", "amount": 500000}},
            "code_example": 'async def handle_razorpay_webhook(payload):\n    if not verify_signature(payload):\n        return {"status": "error"}\n    decision = await governance_engine.evaluate(payload)\n    return {"status": "success", "decision": decision}'
        },
        "poll_razorpay_payouts": {
            "tool": "poll_razorpay_payouts",
            "name": "Poll Razorpay Payouts",
            "icon": "🔄",
            "description": "Poll Razorpay X API for recent payout events",
            "what_it_does": "Periodically fetches recent payout data from Razorpay and processes through governance.",
            "use_cases": ["Daily reconciliation", "Failed payout detection", "Batch processing"],
            "steps": [
                {"step": "1. Query", "action": "Call Razorpay API", "detail": "GET /payouts"},
                {"step": "2. Filter", "action": "Process new payouts", "detail": "Filter already-processed"},
                {"step": "3. Evaluate", "action": "Governance check", "detail": "Budget & policy"},
                {"step": "4. Action", "action": "Trigger workflows", "detail": "Notify or escalate"},
            ],
            "example_payload": {"count": 5, "items": [{"id": "pout_001", "amount": 10000}]},
            "code_example": "async def poll_razorpay_payouts():\n    payouts = await razorpay.get_payouts()\n    for p in payouts:\n        decision = await governance.evaluate(p)"
        },
        "check_vendor_reputation": {
            "tool": "check_vendor_reputation",
            "name": "Check Vendor Reputation",
            "icon": "🔍",
            "description": "Verify URL safety using Google Safe Browsing",
            "what_it_does": "Checks vendor URLs against Google Safe Browsing threat lists.",
            "use_cases": ["Pre-payment verification", "Vendor onboarding", "Periodic re-verification"],
            "steps": [
                {"step": "1. Input", "action": "Receive URL", "detail": "Validate format"},
                {"step": "2. Check", "action": "Query Safe Browsing", "detail": "Check threats"},
                {"step": "3. Parse", "action": "Analyze response", "detail": "Extract threat types"},
                {"step": "4. Decide", "action": "Make determination", "detail": "SAFE / UNSAFE"},
            ],
            "example_payload": {"url": "https://vendor.com", "safe": True},
            "code_example": "async def check_vendor_reputation(url):\n    result = await safe_browsing.check(url)\n    return result"
        },
        "verify_vendor_entity": {
            "tool": "verify_vendor_entity",
            "name": "Verify Vendor Entity",
            "icon": "🏢",
            "description": "Verify legal entity via GLEIF LEI lookup",
            "what_it_does": "Looks up vendor companies in GLEIF database to verify legitimacy.",
            "use_cases": ["KYC compliance", "Contractor verification", "Supply chain"],
            "steps": [
                {"step": "1. Input", "action": "Receive LEI", "detail": "Validate format"},
                {"step": "2. Query", "action": "Call GLEIF API", "detail": "Search database"},
                {"step": "3. Extract", "action": "Parse entity data", "detail": "Get legal name, status"},
            ],
            "example_payload": {"lei": "549300ABCDEFG123456", "entity": {"legalName": "Example Corp", "status": "ACTIVE"}},
            "code_example": "async def verify_vendor_entity(lei):\n    entity = await gleif.lookup(lei)\n    return {\"verified\": entity.status == \"ACTIVE\"}"
        },
        "get_agent_budget": {
            "tool": "get_agent_budget",
            "name": "Get Agent Budget",
            "icon": "💰",
            "description": "Check remaining daily budget for an agent",
            "what_it_does": "Retrieves current day spending and remaining budget from Redis.",
            "use_cases": ["Pre-payment check", "Dashboard display", "Budget alerts"],
            "steps": [
                {"step": "1. Input", "action": "Receive agent_id", "detail": "Validate exists"},
                {"step": "2. Query", "action": "Read from Redis", "detail": "Get daily spend"},
                {"step": "3. Fetch", "action": "Get policy limit", "detail": "From PostgreSQL"},
                {"step": "4. Calculate", "action": "Compute remaining", "detail": "limit - spent"},
            ],
            "example_payload": {"daily_limit": 5000000, "spent": 1500000, "remaining": 3500000},
            "code_example": "async def get_agent_budget(agent_id):\n    spent = await redis.get(f\"spend:{agent_id}:today\")\n    policy = await db.get_policy(agent_id)\n    return {\"remaining\": policy.limit - spent}"
        },
        "get_audit_log": {
            "tool": "get_audit_log",
            "name": "Get Audit Log",
            "icon": "📜",
            "description": "Query immutable audit trail of decisions",
            "what_it_does": "Retrieves historical records of governance decisions.",
            "use_cases": ["Compliance reporting", "Incident investigation", "Analysis"],
            "steps": [
                {"step": "1. Query", "action": "Receive filters", "detail": "agent_id, date range"},
                {"step": "2. Fetch", "action": "Read from PostgreSQL", "detail": "Audit table"},
                {"step": "3. Return", "action": "Send paginated", "detail": "With total count"},
            ],
            "example_payload": {"total": 100, "entries": [{"decision": "APPROVED", "timestamp": "2024-01-15"}]},
            "code_example": "async def get_audit_log(filters):\n    results = await db.query(\"SELECT * FROM audit_log\")\n    return {\"total\": len(results), \"entries\": results}"
        },
        "set_agent_policy": {
            "tool": "set_agent_policy",
            "name": "Set Agent Policy",
            "icon": "⚙️",
            "description": "Create or update spending rules for an agent",
            "what_it_does": "Stores governance policy including limits and thresholds.",
            "use_cases": ["Initial setup", "Limit adjustments", "Emergency changes"],
            "steps": [
                {"step": "1. Input", "action": "Receive policy", "detail": "Validate fields"},
                {"step": "2. Validate", "action": "Check rules", "detail": "Logical validation"},
                {"step": "3. Store", "action": "Upsert to PostgreSQL", "detail": "Insert or update"},
                {"step": "4. Log", "action": "Audit change", "detail": "Who changed what"},
            ],
            "example_payload": {"agent_id": "bot-001", "daily_limit": 10000000, "per_txn_limit": 1000000},
            "code_example": "async def set_agent_policy(policy):\n    await db.upsert_policy(policy)\n    await audit.log(\"policy_updated\", policy)\n    return {\"status\": \"success\"}"
        },
        "health_check": {
            "tool": "health_check",
            "name": "Health Check",
            "icon": "🏥",
            "description": "Verify all system components are operational",
            "what_it_does": "Checks Redis, PostgreSQL, and external APIs.",
            "use_cases": ["Startup check", "Monitoring", "Load balancer probe"],
            "steps": [
                {"step": "1. Redis", "action": "Ping Redis", "detail": "TCP test"},
                {"step": "2. Database", "action": "Ping PostgreSQL", "detail": "Query test"},
                {"step": "3. APIs", "action": "Check external", "detail": "Razorpay, GLEIF"},
            ],
            "example_payload": {"status": "healthy", "components": {"redis": "ok", "postgres": "ok"}},
            "code_example": "async def health_check():\n    results = {}\n    try: await redis.ping(); results[\"redis\"] = \"ok\"\n    except: results[\"redis\"] = \"error\"\n    return {\"status\": \"healthy\"}"
        },
        "get_metrics": {
            "tool": "get_metrics",
            "name": "Get Metrics",
            "icon": "📊",
            "description": "Retrieve Prometheus-compatible governance metrics",
            "what_it_does": "Exposes governance statistics in Prometheus format.",
            "use_cases": ["Prometheus scraping", "Grafana dashboards", "SLA reporting"],
            "steps": [
                {"step": "1. Collect", "action": "Gather metrics", "detail": "From Redis counters"},
                {"step": "2. Format", "action": "Render Prometheus", "detail": "Text format"},
            ],
            "example_payload": "vyapaar_decisions_total{decision=\"APPROVED\"} 1523",
            "code_example": "async def get_metrics():\n    decisions = await redis.hgetall(\"metrics:decisions\")\n    return render_prometheus(decisions)"
        },
        "handle_slack_action": {
            "tool": "handle_slack_action",
            "name": "Handle Slack Action",
            "icon": "💬",
            "description": "Process Slack interactive button callbacks",
            "what_it_does": "Handles approval/rejection from Slack for human-in-loop workflows.",
            "use_cases": ["Approve payment", "Reject transaction", "Escalate"],
            "steps": [
                {"step": "1. Receive", "action": "Slack callback", "detail": "Interactive payload"},
                {"step": "2. Verify", "action": "Authenticate", "detail": "Verify secret"},
                {"step": "3. Parse", "action": "Extract action", "detail": "approve/reject"},
                {"step": "4. Process", "action": "Update decision", "detail": "Apply to audit"},
            ],
            "example_payload": {"actions": [{"action_id": "approve", "value": "pout_123"}]},
            "code_example": "async def handle_slack_action(payload):\n    if verify_slack(payload):\n        await db.update_decision(payload[\"value\"], payload[\"action\"])"
        },
        "score_transaction_risk": {
            "tool": "score_transaction_risk",
            "name": "Score Transaction Risk",
            "icon": "🎯",
            "description": "ML-based anomaly detection for transactions",
            "what_it_does": "Uses IsolationForest ML model to score transaction anomaly risk.",
            "use_cases": ["Detect unusual amounts", "Spot abnormal patterns", "Time anomalies"],
            "steps": [
                {"step": "1. Feature", "action": "Extract features", "detail": "Amount, vendor, time"},
                {"step": "2. Score", "action": "Run ML model", "detail": "IsolationForest"},
                {"step": "3. Threshold", "action": "Apply thresholds", "detail": "High/Medium/Low"},
            ],
            "example_payload": {"risk_score": 0.85, "risk_level": "HIGH", "factors": ["unusual_amount"]},
            "code_example": "async def score_transaction_risk(tx):\n    features = extract_features(tx)\n    score = model.score_samples([features])\n    return {\"risk_score\": float(score), \"level\": map_level(score)}"
        },
        "get_agent_risk_profile": {
            "tool": "get_agent_risk_profile",
            "name": "Get Agent Risk Profile",
            "icon": "📈",
            "description": "Comprehensive risk analysis for an agent over time",
            "what_it_does": "Analyzes historical patterns to build risk profile.",
            "use_cases": ["Risk trending", "Behavior baseline", "Compliance reporting"],
            "steps": [
                {"step": "1. Fetch", "action": "Get historical data", "detail": "From audit log"},
                {"step": "2. Analyze", "action": "Calculate metrics", "detail": "Volume, anomalies"},
                {"step": "3. Score", "action": "Compute profile", "detail": "Aggregate score"},
            ],
            "example_payload": {"agent_id": "bot-001", "avg_risk": 0.15, "trend": "stable"},
            "code_example": "async def get_agent_risk_profile(agent_id):\n    txns = await db.get_transactions(agent_id)\n    profile = analyze_risk(txns)\n    return profile"
        },
    }

    # Tool selector
    st.markdown("### Select an MCP Tool Case Study")

    selected_tool = st.selectbox(
        "Choose a tool to explore:",
        options=list(tool_case_studies.keys()),
        format_func=lambda k: f"{tool_case_studies[k]['icon']} {tool_case_studies[k]['name']}",
        label_visibility="collapsed"
    )

    if selected_tool:
        study = tool_case_studies[selected_tool]

        # Header
        st.markdown(f"## {study['icon']} {study['name']}")
        st.markdown(f"**{study['description']}**")

        # What it does
        with st.expander("What does this tool do?", expanded=True):
            st.markdown(f"**{study['what_it_does']}**")
            st.markdown("### Common Use Cases:")
            for use_case in study['use_cases']:
                st.markdown(f"- {use_case}")

        # Visual workflow
        st.markdown("### Workflow Steps")

        for i, step in enumerate(study['steps']):
            col1, col2, col3 = st.columns([1, 3, 3])
            with col1:
                st.markdown(f"**{step['step']}**")
            with col2:
                st.markdown(f"_{step['action']}_")
            with col3:
                st.caption(step['detail'])
            if i < len(study['steps']) - 1:
                st.markdown("↓")

        # Example payload
        st.markdown("### Example Payload / Response")
        with st.expander("View payload example"):
            st.json(study['example_payload'])

        # Code example
        st.markdown("### Code Example")
        st.code(study['code_example'], language="python")

        # Interactive demo
        st.markdown("---")
        st.markdown("### Interactive Demo")

        col_demo1, col_demo2 = st.columns([2, 1])
        with col_demo1:
            demo_input = st.text_input("Enter demo input:", value=f"demo_{selected_tool[:10]}")
        with col_demo2:
            if st.button("Run Demo", type="primary", use_container_width=True):
                with st.spinner("Processing..."):
                    import time
                    time.sleep(0.5)
                    st.success(f"✅ {study['name']} executed!")
                    st.json({"status": "success", "tool": selected_tool, "input": demo_input})

        # Related tools
        st.markdown("### Related MCP Tools")
        related = list(tool_case_studies.keys())
        related.remove(selected_tool)
        cols = st.columns(4)
        for i, rel in enumerate(related[:4]):
            with cols[i]:
                st.code(rel, language=None)'''

content = content.replace(old_header, new_header)

with open('demo/dashboard.py', 'w') as f:
    f.write(content)

print("Added 12 MCP Tool Case Studies to dashboard!")
