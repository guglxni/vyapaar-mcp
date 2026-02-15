# Vyapaar MCP Dashboard Design Specification

## Next.js + React Neo-Brutalist Dashboard

---

## 1. Executive Summary

**Project:** Vyapaar MCP Dashboard  
**Type:** Interactive Web Application  
**Tech Stack:** Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS, Framer Motion  
**Design Philosophy:** Neo-Brutalist - raw, bold, unapologetic  
**Target Audience:** Judges, investors, technical reviewers, potential enterprise customers

---

## 2. Design System

### 2.1 Color Palette

```css
:root {
  /* Core Colors */
  --black: #000000;
  --white: #FFFFFF;
  
  /* Accent - Electric Orange */
  --accent: #FF6B35;
  --accent-hover: #FF8C5A;
  --accent-muted: rgba(255, 107, 53, 0.2);
  
  /* Grayscale */
  --gray-900: #0A0A0A;
  --gray-800: #1A1A1A;
  --gray-700: #2D2D2D;
  --gray-600: #404040;
  --gray-500: #525252;
  --gray-400: #71717A;
  --gray-300: #A1A1AA;
  
  /* Semantic Colors */
  --success: #00FF88;
  --error: #FF3366;
  --warning: #FFDD00;
  --info: #3B82F6;
}
```

### 2.2 Typography

```css
/* Display - Syne (bold, geometric) */
--font-display: 'Syne', sans-serif;

/* Body - Space Mono (technical, monospace) */
--font-body: 'Space Mono', monospace;

/* Font Sizes */
--text-xs: 0.75rem;
--text-sm: 0.875rem;
--text-base: 1rem;
--text-lg: 1.125rem;
--text-xl: 1.25rem;
--text-2xl: 1.5rem;
--text-3xl: 2rem;
--text-4xl: 3rem;
--text-5xl: 4rem;
```

### 2.3 Neo-Brutalist Principles

- **No rounded corners** - All elements use sharp 0px border-radius
- **Bold borders** - 2-3px solid borders on all interactive elements  
- **High contrast** - Pure black backgrounds, white text
- **Visible grid** - Exposed grid lines as design element
- **Brutal shadows** - Offset solid shadows (no blur)
- **Uppercase labels** - All labels in uppercase
- **Monospace numbers** - Tabular figures for data

---

## 3. Page Structure

### 3.1 Landing / Hero Section

**Layout:**
```
┌─────────────────────────────────────────────────┐
│ LOGO [VYAPAAR MCP]              [GITHUB] [DOCS]│
├─────────────────────────────────────────────────┤
│                                                 │
│   ⚡                                            │
│   VYAPAAR MCP                                  │
│   Agentic Financial Governance                  │
│                                                 │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│   │ 12 TOOLS │  │ REAL-TIME│  │ DUAL-LLM │     │
│   │   MCP    │  │ ANALYTICS│  │ SECURITY │     │
│   └──────────┘  └──────────┘  └──────────┘     │
│                                                 │
│   [▶ LIVE DEMO]  [📊 CASE STUDIES]            │
│                                                 │
└─────────────────────────────────────────────────┘
```

### 3.2 Main Navigation

- Fixed sidebar on desktop (left)
- Bottom navigation on mobile
- Keyboard shortcuts for power users

### 3.3 Content Sections

1. **Dashboard Overview** - Real-time metrics
2. **MCP Tools** - All 12 tools with live demos
3. **Case Studies** - Interactive scenarios
4. **Analytics** - Charts and insights
5. **Security** - Dual-LLM showcase
6. **Live Demo** - Interactive playground

---

## 4. Component Library

### 4.1 Core Components

#### BrutalCard
```
Props: variant, accent, glow
Variants: default, accent, success, error, warning
States: default, hover (translate + shadow shift), active
```

#### BrutalButton
```
Variants: primary, secondary, ghost, danger
States: default, hover, active, disabled, loading
Animation: 100ms spring transition
```

#### BrutalInput
```
States: default, focus (accent border + glow), error, disabled
Features: Inline validation, error messages
```

#### MetricCard
```
Layout: Label (uppercase) + Value (large accent) + Trend
Features: Sparkline option, delta indicator
```

#### Data: SortTable
```
Featuresable, filterable, paginated
Styling: Brutal borders, alternating backgrounds
```

### 4.2 Visualization Components

#### PipelineDiagram
- Horizontal flow showing governance decision stages
- Animated connections between steps
- Status indicators per stage

#### RiskGauge
- Semi-circular gauge with gradient
- Animated needle
- Threshold markers

#### TrendChart
- Line chart with area fill
- Interactive tooltips
- Time range selector

#### DistributionPie
- Donut chart with legend
- Center metric display
- Animated segments

---

## 5. Data Integration

### 5.1 Real Data Sources

The dashboard MUST connect to real backend:

```typescript
// API Routes (Next.js)
/api/metrics      → Prometheus metrics
/api/audit       → PostgreSQL audit logs  
/api/health       → Service health status
/api/budget/{id} → Redis budget data
/api/policy/{id} → PostgreSQL policies

// WebSocket (optional for real-time)
/ws/events        → Live decision events
```

### 5.2 Data Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Next.js    │────▶│   API       │────▶│  Backend    │
│  Frontend   │◀────│   Routes    │◀────│  (Go/Node)  │
└─────────────┘     └─────────────┘     └─────────────┘
                                               │
                    ┌─────────────┐            │
                    │  PostgreSQL │◀───────────┤
                    │  Redis      │            │
                    │  Razorpay   │            │
                    └─────────────┘            │
```

### 5.3 Mock Data Policy

**ABSOLUTELY NO MOCK DATA in production code.**  
For development/demo, use:
- `/lib/mock-data.ts` - Explicit mock utilities
- Clear "DEMO MODE" indicators when using mock data
- Environment variables to toggle real vs mock

---

## 6. MCP Tools Integration

### 12 Tools to Showcase

| Category | Tool | Description |
|----------|------|-------------|
| 💰 Payment | handle_razorpay_webhook | Process Razorpay webhooks |
| 💰 Payment | poll_razorpay_payouts | Poll Razorpay X API |
| 🔍 Vendor | check_vendor_reputation | Google Safe Browsing |
| 🔍 Vendor | verify_vendor_entity | GLEIF LEI lookup |
| 💵 Budget | get_agent_budget | Budget status |
| 💵 Budget | set_agent_policy | Policy management |
| 💵 Budget | get_audit_log | Audit trail |
| ⚙️ System | health_check | Service health |
| ⚙️ System | get_metrics | Prometheus metrics |
| 💬 Slack | handle_slack_action | Slack integration |
| 🎯 Risk | score_transaction_risk | ML anomaly detection |
| 🎯 Risk | get_agent_risk_profile | Risk profiling |

### 6.1 Tool Cards

Each tool displayed as interactive card:
- Tool name (monospace)
- One-line description
- Category badge
- "Try It" button → Opens demo modal

### 6.2 Live Demo Modal

For each tool, an interactive demo that:
- Accepts real input parameters
- Calls actual API endpoint
- Shows real response
- Displays processing time

---

## 7. Case Studies (Interactive)

### 7.1 Pre-Built Scenarios

1. **Safe Payment Flow**
   - Step-by-step walkthrough
   - All checks pass
   - Payment approved

2. **Budget Exceeded**
   - Agent at limit
   - Transaction rejected
   - Slack alert sent

3. **Malicious Vendor**
   - URL in blocklist
   - Google Safe Browsing triggered
   - Payment blocked

4. **Prompt Injection**
   - Security LLM detects taint
   - Context invalidated
   - Deterministic fallback

5. **High-Risk Transaction**
   - ML flags anomaly
   - Held for review
   - Human approval workflow

6. **Entity Verification**
   - LEI lookup
   - GLEIF API query
   - Legal entity verified

### 7.2 Interactive Builder

Users can create custom scenarios:
- Select trigger (webhook, poll, manual)
- Configure parameters
- Run through pipeline
- See real-time decision

---

## 8. Animations & Motion

### 8.1 Principles

- **Purposeful** - Every animation serves a purpose
- **Fast** - 100-300ms duration
- **Responsive** - Respects `prefers-reduced-motion`
- **Performance** - GPU-accelerated transforms only

### 8.2 Key Animations

```typescript
// Page load - staggered entrance
staggerChildren: 0.1s
duration: 0.4s
ease: [0.34, 1.56, 0.64, 1] // spring

// Card hover - brutal shift
translate: -2px, -2px  
shadow: 4px 4px 0 currentColor

// Button press - scale
scale: 0.98

// Data update - number counter
duration: 1s
ease: expoOut
```

### 8.3 Page Transitions

- Fade + slight Y translate
- Duration: 200ms
- Stagger child elements

---

## 9. Responsive Design

### 9.1 Breakpoints

```css
--mobile: 0 - 639px
--tablet: 640px - 1023px  
--desktop: 1024px+
--wide: 1440px+
```

### 9.2 Layout Shifts

| Element | Mobile | Tablet | Desktop |
|---------|--------|--------|---------|
| Nav | Bottom bar | Collapsed sidebar | Fixed left sidebar |
| Hero | Stacked | 2-col | 2-col with stats |
| Cards | 1 col | 2 col | 3-4 col |
| Charts | Full width | Full width | Side-by-side |

---

## 10. Technical Architecture

### 10.1 Project Structure

```
vyapaar-dashboard/
├── app/
│   ├── layout.tsx          # Root layout
│   ├── page.tsx           # Landing/hero
│   ├── dashboard/
│   │   └── page.tsx       # Main dashboard
│   ├── tools/
│   │   └── page.tsx       # MCP tools
│   ├── cases/
│   │   └── page.tsx       # Case studies
│   └── api/
│       ├── metrics/
│       ├── audit/
│       └── health/
├── components/
│   ├── ui/                # Base components
│   ├── charts/            # Visualizations
│   ├── tools/             # Tool-specific
│   └── layout/            # Navigation
├── lib/
│   ├── api.ts             # API client
│   ├── mock-data.ts       # Dev mocks only
│   └── types.ts           # TypeScript types
├── public/
│   └── icons/
└── tailwind.config.js
```

### 10.2 Dependencies

```json
{
  "dependencies": {
    "next": "14.x",
    "react": "18.x",
    "framer-motion": "10.x",
    "recharts": "2.x",
    "lucide-react": "icons",
    "tailwindcss": "3.x",
    "clsx": "utility"
  }
}
```

### 10.3 API Integration

```typescript
// Example: Fetch real metrics
async function getMetrics() {
  const res = await fetch('/api/metrics', {
    next: { revalidate: 10 } // ISR - 10s cache
  });
  if (!res.ok) throw new Error('Failed');
  return res.json();
}

// Example: Call MCP tool
async function handleWebhook(payload: WebhookPayload) {
  const res = await fetch('/api/tools/webhook', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
  return res.json();
}
```

---

## 11. Deployment

### 11.1 Build

```bash
npm run build
# Output: .next/ folder
```

### 11.2 Deploy Options

| Platform | Command | Notes |
|----------|---------|-------|
| Vercel | `vercel deploy` | Recommended - zero config |
| Docker | `docker build -t vyapaar-dashboard .` | Containerized |
| Node | `npm start` | Self-hosted |

### 11.3 Environment Variables

```bash
# Required
NEXT_PUBLIC_API_URL=http://localhost:8000

# Optional (for demo mode)
NEXT_PUBLIC_DEMO_MODE=true
```

---

## 12. Acceptance Criteria

### Must Have
- [ ] Neo-brutalist design implemented exactly
- [ ] All 12 MCP tools displayed with descriptions
- [ ] Real data from backend (no mock in production)
- [ ] At least 3 interactive case studies
- [ ] Responsive on mobile/tablet/desktop
- [ ] Page load < 2s
- [ ] Deployed and accessible via URL

### Should Have
- [ ] Live demo for each MCP tool
- [ ] Charts and visualizations
- [ ] Keyboard shortcuts
- [ ] Dark mode toggle (optional)

### Nice to Have
- [ ] WebSocket for real-time updates
- [ ] Custom scenario builder
- [ ] Export to PDF/PNG

---

## 13. Timeline Estimate

| Phase | Days | Deliverable |
|-------|------|-------------|
| Setup | 1 | Next.js project, Tailwind config |
| Design System | 2 | Component library |
| Core Pages | 3 | Dashboard, tools, cases |
| Data Integration | 2 | API routes, real data |
| Polish | 2 | Animations, responsive |
| Deploy | 1 | Vercel/production |
| **Total** | **11 days** | |

---

## 14. References

- Neo-Brutalism: https://www.cccreative.design/blogs/brutalism-vs-neubrutalism-in-ui-design
- Premium Frontend Design: /Users/aaryanguglani/.agents/skills/premium-frontend-design/
- Dashboard Best Practices: https://www.uxpin.com/studio/blog/dashboard-design-principles/
- Next.js Docs: https://nextjs.org/docs

---

*Document Version: 1.0*  
*Last Updated: 2026-02-15*  
*Author: Claude*
