# Skill: Error Recovery (Gold)

## Purpose
Handle failures gracefully.

## Trigger
- Any skill failure during execution
- Watcher crash or unresponsive MCP server
- Connection errors (Odoo, SMTP, social APIs)

## Steps (per spec Section 7)
1. Classify: Transient (retry w/ backoff), Auth (alert human), Logic (review queue)
2. Retry: Exponential backoff (max 3) — attempt 1 (2s), attempt 2 (4s), attempt 3 (8s)
3. Degrade: Queue in /Quarantine/, continue others
4. Alert: Write ERROR_{id}.md in /Needs_Action/
5. System: Use watchdog for restarts

## Rules
- **Max Retries:** 3 (configurable via `MAX_RETRY_ATTEMPTS`)
- **Never auto-retry payments; fresh approval required**
- **Never silently drop errors** — every failure must be logged and tracked
- **Quarantine:** On permanent failure (all retries exhausted):
  - Move task file to `data/Quarantine/` with error metadata
  - Add `quarantine_reason` and `quarantine_date` to frontmatter
  - Log full error trace via skill-audit-logger
- **Graceful Degradation:**
  - If Odoo is unreachable → skip accounting, continue other tasks
  - If social API fails → skip that platform, post to others
  - If email SMTP fails → keep in Pending_Approval for retry
- Update Dashboard with error/recovery event counts

## Quarantine File Format
```yaml
---
type: quarantined_task
original_type: email_task
original_file: EMAIL_abc123.md
quarantine_reason: "SMTP connection refused after 3 retries"
quarantine_date: 2026-02-18T10:00:00Z
retry_count: 3
error_trace: "ConnectionRefusedError: [Errno 111]..."
recoverable: false
---
```

## Gold Spec
- Never auto-retry payments; fresh approval
- Integrated into every skill execution path
- Error patterns tracked for weekly audit anomaly detection
- Recovery success rate reported in CEO Briefing

## Prior Integration
- Wrap MCP calls, watchers
- skill-fs-access → move files to Quarantine
- skill-audit-logger → log all retry attempts and failures
- skill-dashboard-updater → update error counters
