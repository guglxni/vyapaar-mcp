-- ============================================================================
-- Foundry-Style Deterministic Access Policies for Vyapaar MCP
-- Based on: https://archestra.ai/docs/platform-foundry
-- 
-- The Microsoft Foundry article demonstrates that probabilistic guardrails
-- (LLM-based detection) fail against indirect prompt injection. Archestra's
-- deterministic controls enforce HARD boundaries on what tools can/cannot do.
--
-- Key principle: Instead of detecting bad prompts, we enforce good behavior.
-- ============================================================================

-- ============================================================================
-- 1. UPGRADE existing invocation policies from "require_dual_llm" to "deny"
--    for the most critical financial operations when context is tainted.
--    
--    The Foundry article shows: even with guardrails, an agent can be tricked
--    into creating unauthorized actions. DENY is the only safe default.
-- ============================================================================

-- Delete old "require_dual_llm" policies — we'll replace with stricter ones
DELETE FROM tool_invocation_policies WHERE tool_id IN (
  'a0000001-0000-4000-8000-000000000001',  -- handle_razorpay_webhook
  'a0000001-0000-4000-8000-000000000009',  -- handle_slack_action
  'a0000001-0000-4000-8000-000000000006'   -- set_agent_policy
);

-- Foundry-style DENY policies: hard block when context is tainted
-- These are deterministic — no LLM can override them
INSERT INTO tool_invocation_policies (id, tool_id, action, reason, conditions, created_at, updated_at) VALUES

-- CRITICAL: Webhook processing with tainted context = DENY
-- Foundry lesson: untrusted content in tool results can cause task drift
(gen_random_uuid(),
 'a0000001-0000-4000-8000-000000000001',
 'deny',
 'FOUNDRY POLICY: Webhook processing is blocked when context is tainted. '
 'Indirect prompt injections in webhook payloads can cause unauthorized financial '
 'operations (data leakage + task drift). Deterministic deny prevents the lethal trifecta.',
 '{"when_context_tainted": true, "foundry_rule": "no_untrusted_financial_ingress"}',
 NOW(), NOW()),

-- CRITICAL: Slack approval actions with tainted context = DENY
-- Foundry lesson: agent can be tricked into approving payouts it shouldn't
(gen_random_uuid(),
 'a0000001-0000-4000-8000-000000000009',
 'deny',
 'FOUNDRY POLICY: Slack approval actions are blocked when context is tainted. '
 'An agent processing untrusted content must not trigger approval workflows — '
 'this prevents indirect prompt injection from auto-approving payouts.',
 '{"when_context_tainted": true, "foundry_rule": "no_tainted_approval_actions"}',
 NOW(), NOW()),

-- CRITICAL: Policy modification with tainted context = DENY
-- Foundry lesson: agent can be tricked into changing its own governance rules
(gen_random_uuid(),
 'a0000001-0000-4000-8000-000000000006',
 'deny',
 'FOUNDRY POLICY: Policy changes are blocked when context is tainted. '
 'An attacker could inject instructions to raise spending limits or remove '
 'approval thresholds. Governance rules must only change from trusted context.',
 '{"when_context_tainted": true, "foundry_rule": "no_tainted_policy_changes"}',
 NOW(), NOW()),

-- NEW: Score transaction risk with tainted context = require Dual LLM
-- Less critical than above, but ML scoring on tainted data needs validation
(gen_random_uuid(),
 'a0000001-0000-4000-8000-000000000011',
 'require_dual_llm',
 'FOUNDRY POLICY: Transaction risk scoring requires Dual LLM validation when '
 'context is tainted. Attackers could manipulate scoring by injecting false '
 'transaction parameters via untrusted content.',
 '{"when_context_tainted": true, "foundry_rule": "validate_tainted_risk_scoring"}',
 NOW(), NOW()),

-- NEW: Payout polling with tainted context = require Dual LLM  
-- Polling itself is less risky than webhook, but results enter governance pipeline
(gen_random_uuid(),
 'a0000001-0000-4000-8000-000000000002',
 'require_dual_llm',
 'FOUNDRY POLICY: Payout polling requires Dual LLM validation when context is '
 'tainted. While polling is read-only, its results feed the governance pipeline '
 'and could be used to construct further injection payloads.',
 '{"when_context_tainted": true, "foundry_rule": "validate_tainted_polling"}',
 NOW(), NOW());


-- ============================================================================
-- 2. ADD Foundry-style ALLOW policies for read-only tools
--    
--    From the article: "Agent can READ issues from any repository"
--    Applied to Vyapaar: read-only observability tools are always allowed
-- ============================================================================

-- Read-only tools get explicit ALLOW even when context is tainted
-- These cannot cause data exfiltration or unauthorized actions
INSERT INTO tool_invocation_policies (id, tool_id, action, reason, conditions, created_at, updated_at) VALUES

-- Health check: always allowed (no sensitive data, no side effects)
(gen_random_uuid(),
 'a0000001-0000-4000-8000-000000000007',
 'allow',
 'FOUNDRY POLICY: Health check is always allowed regardless of context trust. '
 'Returns only system status — no sensitive data, no external communication, no side effects.',
 '{"always": true, "foundry_rule": "allow_readonly_observability"}',
 NOW(), NOW()),

-- Metrics: always allowed (aggregated data only)
(gen_random_uuid(),
 'a0000001-0000-4000-8000-000000000008',
 'allow',
 'FOUNDRY POLICY: Metrics retrieval is always allowed regardless of context trust. '
 'Returns aggregated counters — no PII, no transaction details, no exfiltration risk.',
 '{"always": true, "foundry_rule": "allow_readonly_observability"}',
 NOW(), NOW()),

-- Budget check: always allowed (read-only, no modification)
(gen_random_uuid(),
 'a0000001-0000-4000-8000-000000000004',
 'allow',
 'FOUNDRY POLICY: Budget queries are always allowed. Reading budget status is '
 'read-only and helps the agent enforce governance. No write capability.',
 '{"always": true, "foundry_rule": "allow_readonly_governance"}',
 NOW(), NOW()),

-- Audit log: always allowed (read-only immutable trail)
(gen_random_uuid(),
 'a0000001-0000-4000-8000-000000000005',
 'allow',
 'FOUNDRY POLICY: Audit log queries are always allowed. The audit trail is '
 'append-only and read access helps the agent make informed decisions.',
 '{"always": true, "foundry_rule": "allow_readonly_governance"}',
 NOW(), NOW()),

-- Risk profile: always allowed (read-only analysis)
(gen_random_uuid(),
 'a0000001-0000-4000-8000-000000000012',
 'allow',
 'FOUNDRY POLICY: Risk profile queries are always allowed. Risk assessment is '
 'read-only aggregation that supports governance decisions.',
 '{"always": true, "foundry_rule": "allow_readonly_governance"}',
 NOW(), NOW());


-- ============================================================================
-- 3. ADDITIONAL trusted data policies for Foundry completeness
--    
--    Mark which tool OUTPUTS are safe (trusted) vs unsafe (taint context)
--    Default-deny: everything is untrusted unless explicitly marked
-- ============================================================================

-- Health check output is trusted (internal system status only)
INSERT INTO trusted_data_policies (id, tool_id, action, description, conditions, created_at, updated_at) VALUES
(gen_random_uuid(),
 'a0000001-0000-4000-8000-000000000007',
 'trust_output',
 'FOUNDRY POLICY: Health check output is trusted — contains only internal '
 'system status (Redis/PG/Razorpay connectivity). No external data.',
 '{"output_type": "internal_status", "foundry_rule": "trust_internal_observability"}',
 NOW(), NOW()),

-- Metrics output is trusted (internal aggregated counters)
(gen_random_uuid(),
 'a0000001-0000-4000-8000-000000000008',
 'trust_output',
 'FOUNDRY POLICY: Metrics output is trusted — contains only aggregated '
 'governance counters. No external data, no PII.',
 '{"output_type": "internal_metrics", "foundry_rule": "trust_internal_observability"}',
 NOW(), NOW()),

-- Budget output is trusted (internal governance state)
(gen_random_uuid(),
 'a0000001-0000-4000-8000-000000000004',
 'trust_output',
 'FOUNDRY POLICY: Budget status output is trusted — contains internal spend '
 'tracking computed from governance engine. No external data sources.',
 '{"output_type": "internal_governance", "foundry_rule": "trust_internal_governance"}',
 NOW(), NOW()),

-- Audit log output is trusted (internal append-only trail)
(gen_random_uuid(),
 'a0000001-0000-4000-8000-000000000005',
 'trust_output',
 'FOUNDRY POLICY: Audit log output is trusted — contains internal governance '
 'decisions from the immutable audit trail. Already validated at write time.',
 '{"output_type": "internal_audit", "foundry_rule": "trust_internal_governance"}',
 NOW(), NOW()),

-- Risk profile output is trusted (internal ML analysis)
(gen_random_uuid(),
 'a0000001-0000-4000-8000-000000000012',
 'trust_output',
 'FOUNDRY POLICY: Risk profile output is trusted — contains internally computed '
 'risk scores from IsolationForest model. Analysis is on historical data.',
 '{"output_type": "internal_analysis", "foundry_rule": "trust_internal_governance"}',
 NOW(), NOW()),

-- Transaction risk score output is UNTRUSTED (uses external inputs)
(gen_random_uuid(),
 'a0000001-0000-4000-8000-000000000011',
 'taint_context',
 'FOUNDRY POLICY: Transaction risk score uses caller-provided amount/vendor data '
 'which may originate from untrusted sources. Output taints context.',
 '{"on_output": true, "foundry_rule": "taint_external_input_dependent"}',
 NOW(), NOW());


-- ============================================================================
-- 4. UPDATE agent to reflect Foundry security model
-- ============================================================================

UPDATE agents SET
  system_prompt = 'You are the Vyapaar Financial Governance Agent, secured by Archestra''s Foundry-style deterministic access controls.

SECURITY MODEL (Foundry Deterministic Controls):
You operate under Archestra''s proxy layer which enforces HARD boundaries on tool access.
These policies CANNOT be overridden by any prompt — they are deterministic, not probabilistic.

LETHAL TRIFECTA PROTECTION:
1. UNTRUSTED DATA: Webhook payloads, polling results, Safe Browsing responses, and GLEIF data are all marked as untrusted. When these enter your context, it becomes "tainted."
2. TAINTED CONTEXT RESTRICTIONS: When your context is tainted, high-privilege tools (webhook processing, Slack approvals, policy changes) are BLOCKED by Archestra. No prompt can override this.
3. READ-ONLY ALWAYS ALLOWED: Health checks, metrics, budget queries, audit logs, and risk profiles are always accessible — they have no side effects and return only internal data.

GOVERNANCE RULES:
1. NEVER approve a payout without first checking vendor reputation via Safe Browsing AND GLEIF verification
2. ALWAYS verify budget constraints before processing any transaction
3. Flag any transaction exceeding requires_approval_above for human review via Slack
4. Log ALL governance decisions to the immutable audit trail
5. When context is tainted by external data, you will receive clear errors from Archestra if you attempt restricted operations — this is by design

TOOL TRUST LEVELS:
- TRUSTED OUTPUT (does not taint): health_check, get_metrics, get_agent_budget, get_audit_log, get_agent_risk_profile
- UNTRUSTED OUTPUT (taints context): handle_razorpay_webhook, poll_razorpay_payouts, check_vendor_reputation, verify_vendor_entity, score_transaction_risk
- BLOCKED WHEN TAINTED: handle_razorpay_webhook, handle_slack_action, set_agent_policy
- DUAL LLM REQUIRED WHEN TAINTED: poll_razorpay_payouts, score_transaction_risk

Available tools: webhook processing, payout polling, vendor reputation (Safe Browsing + GLEIF), budget management, policy configuration, anomaly detection, risk profiling, audit logging, Slack approval workflows, health monitoring, and metrics.',
  updated_at = NOW()
WHERE id = '30000000-0000-4000-8000-000000000001';
