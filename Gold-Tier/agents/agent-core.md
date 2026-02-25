# Agent Core Framework — Gold Tier

## Purpose
The core agent system manages all employee vault operations through a file-based memory system using the Ralph Wiggum autonomous loop pattern. Gold Tier extends Silver with Odoo accounting, social media integration (FB/IG/X), weekly CEO briefings, comprehensive audit logging, error recovery, and architecture documentation. All AI functionality is implemented as Agent Skills.

## Architecture
- Monitors data/Needs_Action, data/Approved/, data/Plans/, and data/Accounting/ for work
- Processes requests according to Company_Handbook policies (Bronze + Silver + Gold)
- Creates multi-step plans for complex tasks
- Routes approved items through HITL watcher skill
- Interfaces with Odoo via odoo-mcp for accounting operations
- Posts to social media via social-mcp (FB, IG, X) with mandatory HITL
- Generates weekly audits and CEO briefings
- Handles errors with retry logic and quarantine
- Manages scheduled task creation and execution
- Updates status in appropriate folders
- Maintains comprehensive audit logs in data/Logs
- Updates dashboard in data/Dashboard.md

## File-Based Memory System
The agent uses the file system as its memory:
- Each request is a file in a specific directory
- Directory location indicates request status
- File content contains request details and metadata (YAML frontmatter)
- Agent reads/writes files to process requests and update state
- Plans track multi-step execution progress
- Quarantine holds permanently failed tasks

## Available Skills (18 Total)

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

### Gold Skills (11-18)
11. **skill-odoo-mcp** — Interface with Odoo Community accounting via JSON-RPC MCP
12. **skill-social-integrator** — Post to FB/IG/X and generate engagement summaries
13. **skill-weekly-audit** — Audit business data (tasks, accounting, social, health)
14. **skill-ceo-briefing** — Generate executive summary from audit data
15. **skill-error-recovery** — Retry logic, quarantine, graceful degradation
16. **skill-audit-logger** — Enhanced logging (severity, correlation IDs, duration)
17. **skill-ralph-advanced** — Advanced Ralph loop with file-move completion detection
18. **skill-doc-generator** — Generate ARCHITECTURE.md and LESSONS.md

## Gold Ralph Wiggum Loop (16 Steps)

```
┌─────────────────────────────────────────────────────────┐
│                RALPH WIGGUM LOOP — GOLD                  │
│                                                          │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │ 1. READ      │───▶│ 2. READ      │                   │
│  │    CONTEXT    │    │    DASHBOARD  │                   │
│  └──────────────┘    └──────┬───────┘                   │
│                             │                            │
│                             ▼                            │
│                    ┌──────────────┐                      │
│                    │ 3. SCAN      │                      │
│                    │ NEEDS_ACTION  │                      │
│                    └──────┬───────┘                      │
│                           │                              │
│                           ▼                              │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │ 4. CREATE    │◀───│  Multi-step? │                   │
│  │    PLANS     │    └──────────────┘                   │
│  └──────┬───────┘                                       │
│         │                                                │
│         ▼                                                │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │ 5. EXECUTE   │───▶│ 6. HANDLE    │                   │
│  │    SKILLS    │    │    SENSITIVE  │                   │
│  └──────────────┘    └──────┬───────┘                   │
│                             │                            │
│                             ▼                            │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │ 7. PROCESS   │───▶│ 8. CHECK     │                   │
│  │    APPROVED  │    │    SCHEDULED  │                   │
│  └──────────────┘    └──────┬───────┘                   │
│                             │                            │
│                             ▼                            │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │ 9. UPDATE    │───▶│ 10. MOVE     │                   │
│  │    DASHBOARD │    │     COMPLETED│                   │
│  └──────────────┘    └──────┬───────┘                   │
│                             │                            │
│                             ▼                            │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │ 11. LOG      │───▶│ 12. CHECK    │                   │
│  │  EVERYTHING  │    │  COMPLETION  │                   │
│  └──────────────┘    └──────┬───────┘                   │
│                             │                            │
│                             ▼                            │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │ 13. AUDIT    │───▶│ 14. ERROR    │                   │
│  │    CHECK     │    │    RECOVERY  │                   │
│  └──────────────┘    └──────┬───────┘                   │
│                             │                            │
│                             ▼                            │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │ 15. GENERATE │───▶│ 16. CONTINUE │                   │
│  │    DOCS      │    │    OR EXIT   │                   │
│  └──────────────┘    └──────┬───────┘                   │
│                      ┌──────┴──────┐                    │
│                      │             │                    │
│                      ▼             ▼                    │
│               ┌────────────┐ ┌─────────────┐           │
│               │ TASK_       │ │ RALPH_      │           │
│               │ COMPLETE    │ │ CONTINUE    │──┐       │
│               │ (exit)      │ └─────────────┘  │       │
│               └────────────┘        ▲          │       │
│                                     └──────────┘       │
└─────────────────────────────────────────────────────────┘
```

### Step 1: READ CONTEXT
Read `Company_Handbook.md` to load all policies, rules, and constraints (Bronze + Silver + Gold).

### Step 2: READ DASHBOARD
Read `data/Dashboard.md` to understand current system state — counts, recent activity, health.

### Step 3: SCAN NEEDS_ACTION
Read every `.md` file in `data/Needs_Action/`. Parse YAML frontmatter to understand task type, priority, and required actions.

### Step 4: CREATE PLANS
For each task requiring more than one step:
- Invoke **skill-plan-creator** to generate `PLAN_{id}.md` in `data/Plans/`
- Single-step tasks skip plan creation and execute directly
- Plans identify which skills are needed and in what order
- Flag steps that require HITL approval

### Step 5: EXECUTE SKILLS
For each task/plan step, invoke the relevant skill:
- Use the **Decision Tree** below to select the correct skill
- Execute Bronze (1-5), Silver (6-10), and Gold (11-18) skills as needed
- Update plan checkboxes as steps complete
- Wrap each execution with error recovery (skill-error-recovery)

### Step 6: HANDLE SENSITIVE
For any action that is external or sensitive:
- Invoke **skill-approval-request-creator** to create approval file
- Move the approval request to `data/Pending_Approval/`
- Do NOT execute the action — wait for human approval
- Sensitive actions: emails, LinkedIn posts, social media posts, Odoo invoices >$5000, file access outside project

### Step 7: PROCESS APPROVED
Check `data/Approved/` for files that have been approved by a human:
- Invoke **skill-hitl-watcher** to route each file by its `action` field
- Execute the corresponding skill (email, LinkedIn, social, Odoo)
- Update frontmatter with execution results
- Move completed files to `data/Done/`

### Step 8: CHECK SCHEDULED
Check for any scheduled tasks:
- Process `scheduled_task` type files in `data/Needs_Action/`
- Route to appropriate skill based on `task_type` field
- Check if weekly audit is due (handled in Step 13)

### Step 9: UPDATE DASHBOARD
Invoke **skill-dashboard-updater** to refresh `data/Dashboard.md`:
- Count files in each directory (Inbox, Needs_Action, Pending_Approval, Approved, Rejected, Done, Plans, Accounting, Briefings, Quarantine)
- Update recent activity log
- Update system health indicators

### Step 10: MOVE COMPLETED
Move all finished task files to `data/Done/`:
- Tasks with status `completed` or `done`
- Plans with all steps checked off
- Processed approval requests

### Step 11: LOG EVERYTHING
Invoke **skill-audit-logger** for every action taken this iteration:
- Enhanced JSON entries to `data/Logs/YYYY-MM-DD.json`
- Include: timestamp, severity, correlation_id, action, skill_used, file_affected, result, duration_ms, details
- Error entries include full error_trace

### Step 12: CHECK COMPLETION
Evaluate whether all queues are empty:
- `data/Needs_Action/` has no unprocessed files
- `data/Approved/` has no unprocessed files
- `data/Plans/` has no in_progress plans
- `data/Accounting/` has no pending tasks
- If all empty → proceed to Step 13
- If work remains → proceed to Step 13 anyway (audit check)

### Step 13: AUDIT CHECK (Gold)
Check if weekly audit is due:
- Compare current day/time with `CEO_BRIEF_DAY` and `CEO_BRIEF_HOUR`
- If due: invoke **skill-weekly-audit** → then **skill-ceo-briefing**
- If not due: skip

### Step 14: ERROR RECOVERY (Gold)
Check for any errors during this iteration:
- If errors occurred: invoke **skill-error-recovery** for each failure
- Retry transient errors, quarantine permanent failures
- Update error counters on dashboard

### Step 15: GENERATE DOCS (Gold)
Check if documentation update is needed:
- If significant changes detected (new skills, new MCP tools, architecture changes): invoke **skill-doc-generator**
- Typically runs end-of-session, not every iteration
- Skip if no changes

### Step 16: CONTINUE OR EXIT (Gold)
Enhanced completion check:
- If all queues empty AND no pending recoveries → output `TASK_COMPLETE` and exit
- If work remains → output `RALPH_CONTINUE` and return to Step 1

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
│  │  ├─ type: odoo_task
│  │  │  └─ Route to skill-odoo-mcp (invoice/payment/query)
│  │  │     └─ If creates external record → Approval required
│  │  │
│  │  ├─ type: social_post
│  │  │  └─ Route to skill-social-integrator → Approval required (always)
│  │  │
│  │  ├─ type: audit_task
│  │  │  └─ Route to skill-weekly-audit → skill-ceo-briefing
│  │  │
│  │  ├─ type: ceo_briefing
│  │  │  └─ Route to skill-ceo-briefing (reads latest audit)
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
   └─ Log warning → Move to Quarantine/ with error status (skill-error-recovery)
```

## Completion Signals
- `TASK_COMPLETE` — All queues empty, no pending work or recoveries. Agent exits cleanly.
- `RALPH_CONTINUE` — Work remains in at least one queue. Loop continues.
- `RALPH_AUDIT` — Weekly audit triggered. Run audit, then re-check completion.
- `RALPH_RECOVER` — Error detected. Enter recovery mode via skill-error-recovery.
