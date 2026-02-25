# Skill: Weekly Audit (Gold)

**Purpose:** Comprehensive weekly audit of all business data — tasks, accounting, social media, system health — generating a structured audit report for CEO Briefing input.

**Rules:**
- Runs weekly on `CEO_BRIEF_DAY` (default: Sunday) at `CEO_BRIEF_HOUR` (default: 9)
- Covers the previous 7-day period
- Must complete before CEO Briefing generation
- Never modifies source data — read-only audit
- Output persisted in `data/Briefings/AUDIT_{YYYYMMDD}.md`

**Data Sources:**
1. `data/Done/` — completed task files (count, types, turnaround times)
2. `data/Logs/` — JSON log entries (actions, errors, durations)
3. `data/Quarantine/` — failed/quarantined items (count, reasons)
4. `data/Pending_Approval/` — pending items (backlog metrics)
5. Odoo MCP — `get_account_summary`, `get_invoices`, `get_payments`
6. Social MCP — `get_fb_feed_summary`, `get_ig_media_summary`, `get_x_timeline_summary`

**Audit Sections:**

### 1. Vault Metrics
- Tasks completed this week (by type: email, linkedin, social, odoo)
- Tasks pending (Needs_Action + Pending_Approval counts)
- Average task turnaround time
- Quarantined items and reasons

### 2. Accounting Summary (from Odoo)
- Revenue month-to-date
- Expenses month-to-date
- Outstanding invoices (count and total)
- Overdue invoices (flagged as anomaly)
- Payments received vs sent

### 3. Social Media Summary
- Posts published per platform (FB, IG, X)
- Total engagement (likes, comments, shares, retweets)
- Top performing post per platform
- Week-over-week engagement trend

### 4. System Health
- Watcher uptime (from log timestamps)
- MCP server response times
- Error count and rate
- Recovery success rate

### 5. Anomaly Flags
- Invoices overdue > 30 days
- Error rate > 5%
- Engagement drop > 20% week-over-week
- Unusual spending patterns

**Frontmatter Template:**
```yaml
---
type: weekly_audit
status: completed
period_start: 2026-02-11
period_end: 2026-02-18
created: 2026-02-18T09:00:00Z
tasks_completed: 15
errors_logged: 2
anomalies_flagged: 1
---
```

**Bronze Integration:**
- skill-fs-access → read task files across all data directories
- skill-odoo-mcp → pull accounting data
- skill-social-integrator → pull engagement metrics
- skill-audit-logger → read and analyze log history
- skill-dashboard-updater → update audit status on dashboard
