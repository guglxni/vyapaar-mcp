# 🎬 2 Fast 2 MCP — Demo Flow

**Project:** Vyapaar MCP — Agentic Financial Governance Server  
**Duration:** 3 minutes  
**Target:** Judges at WeMakeDevs 2 Fast 2 MCP Hackathon

---

## 📺 Demo Overview

> *"Every AI agent needs a CFO. Meet Vyapaar MCP — the financial governance layer that keeps your agents from blowing company money."*

**The Hook:** Show how Vyapaar MCP protects against 6 different financial risks in real AI agent workflows.

---

## 🎯 Scenario 1: Legitimate Vendor Payment ✅

**[0:00 - 0:20] Setup**

```
Narrator: "Imagine an AI agent needing to pay a vendor. Here's what happens when everything is legitimate."
```

**Visual:** Dashboard showing:
- Agent ID: `marketing-agent-001`
- Vendor: Google LLC
- Amount: ₹2,500

**Action:** Click "Simulate Payout"

**Visual:** Step-by-step flow with icons lighting up:
1. ✅ Health Check — All systems operational
2. ✅ Vendor Reputation — Google.com is SAFE
3. ✅ Entity Verification — Google LLC verified via GLEIF
4. ✅ Budget Check — ₹2,500 well within ₹50,000 daily limit
5. ✅ Governance Decision — **APPROVED**

**Result:** 
```
✅ Payment processed in 247ms
📝 Audit log entry created
📊 Metrics updated
```

---

## 🎯 Scenario 2: Suspicious Vendor ❌

**[0:20 - 0:45] The Block**

```
Narrator: "Now let's see what happens when an agent tries to pay a sketchy vendor..."
```

**Visual:** Dashboard showing:
- Agent ID: `marketing-agent-001`
- Vendor: `sketchy-vendor.xyz`  
- Amount: ₹15,000

**Action:** Click "Simulate Payout"

**Visual:** Step-by-step flow:
1. ✅ Health Check
2. ❌ **Vendor Reputation** — THREAT DETECTED
   - Threat type: MALWARE
   - Safe Browsing API: 🚨 ALERT

**Result:**
```
❌ Payment DENIED
Reason: Vendor failed reputation check
Code: THREAT_DETECTED
```

**Narrator:** "The agent tried to pay a malware site. Vyapaar caught it in milliseconds — before any money moved."

---

## 🎯 Scenario 3: Budget Exceeded 💰

**[0:45 - 1:10] The Wall**

```
Narrator: "Even legitimate vendors get blocked when they exceed spending limits."
```

**Visual:** 
- Agent has spent: ₹45,000 today
- Daily limit: ₹50,000
- New payment request: ₹8,000

**Action:** Click "Simulate Payout"

**Visual:**
1. ✅ Health Check
2. ✅ Vendor Reputation — SAFE
3. ✅ Entity Verification — Verified
4. ❌ **Budget Check** — WOULD EXCEED LIMIT
   - Current: ₹45,000
   - Requested: ₹8,000
   - After: ₹53,000 (exceeds ₹50,000)

**Result:**
```
❌ Payment DENIED
Reason: Would exceed daily limit
Remaining budget: ₹5,000
```

---

## 🎯 Scenario 4: High Value = Human Approval 👤

**[1:10 - 1:35] The Approval Flow**

```
Narrator: "For high-value payments, Vyapaar doesn't auto-approve. It brings in a human."
```

**Visual:**
- Vendor: `aws.amazon.com`
- Amount: ₹8,000 (above ₹5,000 threshold)
- Policy: "Require approval above ₹5,000"

**Action:** Click "Simulate Payout"

**Visual:**
1. ✅ All checks pass...
2. ⏸️ **Pending Approval** — Slack notification sent

**Cut to: Slack Mockup**
```
🔔 Vyapaar Alert
━━━━━━━━━━━━━━━━
Agent: marketing-agent-001
Vendor: AWS (amazon.com)
Amount: ₹8,000
Reason: Above approval threshold

[Approve] [Deny]
```

**Action:** Click "Approve"

**Result:**
```
✅ Payment APPROVED (human approved)
📝 Approval recorded in audit log
```

---

## 🎯 Scenario 5: ML Anomaly Detection 🤖

**[1:35 - 2:00] The Smart Detection**

```
Narrator: "But Vyapaar doesn't just check rules — it learns. Here's ML anomaly detection in action."
```

**Visual:**
- Agent: `night-automation-bot`
- Vendor: `unknown-vendor.io`
- Amount: ₹25,000
- **Time: 3:47 AM** (unusual hour)

**Action:** Click "Simulate Payout"

**Visual:**
1. ✅ Health Check
2. ✅ Vendor Reputation — No threats found
3. ⚠️ **ML Anomaly Score: 0.87** (HIGH RISK)
   - Unusual transaction hour
   - First transaction with this vendor
   - Amount > 2x historical average
4. ⚠️ **Governance Decision: FLAGGED**

**Result:**
```
⚠️ Payment FLAGGED for review
Risk score: 87/100
Anomaly factors: 3 detected
```

---

## 🎯 Scenario 6: Policy Change Enforcement ⚙️

**[2:00 - 2:30] Real-Time Governance**

```
Narrator: "Finally — watch how governance policies adapt in real-time."
```

**Visual:** Admin panel - Policy Editor
- Action: Add new rule → "Block all .xyz domains"

**Action:** Click "Save Policy"

**Visual:** Confirmation
```
✅ Policy updated
Effective: Immediately
Affected agents: All
```

**Now test immediately:**
- Agent tries to pay: `new-xyz-vendor.com`
- Amount: ₹1,000

**Result:**
```
❌ Payment DENIED
Reason: Domain blocked by policy
Rule: .xyz domains prohibited
```

**Narrator:** "The policy change took effect instantly. No redeployment needed."

---

## 🎯 Demo Summary

**[2:30 - 3:00]**

```
Narrator: "Vyapaar MCP — The CFO for the Agentic Economy."

🔒 6 Security Layers:
  1. Safe Browsing API — Blocks malware sites
  2. GLEIF Verification — Confirms real entities
  3. Budget Enforcement — Hard limits, no overspending
  4. Human Approval Gate — No auto-approval for big $ 
  5. ML Anomaly Detection — Catches unusual patterns
  6. Policy Engine — Real-time rule updates

📊 Built on Production Stack:
  • FastMCP — 12 MCP tools exposed
  • Redis — Atomic budget counters
  • PostgreSQL — Audit trail
  • Slack — Human-in-the-loop (from env)
  • Azure AI Foundry — Governance LLM (hardcoded)
  • Archestra — Full Foundry integration

🚀 Ready for:
  • Claude Desktop (local dev)
  • Archestra Platform (production)
  • Custom MCP clients

GitHub: github.com/guglxni/vyapaar-mcp
```

---

## 🎬 Recording Tips

1. **Screen Setup:** 1920x1080, dark theme
2. **Browser:** Chrome with Vyapaar dashboard on left, Terminal output on right
3. **Slack:** Use real Slack from your `.env` - no mockup needed
4. **Voiceover:** Record after — edit in post
5. **Background:** Subtle tech music (optional)

---

## 📦 Required Assets

- [x] Demo flow document (this file)
- [x] Automated demo script (demo/automated_demo.py)
- [ ] Dashboard with scenario buttons
- [ ] Screen recording setup
- [ ] Final 3-min video export

---

## 🔑 Environment Configuration

Your `.env` should have these keys configured:

```bash
# Slack (Human-in-the-Loop)
VYAPAAR_SLACK_BOT_TOKEN=xoxb-...
VYAPAAR_SLACK_CHANNEL_ID=C...

# Google Safe Browsing
VYAPAAR_GOOGLE_SAFE_BROWSING_KEY=AIza...

# Razorpay X
VYAPAAR_RAZORPAY_KEY_ID=rzp_test_...
VYAPAAR_RAZORPAY_KEY_SECRET=...
VYAPAAR_RAZORPAY_ACCOUNT_NUMBER=...

# Azure AI Foundry (hardcoded in config)
VYAPAAR_AZURE_OPENAI_ENDPOINT=https://...
VYAPAAR_AZURE_OPENAI_API_KEY=...
```

> **Note:** AI Agent uses Azure AI Foundry (hardcoded). Slack keys are loaded from environment - no BYOK for either.
