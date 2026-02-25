# Skill: Ralph Advanced (Gold)

## Purpose
Autonomous multi-step completion.

## Trigger
- Orchestrator starts the Ralph loop
- Watcher detects new files in Needs_Action or Approved

## Rules
- Use file-movement: Stop-hook checks if task in /Done/
- Max iterations: 20
- Claim-by-move: Move to /In_Progress/{agent}/ to own
- On error: Call skill-error-recovery
- Support enhanced control signals:
  - `RALPH_CONTINUE` — work remains, loop again
  - `TASK_COMPLETE` — all queues empty, exit cleanly
  - `RALPH_AUDIT` — trigger weekly audit check before completion
  - `RALPH_RECOVER` — error detected, enter recovery mode
- Queue Priority: Process Approved > Needs_Action > Plans > Scheduled

## Loop Flow (16 Steps)
```
1. READ_CONTEXT → 2. READ_DASHBOARD → 3. SCAN_NEEDS_ACTION
→ 4. CREATE_PLANS → 5. EXECUTE_SKILLS → 6. HANDLE_SENSITIVE
→ 7. PROCESS_APPROVED → 8. CHECK_SCHEDULED → 9. UPDATE_DASHBOARD
→ 10. MOVE_COMPLETED → 11. LOG_EVERYTHING → 12. CHECK_COMPLETION
→ 13. AUDIT_CHECK → 14. ERROR_RECOVERY → 15. GENERATE_DOCS
→ 16. CONTINUE_OR_EXIT
```

## Gold Spec
- Section 2D – promise + file-move strategies
- 16-step loop extends Silver's 13-step loop with 3 new steps
- File-move detection replaces polling for more responsive completion
- Integrates with orchestrator.py for centralized process management

## Prior Integration
- Enhance base Ralph loop
- All Bronze and Silver skills available in each iteration
- Gold skills (11-18) added to the decision tree
- Enhanced logging via skill-audit-logger for every iteration
