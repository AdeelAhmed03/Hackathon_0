# Agent Core Framework — Silver Tier

## Purpose
The core agent system manages all employee vault operations through a file-based memory system using the Ralph Wiggum autonomous loop pattern. Silver Tier extends Bronze with plan creation, LinkedIn drafts, MCP email, HITL approval processing, and scheduled tasks.

## Architecture
- Monitors data/Needs_Action, data/Approved/, and data/Plans/ for work
- Processes requests according to Company_Handbook policies
- Creates multi-step plans for complex tasks
- Routes approved items through HITL watcher skill
- Manages scheduled task creation and execution
- Updates status in appropriate folders
- Maintains logs in data/Logs
- Updates dashboard in data/Dashboard.md

## File-Based Memory System
The agent uses the file system as its memory:
- Each request is a file in a specific directory
- Directory location indicates request status
- File content contains request details and metadata (YAML frontmatter)
- Agent reads/writes files to process requests and update state
- Plans track multi-step execution progress

## Available Skills (10 Total)

### Bronze Skills (1-5)
1. **skill-fs-access** — Read/write/move files within project directories
2. **skill-needs-action-processor** — Parse and route new task files from Needs_Action
3. **skill-dashboard-updater** — Update counts and activity in Dashboard.md
4. **skill-approval-request-creator** — Generate approval files for sensitive actions
5. **skill-logger** — Append structured JSON log entries to data/Logs/

### Silver Skills (6-10)
6. **skill-plan-creator** — Create multi-step execution plans in data/Plans/
7. **skill-linkedin-draft** — Generate professional LinkedIn post drafts (150-300 words)
8. **skill-mcp-email** — Send email via SMTP (only from Approved/, always HITL)
9. **skill-hitl-watcher** — Route approved files to correct execution skill
10. **skill-scheduler** — Create scheduled task files via time-based triggers

## Silver Ralph Wiggum Loop (13 Steps)

```
┌─────────────────────────────────────────────────────┐
│              RALPH WIGGUM LOOP — SILVER              │
│                                                      │
│  ┌──────────────┐    ┌──────────────┐               │
│  │ 1. READ      │───▶│ 2. READ      │               │
│  │    CONTEXT    │    │    DASHBOARD  │               │
│  └──────────────┘    └──────┬───────┘               │
│                             │                        │
│                             ▼                        │
│                    ┌──────────────┐                  │
│                    │ 3. SCAN      │                  │
│                    │ NEEDS_ACTION  │                  │
│                    └──────┬───────┘                  │
│                           │                          │
│                           ▼                          │
│  ┌──────────────┐    ┌──────────────┐               │
│  │ 4. CREATE    │◀───│  Multi-step? │               │
│  │    PLANS     │    └──────────────┘               │
│  └──────┬───────┘                                   │
│         │                                            │
│         ▼                                            │
│  ┌──────────────┐    ┌──────────────┐               │
│  │ 5. EXECUTE   │───▶│ 6. HANDLE    │               │
│  │    SKILLS    │    │    SENSITIVE  │               │
│  └──────────────┘    └──────┬───────┘               │
│                             │                        │
│                             ▼                        │
│  ┌──────────────┐    ┌──────────────┐               │
│  │ 7. PROCESS   │───▶│ 8. CHECK     │               │
│  │    APPROVED  │    │    SCHEDULED  │               │
│  └──────────────┘    └──────┬───────┘               │
│                             │                        │
│                             ▼                        │
│  ┌──────────────┐    ┌──────────────┐               │
│  │ 9. UPDATE    │───▶│ 10. MOVE     │               │
│  │    DASHBOARD │    │     COMPLETED│               │
│  └──────────────┘    └──────┬───────┘               │
│                             │                        │
│                             ▼                        │
│  ┌──────────────┐    ┌──────────────┐               │
│  │ 11. LOG      │───▶│ 12. CHECK    │               │
│  │  EVERYTHING  │    │  COMPLETION  │               │
│  └──────────────┘    └──────┬───────┘               │
│                             │                        │
│                     ┌───────┴────────┐              │
│                     │                │              │
│                     ▼                ▼              │
│              ┌────────────┐  ┌─────────────┐       │
│              │ TASK_       │  │ 13. CONTINUE│       │
│              │ COMPLETE    │  │  (RALPH_    │       │
│              │ (exit)      │  │  CONTINUE)  │──┐   │
│              └────────────┘  └─────────────┘  │   │
│                     ▲                          │   │
│                     └──────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

### Step 1: READ CONTEXT
Read `Company_Handbook.md` to load all policies, rules, and constraints for this iteration.

### Step 2: READ DASHBOARD
Read `data/Dashboard.md` to understand current system state — counts, recent activity, health.

### Step 3: SCAN NEEDS_ACTION
Read every `.md` file in `data/Needs_Action/`. Parse YAML frontmatter to understand task type, priority, and required actions.

### Step 4: CREATE PLANS
For each task that requires more than one step:
- Invoke **skill-plan-creator** to generate `PLAN_{id}.md` in `data/Plans/`
- Single-step tasks skip plan creation and execute directly
- Plans identify which skills are needed and in what order
- Flag steps that require HITL approval

### Step 5: EXECUTE SKILLS
For each task/plan step, invoke the relevant skill:
- Use the **Decision Tree** below to select the correct skill
- Execute Bronze skills (1-5) and Silver skills (6-10) as needed
- Update plan checkboxes as steps complete

### Step 6: HANDLE SENSITIVE
For any action that is external or sensitive:
- Invoke **skill-approval-request-creator** to create approval file
- Move the approval request to `data/Pending_Approval/`
- Do NOT execute the action — wait for human approval
- Sensitive actions: email sends, LinkedIn posts, file access outside project, data modifications

### Step 7: PROCESS APPROVED
Check `data/Approved/` for files that have been approved by a human:
- Invoke **skill-hitl-watcher** to route each file by its `action` field
- Execute the corresponding skill (email, LinkedIn, file access)
- Update frontmatter with execution results
- Move completed files to `data/Done/`

### Step 8: CHECK SCHEDULED
Check for any `scheduled_task` type files in `data/Needs_Action/`:
- Process them like any other task (they were created by the scheduler)
- Route to appropriate skill based on `task_type` field

### Step 9: UPDATE DASHBOARD
Invoke **skill-dashboard-updater** to refresh `data/Dashboard.md`:
- Count files in each directory (Inbox, Needs_Action, Pending_Approval, Approved, Rejected, Done, Plans)
- Update recent activity log
- Update system health indicators

### Step 10: MOVE COMPLETED
Move all finished task files to `data/Done/`:
- Tasks with status `completed` or `done`
- Plans with all steps checked off
- Processed approval requests

### Step 11: LOG EVERYTHING
Invoke **skill-logger** for every action taken this iteration:
- JSON entries to `data/Logs/YYYY-MM-DD.json`
- Include: timestamp, action, skill_used, file_affected, result, duration

### Step 12: CHECK COMPLETION
Evaluate whether all queues are empty:
- `data/Needs_Action/` has no unprocessed files
- `data/Approved/` has no unprocessed files
- `data/Plans/` has no in_progress plans
- If all empty → proceed to TASK_COMPLETE

### Step 13: CONTINUE OR EXIT
- If queues are empty: output `TASK_COMPLETE` and exit the loop
- If work remains: output `RALPH_CONTINUE` and return to Step 1

## Decision Tree

```
New task file detected
│
├─ Has YAML frontmatter?
│  ├─ YES → Parse type and action fields
│  │  │
│  │  ├─ type: email_task
│  │  │  └─ Create approval request → Pending_Approval (skill-approval-request-creator)
│  │  │
│  │  ├─ type: linkedin_draft
│  │  │  └─ Generate draft → Create approval → Pending_Approval (skill-linkedin-draft)
│  │  │
│  │  ├─ type: scheduled_task
│  │  │  └─ Route by task_type field → appropriate skill
│  │  │
│  │  ├─ type: approval_request (in Approved/)
│  │  │  └─ Route by action field → skill-hitl-watcher
│  │  │
│  │  ├─ type: plan
│  │  │  └─ Execute next unchecked step → appropriate skill
│  │  │
│  │  └─ type: other/unknown
│  │     └─ Multi-step? → skill-plan-creator
│  │        Single-step? → skill-needs-action-processor
│  │
│  └─ NO → skill-needs-action-processor (attempt to parse and route)
│
└─ File is empty or invalid
   └─ Log warning → Move to Done/ with error status
```

## Completion Signals
- `TASK_COMPLETE` — All queues empty, no pending work. Agent exits cleanly.
- `RALPH_CONTINUE` — Work remains in at least one queue. Loop continues.
