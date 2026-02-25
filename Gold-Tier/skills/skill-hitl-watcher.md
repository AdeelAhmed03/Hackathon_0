# HITL Watcher Skill

## Purpose
Human-in-the-loop workflow for approvals. Watches approval directories and routes files based on human decisions.

## Steps
1. Watch `data/Pending_Approval/` for files
2. If human moves to `data/Approved/` → trigger action (e.g. MCP send)
3. If to `data/Rejected/` → log and move to `data/Done/`
4. Use watchdog-like logic (simulate in loop: check every iteration)

## Silver Spec
- Sensitive actions (payments, new sends) always require HITL
- Routes approved files by `action` field: email → skill-mcp-email, linkedin → skill-linkedin-draft, file ops → skill-fs-access

## Bronze Integration
- Call after skill-plan-creator if steps need approval
- Use skill-approval-request-creator to generate the approval files
- Logged via skill-logger
- Dashboard updated via skill-dashboard-updater

## Triggering
- Automated: `watcher/hitl_watcher.py` uses watchdog to detect files in Approved/
- Agent loop: agent-core.md step 7 scans Approved/ each iteration
