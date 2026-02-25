---
type: error_alert
status: pending
priority: critical
error_type: process_failure
process_name: orchestrator_local
process_type: orchestrator
restart_attempts: 5
consecutive_failures: 5
created: 2026-02-24T10:33:32Z
---

## Watchdog Alert: [CRITICAL] orchestrator_local Repeatedly Failing

The process **orchestrator_local** (orchestrator) has failed **5** consecutive times
and exceeded the maximum restart attempts (5).

**Script:** `watcher/orchestrator_local.py`
**Last Started:** 2026-02-24T10:30:05.553516+00:00
**Last Died:** 2026-02-24T10:33:32.943787+00:00
**Total Restarts:** 5

### Required Action

- Check the process logs for errors
- Verify configuration and credentials
- Manually restart: `python watcher/orchestrator_local.py`
- If resolved, the watchdog will auto-resume monitoring
