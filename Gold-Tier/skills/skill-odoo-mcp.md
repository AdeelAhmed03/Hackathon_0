# Skill: Odoo MCP (Gold)

## Purpose
Integrate local Odoo Community via MCP (JSON-RPC APIs, Odoo 19+).

## Trigger
- Invoice requests, payment tracking, accounting queries
- Cross-domain: email contacts linked to Odoo partners
- CEO Briefing data collection (account summaries)

## Rules
- MCP server: Call for create invoice, track payment, query accounts
- Format: `invoke_mcp("odoo", {"method": "execute_kw", "model": "account.invoice", "args": [...]})`
- Local self-hosted: Assume running on localhost:8069
- Cross-domain: Link personal email to business invoice creation
- Require HITL for posting invoices/payments
- `ODOO_DRY_RUN=true` must be used for initial testing
- Results saved to `data/Accounting/` as structured .md files
- Available tools: `create_invoice`, `get_invoices`, `create_payment`, `get_payments`, `get_account_summary`, `search_partners`

## Example MCP Call
```
invoke_mcp("odoo", {"method": "execute_kw", "model": "account.invoice", "args": [...]})
invoke_mcp("odoo", {"name": "get_account_summary", "arguments": {}})
invoke_mcp("odoo", {"name": "create_invoice", "arguments": {"partner_name": "Acme Corp", "lines": [{"description": "Consulting", "quantity": 10, "price_unit": 150}]}})
```

## Gold Spec
- Accounting system for business; integrate via MCP
- Cross-domain: Link email sender addresses to Odoo partners via `search_partners`
- Feeds data into skill-weekly-audit and skill-ceo-briefing
- Exponential backoff (3 retries) on Odoo connection failures

## Prior Integration
- Call after skill-plan-creator for finance tasks
- Use skill-approval-request-creator for invoice/payment approvals
- Logged via skill-audit-logger (Gold enhanced)
- Dashboard updated via skill-dashboard-updater
- Error recovery via skill-error-recovery on connection failures
