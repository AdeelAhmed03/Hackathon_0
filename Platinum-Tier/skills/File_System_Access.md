# Skill: File System Access (Bronze – VS Code)

**Purpose:** Read/write/list files using Claude Code's file system tools.

**Rules:**
- Prefer relative paths from project root (e.g. data/Needs_Action/EMAIL_123.md)
- Always read Company_Handbook.md + data/Dashboard.md first when starting
- Never delete — move to data/Done/
- When writing, add frontmatter: processed_by: Agent_Core, timestamp: ISO

**Capabilities:**
- Read files from any directory in the project
- Write files to designated data directories
- Move files between status directories
- List directory contents
- Check file existence

**Security Restrictions:**
- Cannot access files outside the project directory
- Cannot execute system commands
- Cannot modify skill or agent definition files
- All operations logged for audit purposes

**Usage Examples:**
```
read_file: data/Needs_Action/request.md
write_file: data/Done/completed_request.md
move_file: data/Needs_Action/request.md data/Pending_Approval/
list_dir: data/Needs_Action/
```

**Frontmatter Template:**
```yaml
---
processed_by: Agent_Core
timestamp: 2026-02-13T10:30:00Z
original_status: Needs_Action
---
```