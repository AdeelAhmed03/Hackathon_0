# Skill: Weekly Audit (Gold)

## Purpose
Audit business/accounting weekly.

## Steps
1. Trigger: Sunday via scheduler (`job_weekly_audit` at `CEO_BRIEF_HOUR`)
2. Read Business_Goals.md, /Accounting/*.md, /Accounting/*.csv, Odoo via MCP
3. Use `audit_logic.py` — `SUBSCRIPTION_PATTERNS` dict to match and flag transactions
4. Call `analyze_transaction()` on each record to classify: saas_monthly, cloud_infra, marketing_ad, contractor, office_ops
5. Identify revenue vs target, bottlenecks (overdue invoices, queue backlog), flags (cost spikes, duplicates)
6. Output `AUDIT_{YYYYMMDD}.md` to `/Briefings/` via `generate_audit_report()`
7. Call skill-ceo-briefing → `generate_ceo_briefing()` for final Monday Briefing

## Data Sources
- `/data/Done/` — completed tasks (past 7 days)
- `/data/Logs/*.json` — log entries, error rates
- `/data/Accounting/*.md` — invoice/payment records (YAML frontmatter)
- `/data/Accounting/*.csv` — CSV transaction imports (date,partner,description,amount,type)
- Odoo MCP — `get_account_summary`, `get_invoices`, `get_transactions`
- Social MCP — `get_fb_feed_summary`, `get_ig_media_summary`, `get_x_timeline_summary`
- `/data/Briefings/SUMMARY_*.md` — social engagement summaries
- `/data/Business_Goals.md` — monthly targets, alert thresholds

## Pattern Matching (audit_logic.py)
```python
SUBSCRIPTION_PATTERNS = {
    "saas_monthly":  r"subscription|saas|monthly|recurring|license|plan",
    "cloud_infra":   r"aws|azure|gcp|cloud|hosting|server|compute|storage",
    "marketing_ad":  r"google ads|facebook ads|meta ads|linkedin ads|ad spend",
    "contractor":    r"freelance|contractor|consulting|retainer|outsource",
    "office_ops":    r"office|supplies|utilities|rent|internet|phone",
}

# Flag rules per category:
#   no_login_days: 30       — flag unused subscriptions
#   cost_increase_pct: 20   — flag cost spikes vs prior period
#   duplicate_window_days: 7 — flag duplicate charges
#   invoice_overdue_days: 30 — flag unpaid invoices
```

## Rules
- Scan `data/Done/` for completed tasks in the past 7 days
- Scan `data/Logs/` for all log entries in the past 7 days
- Query Odoo via skill-odoo-mcp for `get_account_summary` and `get_invoices`
- Query social platforms via skill-social-integrator for engagement summaries
- Count files in each data directory for health metrics
- Generate `AUDIT_{YYYYMMDD}.md` in `data/Briefings/`
- On-demand via manual task file in `data/Needs_Action/`

## Output Format
```markdown
# Weekly Audit Report — {date}

## Vault Metrics
| Metric | Count |
| Tasks Completed | {count} |
...

## Revenue Summary
| Metric | Amount |
| Total Invoiced | ${amount} |
| Total Received | ${amount} |
| **Net Revenue** | **${amount}** |

## Flagged Transactions
| Reference | Partner | Amount | Severity | Flags |
...

## Bottlenecks
| Task | Expected | Actual | Delay |
...

## Social Media
| Platform | Engagement |
...

## System Health
| Metric | Value |
| Error Rate | {pct}% |

## Anomalies
- {anomaly list}
```

## Gold Spec
- Check tasks/Done, bank, Odoo for bottlenecks/revenue
- Feeds directly into skill-ceo-briefing for executive summary generation
- Cross-references Odoo data with email/social activity
- Flags anomalies: overdue invoices >30 days, error rate >5%, engagement drop >20%, cost spikes >20%

## Prior Integration
- Integrate skill-scheduler for timing (`job_weekly_audit` on Sunday)
- Uses skill-fs-access to read completed task files
- Uses skill-audit-logger to read and analyze log data
- Dashboard updated via skill-dashboard-updater with audit results
- Run standalone: `python audit_logic.py --simulate`
