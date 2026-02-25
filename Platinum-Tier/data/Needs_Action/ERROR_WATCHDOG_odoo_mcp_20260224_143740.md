---
type: error_alert
status: pending
priority: high
error_type: process_failure
process_name: odoo_mcp
process_type: mcp
restart_attempts: 5
consecutive_failures: 11
created: 2026-02-24T14:37:40Z
---

## Watchdog Alert: odoo_mcp Repeatedly Failing

The process **odoo_mcp** (mcp) has failed **11** consecutive times
and exceeded the maximum restart attempts (5).

**Script:** `mcp-servers/odoo-mcp/odoo_mcp.py`
**Last Started:** 2026-02-24T10:30:05.553516+00:00
**Last Died:** 2026-02-24T14:37:40.612789+00:00
**Total Restarts:** 5

### Required Action

- Check the process logs for errors
- Verify configuration and credentials
- Manually restart: `python mcp-servers/odoo-mcp/odoo_mcp.py`
- If resolved, the watchdog will auto-resume monitoring
