# Skill: CEO Briefing (Gold)

## Purpose
Generate Monday Morning CEO Briefing.

## Trigger
- After skill-weekly-audit completes (reads latest `AUDIT_{date}.md`)
- On-demand via manual task file
- Scheduler: `job_ceo_briefing` runs 1 hour after audit on `CEO_BRIEF_DAY`

## Rules
- Read latest `AUDIT_{YYYYMMDD}.md` from `data/Briefings/`
- Call `audit_logic.generate_ceo_briefing(audit_data)` for generation
- Summarize into executive-friendly format (concise, actionable)
- Highlight top 3-5 KPIs with Green/Yellow/Red status indicators
- Flag critical issues requiring CEO attention
- Include proactive suggestions with `[ACTION]` tags and trends
- Maximum 1 page / 500 words

## Output Format (per spec template)
```markdown
# /Briefings/{date}_Monday_Briefing.md
---
generated: ISO
period: from-to
---
# Executive Summary
{tasks completed}, {flags}, {bottlenecks identified}

## Key Performance Indicators
| KPI | Value | Status |
| Revenue vs Target | {pct}% (${received} / ${target}) | Green/Yellow/Red |
| Net Revenue | ${net} | Green/Red |
| Error Rate | {pct}% | Green/Yellow/Red |
...

## Revenue
| Category | Amount |
| Invoiced | ${amount} |
| Received | ${amount} |
| Expenses | ${amount} |
| **Net** | **${amount}** |

## Bottlenecks
| Task | Expected | Actual | Delay |
| Invoice INV/2026/0001 | 2026-03-01 | Unpaid | 15 days overdue |
| Error Recovery | 0 quarantined | 3 items | Needs manual review |
...

## Suggestions
- [ACTION] Cancel sub? — Review {vendor} pricing (+25%)
- [ACTION] Revenue at 40% of target — accelerate invoicing
- [ACTION] 3 quarantined items — review and recover or discard
```

## KPI Status Rules
- **Green**: Revenue ≥80% target, error rate <5%, queue <10
- **Yellow**: Revenue ≥50% target, error rate <10%, queue <20
- **Red**: Below Yellow thresholds — immediate attention

## Gold Spec
- Proactive suggestions, trends
- Depends on skill-weekly-audit output (audit_logic.run_weekly_audit())
- Cross-references personal (email, LinkedIn) and business (Odoo, social) data
- Tone: professional, concise, CEO-appropriate
- Subscription flags from SUBSCRIPTION_PATTERNS generate [ACTION] items

## Prior Integration
- Call after skill-weekly-audit
- Uses skill-fs-access to read audit reports
- Logged via skill-audit-logger
- Dashboard updated with briefing status
- Run standalone: `python audit_logic.py --simulate`
