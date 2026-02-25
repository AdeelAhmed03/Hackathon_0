# AI Employee Vault - Architecture

## System Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          EXTERNAL SOURCES                                   │
│  Gmail API │ Odoo (JSON-RPC) │ Facebook │ Instagram │ X/Twitter │ LinkedIn │
└─────────────────────┬─────────────────────┬─────────────────────────────────┘
                      │                     │
                      ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PERCEPTION LAYER (Watchers)                              │
│  gmail_watcher.py  │ hitl_watcher.py  │ scheduler.py  │ needs_action_watcher │
│  linkedin_watcher.py │ facebook_watcher.py │ instagram_watcher.py │ x_watcher.py │
└─────────────────────┬───────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                 OBSIDIAN VAULT (Local Markdown)                            │
│  ┌──────────────┐ ┌─────────────────┐ ┌──────────────┐ ┌─────────────────┐ │
│  │   Inbox/     │ │ Needs_Action/   │ │ Approved/    │ │ Pending_Approval│ │
│  │              │ │                 │ │              │ │                 │ │
│  │ New files    │ │ Pending tasks   │ │ Human        │ │ Awaiting        │ │
│  │ drop here    │ │ for processing  │ │ approvals    │ │ approval        │ │
│  └──────────────┘ └─────────────────┘ └──────────────┘ └─────────────────┘ │
│  ┌──────────────┐ ┌─────────────────┐ ┌──────────────┐ ┌─────────────────┐ │
│  │   Done/      │ │  Plans/         │ │ Quarantine/  │ │ In_Progress/    │ │
│  │              │ │                 │ │              │ │                 │ │
│  │ Completed    │ │ Multi-step      │ │ Error        │ │ Claimed by      │ │
│  │ tasks        │ │ execution plans │ │ recovery     │ │ agents          │ │
│  └──────────────┘ └─────────────────┘ └──────────────┘ └─────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────┬───────────────────────────────────────────────────────┐
│                REASONING ENGINE (Claude Code)                               │
│  agent-autonomous-employee.md  │  agent-functional-assistant.md            │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │ 1. READ_CONTEXT → 2. READ_DASHBOARD → 3. SCAN_NEEDS_ACTION             │ │
│  │ → 4. CREATE_PLANS → 5. EXECUTE_SKILLS → 6. HANDLE_SENSITIVE            │ │
│  │ → 7. PROCESS_APPROVED → 8. CHECK_SCHEDULED → 9. UPDATE_DASHBOARD       │ │
│  │ → 10. MOVE_COMPLETED → 11. LOG_EVERYTHING → 12. CHECK_COMPLETION       │ │
│  │ → 13. AUDIT_CHECK → 14. ERROR_RECOVERY → 15. GENERATE_DOCS             │ │
│  │ → 16. CONTINUE_OR_EXIT                                                  │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────┬───────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   ACTION LAYER (MCP Servers)                                │
│  ┌──────────────┐ ┌─────────────────┐ ┌─────────────────┐                   │
│  │ email-mcp    │ │  odoo-mcp       │ │   social-mcp    │                   │
│  │  (Node.js)   │ │   (Python)      │ │   (Python)      │                   │
│  │  SMTP/IMAP   │ │  XML-RPC/JSON   │ │ FB/IG/X APIs    │                   │
│  └──────────────┘ └─────────────────┘ └─────────────────┘                   │
└─────────────────────────────────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                MONITORING & RECOVERY                                        │
│  orchestrator.py (central supervisor)  │  watchdog.py (process monitor)    │
│  weekly_audit + CEO_briefing          │  error_recovery.py                 │
│  scheduler.py (cron-like jobs)        │  retry_handler.py                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Technology Stack

### Core Components
- **Reasoning Engine**: Claude Code (via `/ralph-loop` commands)
- **Knowledge Base**: Local Obsidian-compatible Markdown vault (`data/` folder)
- **File-based State Machine**: Directories as workflow states (Inbox → Needs_Action → Pending_Approval → Done)

### Watchers (Perception Layer)
- **gmail_watcher.py**: Polls Gmail for unread/important emails
- **needs_action_watcher.py**: Detects new files in Needs_Action/ and triggers Ralph loop
- **hitl_watcher.py**: Processes human-approved files in Approved/
- **scheduler.py**: Time-based triggers for recurring tasks
- **linkedin_watcher.py**: Monitors LinkedIn activity and creates tasks
- **facebook_watcher.py**: Polls Facebook for new posts/engagement
- **instagram_watcher.py**: Polls Instagram for new posts/engagement
- **x_watcher.py**: Polls Twitter/X for new posts/engagement

### MCP Servers (Action Layer)
- **email-mcp**: Node.js server for SMTP/IMAP operations via JSON-RPC
- **odoo-mcp**: Python server for Odoo accounting via XML-RPC/JSON-RPC
- **social-mcp**: Python server for Facebook/Instagram/X APIs via JSON-RPC

### Infrastructure (Monitoring & Recovery)
- **orchestrator.py**: Central supervisor for all watchers and cron jobs
- **watchdog.py**: Process health monitoring with restart capabilities
- **retry_handler.py**: Error classification and retry strategies
- **error_recovery.py**: Quarantine, retry, and escalation mechanisms

### Data Flow
1. **Input**: External sources trigger file creation in appropriate directories
2. **Processing**: Watchers detect files and trigger Claude agents with specific prompts
3. **Action**: Agents execute skills via MCP servers or direct file manipulation
4. **Completion**: Files move through workflow states based on processing results
5. **Monitoring**: System logs structured JSON to `data/Logs/` for audit trails

### Security & Reliability
- Human-in-the-Loop (HITL) for sensitive actions
- DRY_RUN mode for safe testing of all integrations
- Comprehensive audit logging with Spec 6.3 JSON format
- Process supervision with automatic restart on failures
- Error recovery with quarantine and escalation mechanisms