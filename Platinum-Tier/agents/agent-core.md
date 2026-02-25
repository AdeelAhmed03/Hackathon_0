# Agent Core Framework — Platinum Tier

## Purpose
The core agent system manages all employee vault operations through a file-based memory system using the Ralph Wiggum autonomous loop pattern. Platinum Tier extends Gold with 24/7 distributed cloud/local operation, work-zone separation (cloud handles drafts/triage, local handles execution/approvals), Git-synced vault, and specialized Cloud Executive agent. All AI functionality is implemented as Agent Skills.

## Architecture
- **Cloud Agent**: 24/7 Cloud Executive specializing in triage/drafts (email/social/Odoo actions as drafts)
- **Local Agent**: Handles approvals, WhatsApp, banking, and actual sends/posts/payments
- Monitors cloud-specific queues: `data/Needs_Action/cloud/`, `data/In_Progress/cloud/`, `data/Done/cloud/`
- Processes cloud requests according to Platinum Tier policies (Bronze + Silver + Gold + Platinum)
- Creates multi-step plans for complex tasks in `data/Plans/cloud/`
- Generates drafts with mandatory approval workflow via `/Pending_Approval/local/`
- Interfaces with MCP servers for external operations (draft-only mode)
- Performs Git synchronization with local system for distributed operation
- Monitors health and alerts local on cloud service issues
- Handles A2A Phase 2 direct messaging (when enabled) with full audit logging
- Maintains comprehensive audit logs in data/Logs
- Updates dashboard via `/Updates/` for local merge

## File-Based Memory System
The agent uses the file system as its memory:
- Each request is a file in a specific directory
- Directory location indicates request status and processing zone (cloud vs local)
- File content contains request details and metadata (YAML frontmatter)
- Agent reads/writes files to process requests and update state
- Plans track multi-step execution progress
- Quarantine holds permanently failed tasks
- Cloud/local separation maintains work-zone boundaries

## Available Skills (28 Total)

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

### Platinum Skills (19-28)
#### Cloud Executive Skills (19-23)
19. **skill-cloud-triage** — Triage incoming cloud tasks and route appropriately
20. **skill-draft-generator** — Generate drafts for email replies, social posts, Odoo actions
21. **skill-sync-handler** — Handle Git synchronization between cloud and local
22. **skill-health-monitor** — Monitor cloud agent health and alert local
23. **skill-a2a-upgrade** — Handle optional A2A Phase 2 direct messages

#### Local Executive Skills (24-28)
24. **skill-approval-executor** — Process approval requests and execute actions using local MCP and credentials
25. **skill-merge-updater** — Merge cloud updates from /Updates/ into local Dashboard.md
26. **skill-sync-handler** — Handle Git synchronization operations (pull/push) for local system
27. **skill-health-monitor** — Monitor local system health and performance
28. **skill-a2a-upgrade** — Handle optional A2A Phase 2 direct messages for local system

## Platinum Ralph Wiggum Loop (20 Steps)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                RALPH WIGGUM LOOP — PLATINUM                                │
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐                                      │
│  │ 1. READ      │───▶│ 2. READ      │                                      │
│  │    CONTEXT    │    │    DASHBOARD  │                                      │
│  └──────────────┘    └──────┬───────┘                                      │
│                             │                                               │
│                             ▼                                               │
│                    ┌──────────────┐                                        │
│                    │ 3. CLAIM     │                                        │
│                    │ CLOUD TASKS  │                                        │
│                    └──────┬───────┘                                        │
│                           │                                                 │
│                           ▼                                                 │
│  ┌──────────────┐    ┌──────────────┐                                      │
│  │ 4. TRIAGE    │───▶│ 5. CATEGORIZE│                                      │
│  │    CLOUD     │    │    TASKS     │                                      │
│  └──────────────┘    └──────┬───────┘                                      │
│                             │                                               │
│                             ▼                                               │
│  ┌──────────────┐    ┌──────────────┐                                      │
│  │ 6. DRAFT     │───▶│ 7. APPROVAL  │                                      │
│  │ GENERATION   │    │   REQUEST    │                                      │
│  └──────────────┘    └──────┬───────┘                                      │
│                             │                                               │
│                             ▼                                               │
│  ┌──────────────┐    ┌──────────────┐                                      │
│  │ 8. LOCAL     │───▶│ 9. PROCESS   │                                      │
│  │  DELEGATION  │    │   APPROVED   │                                      │
│  └──────────────┘    └──────┬───────┘                                      │
│                             │                                               │
│                             ▼                                               │
│  ┌──────────────┐    ┌──────────────┐                                      │
│  │ 10. UPDATE   │───▶│ 11. MOVE     │                                      │
│  │   DASHBOARD  │    │ COMPLETED    │                                      │
│  └──────────────┘    └──────┬───────┘                                      │
│                             │                                               │
│                             ▼                                               │
│  ┌──────────────┐    ┌──────────────┐                                      │
│  │ 12. LOG      │───▶│ 13. CHECK    │                                      │
│  │  EVERYTHING  │    │ COMPLETION   │                                      │
│  └──────────────┘    └──────┬───────┘                                      │
│                             │                                               │
│                             ▼                                               │
│  ┌──────────────┐    ┌──────────────┐                                      │
│  │ 14. SYNC     │───▶│ 15. HEALTH   │                                      │
│  │   GIT        │    │   MONITOR    │                                      │
│  └──────────────┘    └──────┬───────┘                                      │
│                             │                                               │
│                             ▼                                               │
│  ┌──────────────┐    ┌──────────────┐                                      │
│  │ 16. AUDIT    │───▶│ 17. ERROR    │                                      │
│  │    CHECK     │    │    RECOVERY  │                                      │
│  └──────────────┘    └──────┬───────┘                                      │
│                             │                                               │
│                             ▼                                               │
│  ┌──────────────┐    ┌──────────────┐                                      │
│  │ 18. A2A      │───▶│ 19. GENERATE │                                      │
│  │   PHASE 2    │    │    DOCS      │                                      │
│  └──────────────┘    └──────┬───────┘                                      │
│                             │                                               │
│                             ▼                                               │
│  ┌──────────────┐    ┌──────────────┐                                      │
│  │ 20. CONTINUE │───▶│              │                                      │
│  │   OR EXIT    │    │              │                                      │
│  └──────────────┘    └──────────────┘                                      │
│                      ┌──────┬──────┐                                        │
│                      │      │      │                                        │
│                      ▼      ▼      ▼                                        │
│               ┌──────────┐┌─────────┐ ┌─────────────┐                      │
│               │TASK_     ││CLOUD_   │ │ RALPH_      │                      │
│               │COMPLETE  ││TRIAGE   │ │ CONTINUE    │──┐                   │
│               │(exit)    ││(local)  │ └─────────────┘  │                   │
│               └──────────┘└─────────┘        ▲         │                   │
│                                              └─────────┘                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Step 1: READ CONTEXT (Platinum)
Read `Company_Handbook.md` to load all policies, rules, and constraints (Bronze + Silver + Gold + Platinum). Focus on work-zone separation, cloud policies, and sync protocols.

### Step 2: READ DASHBOARD (Platinum)
Read `data/Dashboard.md` (synchronized via Git) to understand current system state — counts, recent activity, health. Process any updates from `/Updates/` folder.

### Step 3: CLAIM CLOUD TASKS (Platinum)
Scan `data/Needs_Action/cloud/` for new cloud-specific tasks. Move to `data/In_Progress/cloud/` to claim ownership (claim-by-move pattern). Ignore tasks already claimed by other processes.

### Step 4: TRIAGE CLOUD TASKS (Platinum)
Invoke **skill-cloud-triage** to categorize and prioritize cloud tasks according to Platinum policies. Determine appropriate handling based on task type and business rules.

### Step 5: CATEGORIZE TASKS (Platinum)
Classify tasks by type (email, social, accounting, health, sync) and priority level (critical, high, normal). Prepare for appropriate processing workflow.

### Step 6: DRAFT GENERATION (Platinum)
Invoke **skill-draft-generator** to create drafts for:
- Email replies in `data/Plans/cloud/`
- Social media posts as draft content
- Odoo actions as draft invoices/payments
- All in draft-only mode per Platinum policies

### Step 7: APPROVAL REQUEST (Platinum)
For any action requiring execution, create approval request in `data/Pending_Approval/local/` via **skill-approval-request-creator**. Cloud agent cannot execute directly.

### Step 8: LOCAL DELEGATION (Platinum)
Write files to local directories when action requires local execution. This includes approval requests, WhatsApp tasks, banking operations, and actual sends/posts/payments.

### Step 9: PROCESS APPROVED (Platinum)
Check for approved items that originated from cloud requests (via sync from local). Execute cloud-side portions of approved actions that were initiated by cloud agent.

### Step 10: UPDATE DASHBOARD (Platinum)
Invoke **skill-dashboard-updater** to refresh cloud-specific metrics and update via `/Updates/cloud_{id}.md` for local merge.

### Step 11: MOVE COMPLETED (Platinum)
Move finished cloud tasks to `data/Done/cloud/` to indicate completion. Update cloud-specific completion metrics.

### Step 12: LOG EVERYTHING (Platinum)
Invoke **skill-audit-logger** for every cloud-specific action with enhanced cloud operation details including sync status, health metrics, and distributed operation tracking.

### Step 13: CHECK COMPLETION (Platinum)
Evaluate whether cloud-specific queues are empty:
- `data/Needs_Action/cloud/` has no unprocessed files
- `data/In_Progress/cloud/` has no active files
- No pending cloud-specific tasks
- If all cloud queues empty, proceed to sync

### Step 14: SYNC GIT (Platinum)
Invoke **skill-sync-handler** to synchronize cloud vault with local system:
- Push cloud-generated files to remote repository
- Pull any local updates to cloud system
- Process `/Updates/` files from local system
- Handle conflicts per Platinum Tier policies

### Step 15: HEALTH MONITOR (Platinum)
Invoke **skill-health-monitor** to check cloud service status:
- System resources (CPU, memory, disk, network)
- MCP server availability
- Performance metrics
- Alert local system if health thresholds exceeded

### Step 16: AUDIT CHECK (Platinum)
Check if weekly audit is due (Gold functionality) but specifically for cloud operations and performance metrics.

### Step 17: ERROR RECOVERY (Platinum)
Check for any cloud-specific errors during this iteration:
- If cloud errors occurred: invoke **skill-error-recovery** for each failure
- Retry cloud-specific transient errors
- Quarantine cloud tasks per Platinum policies
- Alert local on persistent cloud issues

### Step 18: A2A PHASE 2 (Platinum)
Check for A2A Phase 2 messages (if enabled) and process via **skill-a2a-upgrade**. Log all interactions for audit compliance.

### Step 19: GENERATE DOCS (Platinum)
Check if cloud-specific documentation updates are needed (system changes, new patterns, health reports).

### Step 20: CONTINUE OR EXIT (Platinum)
Platinum completion check:
- If all cloud queues empty AND no pending cloud recoveries AND sync completed → output `TASK_COMPLETE` and exit
- If cloud work remains → output `CLOUD_TRIAGE` and return to Step 1 for local processing OR output `RALPH_CONTINUE` for continued cloud operation

## Decision Tree

```
New cloud task file detected in data/Needs_Action/cloud/
│
├─ Has YAML frontmatter?
│  ├─ YES → Parse type and action fields
│  │  │
│  │  ├─ type: email_triage
│  │  │  └─ Route to skill-cloud-triage → skill-draft-generator → approval request
│  │  │
│  │  ├─ type: social_triage
│  │  │  └─ Route to skill-cloud-triage → skill-draft-generator → approval request
│  │  │
│  │  ├─ type: accounting_draft
│  │  │  └─ Route to skill-cloud-triage → skill-draft-generator (Odoo draft) → approval request
│  │  │
│  │  ├─ type: cloud_health
│  │  │  └─ Route to skill-health-monitor
│  │  │
│  │  ├─ type: git_sync
│  │  │  └─ Route to skill-sync-handler
│  │  │
│  │  ├─ type: a2a_message (if enabled)
│  │  │  └─ Route to skill-a2a-upgrade
│  │  │
│  │  └─ type: other/unknown
│  │     └─ Route to skill-cloud-triage for categorization
│  │
│  └─ NO → skill-cloud-triage (attempt to parse and categorize)
│
└─ File is empty or invalid
   └─ Log warning → Move to Quarantine/ with error status (skill-error-recovery)
```

## Completion Signals
- `TASK_COMPLETE` — All cloud queues empty, no pending work or recoveries. Cloud agent exits cleanly.
- `CLOUD_TRIAGE` — Cloud tasks processed but local interaction needed (sync/approval). Wait for local action.
- `RALPH_CONTINUE` — Cloud work remains in at least one queue. Continue cloud operation.
- `RALPH_AUDIT` — Cloud audit triggered. Run audit, then re-check completion.
- `RALPH_RECOVER` — Cloud error detected. Enter recovery mode via skill-error-recovery.
- `CLOUD_HEALTH_ALERT` — Critical cloud health issue. Alert local system immediately.
