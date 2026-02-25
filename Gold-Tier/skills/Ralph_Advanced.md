# Skill: Ralph Advanced (Gold)

**Purpose:** Advanced Ralph Wiggum autonomous loop with file-move completion detection, multi-queue priority processing, error recovery integration, and 16-step execution cycle.

**Extends:** Silver Ralph Wiggum Loop (13 steps → 16 steps)

**Rules:**
- Process queues in priority order: Approved > Needs_Action > Plans > Scheduled
- File-move to `data/Done/` is the canonical completion signal
- Error recovery invoked automatically on any skill failure
- Weekly audit check integrated into each iteration
- Maximum iterations enforced (default: 30, configurable)

**Control Signals:**
| Signal | Meaning | Action |
|--------|---------|--------|
| `RALPH_CONTINUE` | Work remains in queues | Return to Step 1 |
| `TASK_COMPLETE` | All queues empty | Exit loop cleanly |
| `RALPH_AUDIT` | Weekly audit due | Run skill-weekly-audit before exit |
| `RALPH_RECOVER` | Error detected | Invoke skill-error-recovery |

**16-Step Gold Loop:**

### Steps 1-12 (Inherited from Silver)
1. **READ_CONTEXT** — Load Company_Handbook.md (all policies)
2. **READ_DASHBOARD** — Current system state
3. **SCAN_NEEDS_ACTION** — Parse all pending tasks
4. **CREATE_PLANS** — Multi-step task decomposition
5. **EXECUTE_SKILLS** — Run skills per decision tree
6. **HANDLE_SENSITIVE** — Create approval requests for external actions
7. **PROCESS_APPROVED** — Route approved items via HITL watcher
8. **CHECK_SCHEDULED** — Process scheduled task triggers
9. **UPDATE_DASHBOARD** — Refresh dashboard counts and activity
10. **MOVE_COMPLETED** — Move finished tasks to Done/
11. **LOG_EVERYTHING** — Comprehensive audit logging
12. **CHECK_COMPLETION** — Evaluate queue states

### Steps 13-16 (Gold Additions)
13. **AUDIT_CHECK** — Is weekly audit due? Check `CEO_BRIEF_DAY` + `CEO_BRIEF_HOUR`
    - If due: invoke skill-weekly-audit → skill-ceo-briefing
    - If not due: skip
14. **ERROR_RECOVERY** — Any errors this iteration?
    - If errors: invoke skill-error-recovery for each failed operation
    - Quarantine permanently failed tasks
    - Log recovery attempts
15. **GENERATE_DOCS** — Documentation update check
    - If significant changes detected: invoke skill-doc-generator
    - Typically runs end-of-session, not every iteration
16. **CONTINUE_OR_EXIT** — Enhanced completion check
    - All queues empty AND no pending recoveries → `TASK_COMPLETE`
    - Work remains → `RALPH_CONTINUE`
    - Audit due → `RALPH_AUDIT` (triggers audit, then re-check)

**Queue Priority Processing:**
```
1. data/Approved/     → Highest priority (human waited for this)
2. data/Needs_Action/ → New tasks from watchers
3. data/Plans/        → In-progress multi-step plans
4. Scheduled tasks    → Time-triggered recurring items
5. data/Quarantine/   → Review recoverable items (lowest priority)
```

**File-Move Completion Detection:**
Instead of only checking queue counts, the advanced loop detects when specific task files move to `data/Done/`:
- Watcher events (inotify/watchdog) signal completion
- More responsive than polling-based checks
- Natural workflow — file moves ARE the state transitions

**Batch Processing:**
When multiple tasks are in the same queue:
- Group by type (email, social, odoo, internal)
- Execute same-type tasks together for efficiency
- Maintain individual logging per task (via correlation IDs)

**Bronze Integration:**
- All 18 skills available (5 Bronze + 5 Silver + 8 Gold)
- Decision tree extended with Gold task types
- Enhanced logging via skill-audit-logger for every step
- Error recovery wraps every skill execution
