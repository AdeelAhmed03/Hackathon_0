# Plan Creator Skill

## Purpose
Creates structured Plan.md for tasks requiring more than one step.

## Rules
- Call after skill-needs-action-processor parses the task
- Output to `data/Plans/PLAN_{task_id}.md`
- Single-step tasks do NOT need plans — execute directly

## Plan File Format
```markdown
---
created: ISO
status: pending
steps: 3
---
## Objective
[short desc]

## Steps
- [ ] Step 1
- [ ] Step 2 (if sensitive → note HITL)
- [ ] Step 3

## Dependencies
- Call skill-hitl-watcher if approval needed
```

## Bronze Integration
- Use skill-fs-access to write the plan file to data/Plans/

## Triggers
- Any task in Needs_Action requiring 2+ distinct steps or skills
- Tasks involving external/sensitive actions (email, LinkedIn)

## Integration
- Referenced by agent-core.md step 4 (CREATE PLANS)
- Plans drive skill execution order in step 5
- Works with skill-hitl-watcher for approval-dependent steps
- Completed plans are logged via skill-logger
