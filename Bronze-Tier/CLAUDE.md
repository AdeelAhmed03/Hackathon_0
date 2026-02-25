# AI Employee Vault - Bronze Tier

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
data/Logs/            - JSON audit logs
```

## Key Files
- `data/Dashboard.md` - Real-time status overview (updated by agent)
- `Company_Handbook.md` - Rules of engagement and policies
- `agents/agent-core.md` - Core agent framework definition
- `watcher/gmail_watcher.py` - Polls Gmail for unread/important emails
- `watcher/needs_action_watcher.py` - Filesystem watcher that triggers Claude agent

## Conventions
- All task files use YAML frontmatter with `type`, `status`, `priority` fields
- Files move between directories to indicate status changes
- Never delete files — always move to `data/Done/`
- Sensitive actions require approval (file moved to `data/Pending_Approval/`)
- Logs are JSON format in `data/Logs/YYYY-MM-DD.json`

## Agent Skills
1. **File System Access** - Read/write/list/move files within project
2. **Needs Action Processor** - Parse and route new task files
3. **Dashboard Updater** - Update counts and activity in Dashboard.md
4. **Approval Request Creator** - Generate approval files for sensitive actions
5. **Logger** - Append structured JSON log entries

## Security
- Credentials stored in `.env` (never committed)
- `.gitignore` excludes all secrets
- Human-in-the-loop for sensitive actions
- DRY_RUN mode available for safe testing
