# Skill: CEO Briefing (Gold)

**Purpose:** Generate a concise, executive-level weekly briefing summarizing vault operations, financial health, social media performance, and actionable recommendations.

**Rules:**
- Runs after weekly audit completes (dependency: skill-weekly-audit)
- Reads latest `data/Briefings/AUDIT_{YYYYMMDD}.md` as primary input
- Output: `data/Briefings/CEO_BRIEF_{YYYYMMDD}.md`
- Maximum 500 words — concise, scannable, actionable
- Professional executive tone
- Must include KPI table, highlights, issues, and recommendations

**Sections:**

### 1. KPI Dashboard (Table)
| Metric | Value | Trend | Status |
|--------|-------|-------|--------|
| Tasks Completed | count | +/- % | Green/Yellow/Red |
| Revenue MTD | $amount | +/- % | Green/Yellow/Red |
| Outstanding Invoices | count | +/- | Green/Yellow/Red |
| Social Engagement | total | +/- % | Green/Yellow/Red |
| System Uptime | % | — | Green/Yellow/Red |
| Error Rate | % | +/- | Green/Yellow/Red |

Status thresholds:
- Green: on target or improving
- Yellow: slight concern or flat
- Red: needs immediate attention

### 2. Key Highlights (2-3 bullets)
- Top achievement of the week
- Notable financial or engagement milestone
- New integration or capability milestone

### 3. Issues Requiring Attention (0-3 items)
- Only items that require CEO decision or awareness
- Each with brief context and recommended action
- Priority-ordered (most critical first)

### 4. Recommendations (2-3 items)
- Actionable next steps based on data
- Tied to specific KPI improvements
- Realistic and implementable within the week

**Cross-Domain Integration:**
- Personal domain: Email response times, LinkedIn engagement
- Business domain: Odoo financials, social media metrics
- System domain: Error rates, watcher uptime, queue depths

**Frontmatter Template:**
```yaml
---
type: ceo_briefing
status: completed
audit_source: AUDIT_20260218.md
period: "Week of 2026-02-11"
kpi_count: 6
issues_flagged: 1
recommendations: 3
created: 2026-02-18T09:30:00Z
---
```

**Bronze Integration:**
- skill-fs-access → read audit report from data/Briefings/
- skill-audit-logger → log briefing generation
- skill-dashboard-updater → update briefing status
- skill-error-recovery → handle missing audit data gracefully
