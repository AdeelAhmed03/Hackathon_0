# MCP Email Skill

## Purpose
Draft and send emails via MCP server. Draft only unless human-approved.

## Rules
- Draft only unless approved — sends require file in `data/Approved/`
- Use MCP config: `~/.config/claude-code/mcp.json` (email server)
- Format: Call MCP "email" with `{to, subject, body}`
- Log send result after every action

## Example MCP Call
```
invoke_mcp("email", {"action": "draft", "to": "client@example.com", "subject": "Follow-up", "body": "..."})
```

## Silver Spec
- One MCP for external (email); extend to social in Gold
- Supports: send_email, reply_email, forward_email

## Bronze Integration
- Use skill-approval-request-creator first to create HITL approval file
- Triggered by skill-hitl-watcher when approved file has email action
- Logged via skill-logger
- Dashboard updated via skill-dashboard-updater
