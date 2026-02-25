# Skill: LinkedIn Draft (Silver)

Purpose: Automatically generate sales-oriented LinkedIn post drafts.

Trigger: Scheduled or on business event (e.g. new client email)

Steps:
1. Read Company_Handbook.md for branding/tone
2. Generate post: "Exciting update: [business highlight] – Let's connect for opportunities! #Sales #AI"
3. Write to data/Plans/LINKEDIN_DRAFT_{date}.md
4. Add to Dashboard: "New LinkedIn draft ready for approval"
5. Always require HITL: Create approval file with post text

Silver spec: Generate to boost sales (e.g. reference revenue, products)
Bronze integration: Use skill-logger after
