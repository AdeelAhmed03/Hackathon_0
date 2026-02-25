# Skill: MCP Email (Silver)

Purpose: Draft/send emails via MCP server.

Rules:
- Draft only unless approved
- Use MCP config: ~/.config/claude-code/mcp.json (email server)
- Format: Call MCP "email" with {to, subject, body}
- If send: Require file in /Approved/
- Log send result

Example MCP call (in Claude): invoke_mcp("email", {"action": "draft", "to": "client@example.com", ...})

Silver spec: One MCP for external (email); extend to social in Gold
Bronze integration: Use skill-approval-request-creator first
