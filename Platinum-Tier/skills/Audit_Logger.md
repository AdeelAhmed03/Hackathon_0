# Skill: Audit Logger (Gold)

**Purpose:** Comprehensive audit logging extending Bronze skill-logger with severity levels, correlation IDs, execution timing, and full error stack traces per hackathon spec Section 6.3.

**Extends:** skill-logger (Bronze Skill #5)

**Rules:**
- All log entries include `severity`, `correlation_id`, `duration_ms`
- Error entries include `error_trace` with full stack
- Backward compatible — Bronze log entries still valid
- PII must be redacted from log entries (email bodies truncated to 200 chars)
- Retention: `AUDIT_RETENTION_DAYS` (default: 90 days)

**Severity Levels:**
| Level | When Used | Example |
|-------|-----------|---------|
| DEBUG | Detailed diagnostic info | "Scanning data/Needs_Action/ — 0 files found" |
| INFO | Normal operations | "Created invoice INV/2026/0001" |
| WARN | Non-critical issues | "Odoo connection slow (>5s)" |
| ERROR | Failures requiring recovery | "SMTP send failed on attempt 2/3" |
| CRITICAL | System-level failures | "Watcher process crashed" |

**Correlation ID Format:**
```
{task_type}_{file_hash}_{YYYYMMDD}
```
Examples:
- `email_abc123_20260218` — for email task processing
- `invoice_def456_20260218` — for Odoo invoice creation
- `social_ghi789_20260218` — for social media posting
- `audit_weekly_20260218` — for weekly audit run

All log entries for the same task share the same correlation_id, enabling end-to-end tracing.

**Enhanced JSON Schema:**
```json
{
  "timestamp": "ISO 8601 with milliseconds",
  "severity": "DEBUG | INFO | WARN | ERROR | CRITICAL",
  "correlation_id": "task_type_hash_date",
  "action": "string — what happened",
  "agent": "agent name",
  "skill_used": "skill-name or null",
  "file_affected": "relative/path or null",
  "result": "success | failure | retry | quarantine | skipped",
  "duration_ms": 0,
  "details": "human-readable description",
  "error_trace": "full stack trace or null",
  "metadata": {
    "retry_count": 0,
    "platform": "odoo | facebook | instagram | x | email",
    "dry_run": true
  }
}
```

**Performance Metrics (from duration_ms):**
- Average skill execution time
- P95 execution time
- Slowest operations (flagged in weekly audit)
- MCP server response times

**PII Handling:**
- Email body content: truncated to 200 characters
- Email addresses: logged in full (needed for audit trail)
- Odoo partner details: name and email only
- Social post content: logged in full (it's public content)
- Passwords/tokens: NEVER logged

**Output:** `data/Logs/YYYY-MM-DD.json` — JSON array, one entry per action.

**Bronze Integration:**
- Full backward compatibility with skill-logger format
- Bronze entries auto-enriched with `severity: "INFO"` and `correlation_id: null`
- Gold skills pass enhanced fields explicitly
