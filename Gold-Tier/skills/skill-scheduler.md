# Scheduler Skill

## Purpose
Basic scheduling via cron simulation. Checks time-based triggers in the Ralph loop.

## Rules
- For daily/weekly tasks (e.g. dashboard refresh, LinkedIn draft)
- Check current time vs schedule (e.g. `if now.hour == 8 → run`)
- Simulate cron: In Ralph loop, check every 5 min
- Tasks: Daily briefing stub, weekly audit prep

## Example
```python
if datetime.now().weekday() == 0:  # Monday
    # → generate CEO brief draft
```

## Silver Spec
- Use cron/Task Scheduler externally; here simulate in agent
- Deduplication via `data/Logs/scheduler_state.json` to prevent double triggers
- Creates `SCHEDULED_{task_type}_{date}.md` in `data/Needs_Action/`

## Bronze Integration
- Update Dashboard after scheduled run via skill-dashboard-updater
- Created tasks flow through needs_action_watcher.py → agent-core.md
- Logged via skill-logger

## Implementation
- Standalone: `watcher/scheduler.py` (time-based loop)
- In-agent: agent-core.md step 8 checks scheduled tasks each iteration
