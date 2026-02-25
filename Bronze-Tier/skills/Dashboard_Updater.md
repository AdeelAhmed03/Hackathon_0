# Skill: Dashboard Updater

**Actions:**
- Count .md files in data/Needs_Action/ and data/Pending_Approval/
- Append line to Recent Activity: "- YYYY-MM-DD HH:MM | action description"
- Keep only last 10 activity lines
- Update Last updated field

**Detailed Process:**
1. Read data/Dashboard.md
2. Count all .md files in data/Needs_Action/ directory
3. Count all .md files in data/Pending_Approval/ directory
4. Update the status counts in the dashboard
5. Add new activity entry to Recent Activity section in format: "- YYYY-MM-DD HH:MM | action description"
6. Maintain only the last 10 activity lines, removing older entries
7. Update the "Last updated" field with current timestamp
8. Write the updated dashboard back to data/Dashboard.md

**Activity Entry Examples:**
- "- 2026-02-13 10:30 | Processed email request from John Doe"
- "- 2026-02-13 09:45 | File approval request moved to Pending_Approval"
- "- 2026-02-13 08:22 | New file drop request received"

**Status Count Updates:**
- Items in data/Needs_Action/: [count]
- Items in data/Pending_Approval/: [count]

**Timestamp Format:**
- Use ISO 8601 format: YYYY-MM-DD HH:MM (24-hour format)
- Example: 2026-02-13 14:30

**Preservation:**
- Maintain all other dashboard content unchanged
- Only update the specific sections mentioned above
- Preserve formatting and other sections of the dashboard