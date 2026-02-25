# Skill: Audit Logger (Gold – enhanced)

## Purpose
Comprehensive JSON logging.

## Format (per spec 6.3)
Append to /Logs/{YYYY-MM-DD}.json:
```json
{
  "timestamp": "2026-02-18T10:00:00.000Z",
  "action_type": "email_send",
  "actor": "Autonomous_Employee",
  "target": "client@email",
  "parameters": {},
  "approval_status": "approved",
  "approved_by": "human",
  "result": "success"
}
```

## Rules
- Extends (does not replace) skill-logger — all Bronze logging still works
- Severity levels: DEBUG, INFO, WARN, ERROR, CRITICAL
- Correlation IDs link related log entries across a single task lifecycle
- Duration tracking for performance monitoring
- Output: `data/Logs/YYYY-MM-DD.json` (same directory as skill-logger)
- Retain 90 days (configurable via `AUDIT_RETENTION_DAYS`)
- Log every action, including errors

## Gold Spec
- Log every action, including errors
- All Gold skills use audit-logger instead of basic logger
- Correlation IDs enable tracing a task from Inbox to Done
- Duration tracking feeds into weekly audit performance metrics
- Error traces captured for quarantined tasks

## Prior Integration
- Extend skill-logger
- Backward compatible with existing skill-logger format
- Bronze skills can still write basic log entries
- Gold skills add enhanced fields automatically
