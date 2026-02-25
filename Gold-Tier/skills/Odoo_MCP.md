# Skill: Odoo MCP (Gold)

**Purpose:** Interface with Odoo Community Edition accounting system via JSON-RPC MCP server for invoice management, payment tracking, partner search, and financial summaries.

**Rules:**
- All accounting operations routed through `mcp-servers/odoo-mcp/odoo_mcp.py`
- `ODOO_DRY_RUN=true` for testing — returns realistic mock data
- Invoice creation always requires HITL approval
- Payments above $5000 threshold require HITL approval
- Results persisted as `.md` files in `data/Accounting/`

**Capabilities:**
- `create_invoice` — Create customer invoices with line items
- `get_invoices` — List invoices, filter by state (draft/posted/cancel)
- `create_payment` — Record inbound/outbound payments
- `get_payments` — List payment records with type filtering
- `get_account_summary` — Receivables, payables, revenue, expense totals
- `search_partners` — Find contacts by name or email (cross-domain linking)

**Cross-Domain Integration:**
- Email contacts automatically linked to Odoo partners via `search_partners`
- LinkedIn contacts can be matched to existing Odoo partner records
- Social media engagement metrics feed into CEO Briefing revenue context

**Error Handling:**
- Exponential backoff: 3 retries with 2s, 4s, 8s delays
- On permanent failure: quarantine task to `data/Quarantine/`
- Connection errors logged with full stack trace via skill-audit-logger

**Frontmatter Template:**
```yaml
---
type: odoo_task
action: create_invoice | get_invoices | create_payment | get_payments | get_account_summary | search_partners
status: pending
priority: normal
partner_name: "Acme Corp"
amount: 5000.00
currency: USD
approval_required: true
created: 2026-02-18T10:00:00Z
---
```

**Output File Template (data/Accounting/):**
```yaml
---
type: accounting_record
source: odoo_mcp
action: create_invoice
odoo_ref: INV/2026/0001
partner: "Acme Corp"
amount: 5000.00
currency: USD
state: posted
created: 2026-02-18T10:00:00Z
---

## Invoice Details
- **Reference:** INV/2026/0001
- **Partner:** Acme Corp
- **Amount:** $5,000.00 USD
- **State:** Posted
- **Date:** 2026-02-18
- **Due Date:** 2026-03-18

## Line Items
1. Consulting — 10 x $150.00 = $1,500.00
```

**Bronze Integration:**
- skill-approval-request-creator → HITL for invoices/payments
- skill-audit-logger → comprehensive logging with correlation IDs
- skill-dashboard-updater → update accounting section
- skill-error-recovery → handle Odoo connection failures
