# AI Employee Vault - Silver Tier

## Project Overview
This is a Personal AI Employee (Digital FTE) built for GIAIC Hackathon 0. It uses Claude Code as the reasoning engine and an Obsidian-compatible Markdown vault as the dashboard and memory system.

## Architecture
- **Brain**: Claude Code (Ralph Wiggum loop for autonomous task completion)
- **Memory/GUI**: Obsidian vault (local Markdown files in `data/`)
- **Senses**: Python watcher scripts in `watcher/`
- **Skills**: Agent skill definitions in `skills/`

## Directory Structure
```
data/Inbox/           - Drop-folder for new files
data/Needs_Action/    - Items awaiting agent processing
data/Pending_Approval/- Items requiring human approval
data/Approved/        - Human-approved items
data/Rejected/        - Human-rejected items
data/Done/            - Completed tasks
data/Plans/           - Multi-step execution plans (Silver)
data/Logs/            - JSON audit logs
```

## Key Files
- `data/Dashboard.md` - Real-time status overview (updated by agent)
- `Company_Handbook.md` - Rules of engagement and policies
- `agents/agent-core.md` - Core agent framework definition (13-step Silver loop)
- `watcher/gmail_watcher.py` - Polls Gmail for unread/important emails
- `watcher/needs_action_watcher.py` - Filesystem watcher that triggers Claude agent
- `watcher/hitl_watcher.py` - Watches data/Approved/ for human-approved files (Silver)
- `watcher/scheduler.py` - Time-based scheduler for recurring tasks (Silver)

## Conventions
- All task files use YAML frontmatter with `type`, `status`, `priority` fields
- Files move between directories to indicate status changes
- Never delete files — always move to `data/Done/`
- Sensitive actions require approval (file moved to `data/Pending_Approval/`)
- Plans use `PLAN_{YYYYMMDD_HHMM}_{description}.md` naming convention
- Scheduled tasks use `SCHEDULED_{task_type}_{YYYYMMDD}.md` naming convention
- HITL: Only humans move files to Approved/ — agent never self-approves
- Logs are JSON format in `data/Logs/YYYY-MM-DD.json`

## Agent Skills

### Bronze Skills (1-5)
1. **File System Access** - Read/write/list/move files within project
2. **Needs Action Processor** - Parse and route new task files
3. **Dashboard Updater** - Update counts and activity in Dashboard.md
4. **Approval Request Creator** - Generate approval files for sensitive actions
5. **Logger** - Append structured JSON log entries

### Silver Skills (6-10)
6. **Plan Creator** - Create multi-step execution plans in data/Plans/
7. **LinkedIn Draft** - Generate professional LinkedIn post drafts (150-300 words)
8. **MCP Email** - Send email via SMTP (only from Approved/, always HITL)
9. **HITL Watcher** - Route approved files to correct execution skill by action field
10. **Scheduler** - Create scheduled task files via time-based triggers

## Security
- Credentials stored in `.env` (never committed)
- `.gitignore` excludes all secrets
- Human-in-the-loop for sensitive actions
- DRY_RUN mode available for safe testing
