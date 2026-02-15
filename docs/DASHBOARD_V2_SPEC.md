# Vyapaar MCP Dashboard v2.0 — Enhanced Specification

## 1. Vision
An autonomous financial command center that feels like a "Cyber-Bento" interface. It prioritizes high-density information, real-time reactivity (SSE), and a "Security-First" aesthetic.

## 2. Tech Stack
- **Framework:** Next.js 14 (App Router)
- **Styling:** Tailwind CSS + shadcn/ui
- **Motion:** Framer Motion + ReactBits.dev
- **Data:** Real-time SSE from Vyapaar MCP (Port 8000)
- **Visuals:** Neo-Brutalist (Obsidian & Electric Orange)

## 3. Visual Components (ReactBits Integration)
- **Branding:** `TextPressure` for the "VYAPAAR" logo in the header.
- **Background:** `GridDistortion` applied to the "Threat Intelligence" card for a high-tech vibe.
- **Interactions:** `Magnet` effect on Approve/Reject buttons; `DecryptedText` for loading GLEIF/LEI data.
- **Transitions:** `BlurReveal` for incoming payout alerts.

## 4. Structural Components (shadcn/ui Integration)
- **Audit Logs:** `DataTable` with faceted filters for Decision (APPROVED/REJECTED/HELD).
- **Policy Editor:** `Sheet` component for configuring `set_agent_policy` parameters.
- **Budget Monitoring:** `Progress` bars and `Radial Charts` for daily limit tracking.
- **Global Search:** `Command` (Cmd+K) for jumping between Agents, Vendors, and Payout IDs.
- **Health Monitoring:** `Badge` components showing live status of Redis, Postgres, and Razorpay.

## 5. MCP Tool Mapping (Unified UI)
1. **handle_razorpay_webhook:** Visualized as a live "Incoming Events" stream.
2. **poll_razorpay_payouts:** A "Manual Refresh" button with a spinning `Magnet` icon.
3. **check_vendor_reputation:** A search bar with `HoverCard` threat previews.
4. **get_agent_budget:** Bento cards with circular progress indicators.
5. **get_audit_log:** Main high-density table view.
6. **set_agent_policy:** Interactive form in a sliding side-drawer.
7. **verify_vendor_entity:** "Entity Lookup" module with auto-complete LEI search.
8. **score_transaction_risk:** isolationForest risk gauge with log-scale feature breakdown.
9. **get_agent_risk_profile:** Detailed profile view with spending heatmaps.
10. **check_context_taint:** A global "System Taint" indicator in the status bar.
11. **validate_tool_call_security:** Security validation modal for high-risk actions.
12. **azure_chat:** An embedded "Governance Copilot" chat interface for policy Q&A.

## 6. Implementation Strategy (Plan Only)
- **Day 1:** Scaffold Next.js + shadcn/ui.
- **Day 2:** Integrate ReactBits core components (Grid, Text, Magnet).
- **Day 3:** Establish SSE connection to local MCP server.
- **Day 4:** Build Audit Log Data Table (shadcn).
- **Day 5:** Build Policy Editor & Budget Meters.
- **Day 6:** Implement GLEIF & Safe Browsing Research Modules.
- **Day 7:** ML Risk Dashboard (IsolationForest Visualization).
- **Day 8:** Copilot Integration (Azure AI Chat).
- **Day 9:** Polish, Transitions, and Optimization.
- **Day 10:** Final E2E testing with real Razorpay Sandbox data.
