# Ralph Loop - Platinum Tier Multi-Agent System

## Overview
The Platinum Tier introduces a distributed multi-agent system with separate Cloud and Local Executive agents. Each agent has specialized responsibilities and follows a distinct loop while coordinating via the vault filesystem and A2A messaging.

## Cloud Executive Agent Loop

### Core Loop (Ralph Wiggum - Cloud Executive)
```
1. Read Company_Handbook.md (Platinum policies)
2. Git sync pull - receive updates from local
3. Monitor /Needs_Action/cloud/ (email, social, triage)
4. Claim-by-move to /In_Progress/cloud/ (prevent double-work)
5. Triage/Draft:
   - Email → draft reply in /Plans/cloud/
   - Social → draft post in /Plans/cloud/
   - Odoo → draft action in /Plans/cloud/
6. Write approval request to /Pending_Approval/local/
7. Write update to /Updates/ for dashboard merge
8. Move to /Done/cloud/
9. Git sync push - send to local
10. A2A: Send draft_ready notification if enabled
11. On done: Log, audit trail, return to step 2
```

### Responsibilities
- **Email Triage**: Process incoming emails, categorize priority, generate draft responses
- **Draft Generation**: Create drafts for social posts, accounting actions, email replies
- **24/7 Operation**: Cloud VM handles always-on processing
- **Git Synchronization**: Keep systems in sync via Git
- **Health Monitoring**: Monitor cloud system health
- **Dashboard Updates**: Write to `/Updates/` for local merge

### Platinum Rules
- **Draft-Only**: Cloud agent NEVER executes sends/posts/payments
- **Work-Zone Separation**: Cloud handles triage/drafts only
- **A2A Phase 2**: Optional direct messaging (if enabled) logged to vault
- **Delegation**: Write to local queues when action requires local execution
- **Claim-by-Move**: Move files to `/In_Progress/cloud/` to claim ownership

---

## Local Executive Agent Loop

### Core Loop (Ralph Wiggum - Local Executive)
```
1. Git sync pull - receive cloud drafts/updates
2. Merge /Updates/ → Dashboard.md (single-writer principle)
3. Monitor /Pending_Approval/local/ for approval requests
4. Human HITL: Wait for file moves to /Approved/
5. Claim-by-move approved files to /In_Progress/local/
6. Execute via MCP (send/post/pay using local secrets)
7. Write execution result to /Updates/
8. Move to /Done/local/
9. Git sync push - send completed work to cloud
10. A2A: Send approval_complete notification if enabled
11. On done: Log, audit trail, return to step 1
```

### Responsibilities
- **Approvals**: Handle human approval decisions
- **Execution**: Send emails, post to social media, pay invoices
- **Sensitive Operations**: WhatsApp, banking, payments (local secrets only)
- **Dashboard Management**: Single-writer merge of cloud updates
- **Git Synchronization**: Process cloud changes, push local work

### Platinum Rules
- **Execution-Only**: Local agent executes approved actions only
- **Secrets Protection**: All local credentials, never sync to cloud
- **Work-Zone Separation**: Local handles approvals/executions only
- **A2A Phase 2**: Optional direct messaging (if enabled) logged to vault
- **Claim-by-Move**: Move files to `/In_Progress/local/` to claim ownership

---

## Multi-Agent Coordination

### Claim-by-Move Protocol
```
Cloud:  /Needs_Action/cloud/ → /In_Progress/cloud/ → /Done/cloud/
Local:  /Pending_Approval/   → /In_Progress/local/ → /Done/local/
```
- Files moved to progress directories to prevent double-processing
- Thread-safe via filesystem atomic moves
- Agents only process files in their progress directory

### A2A Messaging (Phase 2 - Optional)
- **draft_ready**: Cloud → Local (draft created, ready for approval)
- **approval_complete**: Local → Cloud (approval decision made)
- **health_ping**: Bidirectional health checks
- **sync_request**: Request immediate Git sync
- **dashboard_update**: Cloud metrics for dashboard

### File-Based Handoff Process
```
Email arrives → /Needs_Action/cloud/ (Cloud Executive owns)
              ↓ (Cloud triage/draft)
Draft created → /Plans/cloud/ + Approval request → /Pending_Approval/local/
              ↓ (Git sync)
Human approves → /Approved/ (Local Executive owns)
              ↓ (Local execution)
Action executed → MCP call → /Updates/ for dashboard merge
              ↓ (Final sync)
Completed → /Done/local/ → Git for audit trail
```

### Sync Protocol
- **Only .md files**: Secrets excluded from Git sync
- **Cloud-to-Local**: Drafts, updates, approvals
- **Local-to-Cloud**: Executions, completed tasks, metrics
- **Conflict Resolution**: Local changes favored for execution decisions

---

## Advanced Multi-Agent Coordination

### Coordination Mechanisms

1. **File-Based State Machine**
   - Directories represent workflow states (Needs_Action → In_Progress → Done)
   - Atomic file moves provide thread-safe ownership claims
   - Zone-specific directories prevent cross-agent conflicts

2. **A2A Direct Messaging** (Optional)
   - Socket-based low-latency communication
   - File fallback when socket unavailable
   - Dual audit logging (JSON + vault .md files)
   - Feature-flagged via `A2A_PHASE2_ENABLED` environment variable

3. **Git Synchronization**
   - Periodic sync between cloud and local vaults
   - Data/ directory only (no secrets)
   - Conflict resolution via Git merge strategies

4. **Health Monitoring**
   - Cross-zone heartbeat checking
   - Cloud VM monitors local status
   - Alert escalation to appropriate zone

### Error Handling & Recovery

1. **Cloud Offline Scenario**
   - Local continues processing approved tasks
   - Draft queue builds in `/Plans/cloud/`
   - Resumes normal operation on cloud recovery

2. **Local Offline Scenario**
   - Cloud continues triage/draft operations
   - Approval queue builds in `/Pending_Approval/local/`
   - Resumes normal operation on local recovery

3. **Sync Conflicts**
   - Git merge strategies handle conflicts
   - Local execution decisions take precedence
   - Quarantine for unrecoverable errors

### Performance Considerations

1. **Scalability Patterns**
   - Claim-by-move prevents resource contention
   - Zone-specific processing reduces cross-agent coordination
   - A2A messaging replaces file handoffs when available

2. **Reliability Features**
   - File-based fallback ensures operation with A2A failure
   - Git sync provides backup coordination mechanism
   - Audit logging captures all coordination events