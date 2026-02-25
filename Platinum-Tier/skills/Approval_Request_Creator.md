# Skill: Approval Request Creator

**Purpose:** For any external/sensitive action that requires human approval.

**Process:**
Create file in data/Pending_Approval/NAME.md with the following template:

```markdown
---
type: approval_request
action: send_email | file_access | data_modification | other
target: [recipient/email/file affected]
reason: [brief explanation of why this action is needed]
status: pending
created: 2026-02-13T10:30:00Z
approved_by: 
rejected_by: 
completion_date: 
---

## To Approve
Move this file to data/Approved/

## To Reject
Move this file to data/Rejected/

## Action Details
[Detailed description of the action to be approved]
[Any additional context or information needed for decision]

## Potential Impact
[Brief overview of what happens if this action is approved/rejected]
```

**Approval Workflow:**
1. Human reviewer examines the request details
2. If approved, move file to data/Approved/ directory
3. If rejected, move file to data/Rejected/ directory
4. The system monitors these directories and acts accordingly

**Approval Triggers:**
- External communications (emails, messages)
- Access to sensitive data
- Modifications to critical systems
- Financial transactions
- Any action marked as high-risk in Company_Handbook.md

**Naming Convention:**
- Use descriptive names for approval files: APPROVAL_[ACTION_TYPE]_[UNIQUE_ID].md
- Include date and brief description in filename
- Follow format: YYYYMMDD_HHMM_ACTION_DESCRIPTION.md

**Logging:**
- Record creation of approval request in data/Logs/
- Include timestamp and requesting component in log entry
- Update dashboard via skill-dashboard-updater after creation