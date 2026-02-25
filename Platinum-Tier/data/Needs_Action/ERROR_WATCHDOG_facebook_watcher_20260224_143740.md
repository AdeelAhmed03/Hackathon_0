---
type: error_alert
status: pending
priority: high
error_type: process_failure
process_name: facebook_watcher
process_type: watcher
restart_attempts: 5
consecutive_failures: 11
created: 2026-02-24T14:37:40Z
---

## Watchdog Alert: facebook_watcher Repeatedly Failing

The process **facebook_watcher** (watcher) has failed **11** consecutive times
and exceeded the maximum restart attempts (5).

**Script:** `watcher/facebook_watcher.py`
**Last Started:** 2026-02-24T10:30:05.553516+00:00
**Last Died:** 2026-02-24T14:37:40.612789+00:00
**Total Restarts:** 5

### Required Action

- Check the process logs for errors
- Verify configuration and credentials
- Manually restart: `python watcher/facebook_watcher.py`
- If resolved, the watchdog will auto-resume monitoring
