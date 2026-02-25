# Skill: Error Recovery (Gold)

**Purpose:** Systematic error handling with retry logic, quarantine for permanent failures, and graceful degradation to maintain system availability.

**Rules:**
- Every skill execution wrapped with error recovery
- Retries: 3 attempts with exponential backoff (2s, 4s, 8s)
- Permanent failures quarantined to `data/Quarantine/`
- Never silently drop errors — all logged with full context
- System continues operating even when individual components fail

**Retry Strategy:**
```
Attempt 1 → Execute skill
  ├─ Success → Continue normally
  └─ Failure → Wait 2s
      Attempt 2 → Retry execution
        ├─ Success → Log recovery, continue
        └─ Failure → Wait 4s
            Attempt 3 → Final retry
              ├─ Success → Log recovery, continue
              └─ Failure → QUARANTINE
```

**Quarantine Process:**
1. Create quarantine file from original task with error metadata
2. Move to `data/Quarantine/QUARANTINE_{original_name}_{date}.md`
3. Update frontmatter with:
   - `quarantine_reason`: Human-readable failure description
   - `quarantine_date`: ISO timestamp
   - `retry_count`: Number of attempts made
   - `error_trace`: Full error stack trace
   - `recoverable`: Boolean — can be retried manually later
4. Log quarantine event via skill-audit-logger (severity: ERROR)
5. Update Dashboard error counter

**Graceful Degradation Rules:**
| Component Failure | Degradation Behavior |
|-------------------|---------------------|
| Odoo unreachable | Skip accounting tasks, continue email/social |
| Facebook API error | Skip FB, post to IG and X |
| Instagram API error | Skip IG, post to FB and X |
| Twitter API error | Skip X, post to FB and IG |
| SMTP failure | Keep in Pending_Approval for manual retry |
| Watcher crash | Other watchers continue independently |
| Dashboard write fail | Log error, continue processing |

**Error Categories:**
- **Transient** (retryable): Network timeout, rate limit, temporary 5xx
- **Permanent** (quarantine): Auth failure, invalid data, 4xx errors
- **System** (alert): Disk full, permission denied, process crash

**Frontmatter Template (Quarantine File):**
```yaml
---
type: quarantined_task
original_type: email_task
original_file: EMAIL_abc123.md
quarantine_reason: "SMTP connection refused after 3 retries"
quarantine_date: 2026-02-18T10:00:00Z
retry_count: 3
max_retries: 3
error_trace: "ConnectionRefusedError: [Errno 111] Connection refused"
error_category: transient
recoverable: true
last_attempt: 2026-02-18T10:00:08Z
---

## Error Details
Original task attempted to send email via MCP.
SMTP server at smtp.gmail.com:587 refused connection.

## Recovery Options
1. Check SMTP credentials in .env
2. Verify network connectivity to smtp.gmail.com
3. Move file back to data/Needs_Action/ to retry
```

**Bronze Integration:**
- skill-fs-access → move files between directories
- skill-audit-logger → log all errors with severity and correlation ID
- skill-dashboard-updater → update error/recovery counters
- Feeds into skill-weekly-audit for error trend analysis
