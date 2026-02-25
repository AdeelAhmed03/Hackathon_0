# Skill: Scheduler (Silver)

Purpose: Basic scheduling via cron simulation.

Rules:
- For daily/weekly tasks (e.g. dashboard refresh, LinkedIn draft)
- Check current time vs schedule (e.g. if now.hour == 8 → run)
- Simulate cron: In Ralph loop, check every 5 min
- Tasks: Daily briefing stub, weekly audit prep

Example: if datetime.now().weekday() == 0 → generate CEO brief draft

Silver spec: Use cron/Task Scheduler externally; here simulate in agent
Bronze integration: Update Dashboard after scheduled run
