# Skill: Social Integrator (Gold)

## Purpose
Handle FB/IG/X – post messages + generate summaries.

## Trigger
- Approved social media posts from `data/Approved/`
- Scheduled posting tasks from scheduler
- On-demand engagement summary requests

## Steps
1. For post: Draft in /Plans/, HITL approve, then MCP send
2. For summary: Poll via watcher/MCP, generate .md summary (e.g. engagement metrics)
3. Multiple MCPs: social-mcp-fb, social-mcp-ig, social-mcp-x
4. Sales gen: Posts like "New client success – join us!"

## Rules
- **All social posts ALWAYS require HITL approval** — no exceptions
- Route all social operations through `mcp-servers/social-mcp/social_mcp.py`
- Available tools: `post_to_facebook`, `get_fb_feed_summary`, `post_to_instagram`, `get_ig_media_summary`, `post_tweet`, `get_x_timeline_summary`
- Platform-specific formatting:
  - Facebook: No character limit, supports long-form
  - Instagram: Caption max 2200 chars, requires image_url for real posts
  - Twitter/X: Max 280 characters
- `FB_DRY_RUN=true` and `X_DRY_RUN=true` for testing
- Engagement summaries saved to `data/Briefings/` for CEO Briefing input

## Example MCP Call
```
invoke_mcp("social", {"name": "post_to_facebook", "arguments": {"message": "Exciting news!"}})
invoke_mcp("social", {"name": "get_x_timeline_summary", "arguments": {"limit": 10}})
```

## Gold Spec
- Integrate FB/IG/X; post + summary
- Unified cross-platform posting with per-platform content adaptation
- Engagement metrics feed into skill-weekly-audit and skill-ceo-briefing
- Content must comply with Company_Handbook Social Media Policy

## Prior Integration
- Use skill-linkedin-draft as base, extend to others
- Use skill-approval-request-creator for all posts (HITL mandatory)
- Triggered by skill-hitl-watcher when approved file has social action
- Logged via skill-audit-logger with platform-specific details
- Dashboard updated via skill-dashboard-updater
