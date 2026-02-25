# Skill: Plan Creator (Silver)

Purpose: Create structured Plan.md for tasks >1 step.

Rules:
- Call after skill-needs-action-processor
- Output to data/Plans/PLAN_{task_id}.md
- Format: ---
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

Bronze integration: Use skill-fs-access to write file
