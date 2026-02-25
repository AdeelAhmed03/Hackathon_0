# Skill: HITL Watcher (Silver)

Purpose: Human-in-the-loop workflow for approvals.

Steps:
1. Watch data/Pending_Approval/ for files
2. If human moves to data/Approved/ → trigger action (e.g. MCP send)
3. If to data/Rejected/ → log and move to data/Done/
4. Use watchdog-like logic (simulate in loop: check every iteration)

Silver spec: Sensitive actions (payments, new sends) always HITL
Bronze integration: Call after skill-plan-creator if steps need approval
