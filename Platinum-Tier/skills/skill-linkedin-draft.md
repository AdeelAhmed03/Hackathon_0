# LinkedIn Draft Skill

## Purpose
Automatically generate sales-oriented LinkedIn post drafts to boost visibility and revenue.

## Trigger
- Scheduled daily via skill-scheduler
- On business event (e.g. new client email detected by gmail_watcher)

## Steps
1. Read Company_Handbook.md for branding/tone
2. Generate post: "Exciting update: [business highlight] – Let's connect for opportunities! #Sales #AI"
3. Write to `data/Plans/LINKEDIN_DRAFT_{date}.md`
4. Add to Dashboard: "New LinkedIn draft ready for approval"
5. Always require HITL: Create approval file with post text

## Silver Spec
- Generate to boost sales (e.g. reference revenue, products)
- Post types: update, announcement, thought_leadership, milestone

## Configuration
- Uses env vars: LINKEDIN_ACCESS_TOKEN, LINKEDIN_PERSON_URN, LINKEDIN_POST_SCHEDULE
- LINKEDIN_DRY_RUN=true prevents actual API calls

## Bronze Integration
- Use skill-logger after draft creation and posting
- Use skill-dashboard-updater to reflect new draft status
- Use skill-approval-request-creator for HITL approval file
