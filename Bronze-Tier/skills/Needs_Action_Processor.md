# Skill: Needs_Action Processor (Bronze)

**Trigger:** Any .md in data/Needs_Action/

**Exact steps:**
1. Read file
2. Parse type from frontmatter (email, file_drop, etc.)
3. Add ## Plan section with checkboxes
4. If needs approval → call skill-approval-request-creator
5. Else → mark complete, move to data/Done/
6. Call skill-dashboard-updater

**Bronze limitation:** only handle watcher-generated files; else → create UNCERTAIN_ file

**Process Flow:**
- Monitor data/Needs_Action/ directory for new files
- When a file is detected, read its content and frontmatter
- Identify the file type from frontmatter (email, file_drop, etc.)
- Generate a plan section with checkboxes for required actions
- Evaluate if the request requires approval based on complexity/risk
- If approval needed, create a request using skill-approval-request-creator and move to Pending_Approval
- If no approval needed, mark as complete and move to data/Done/
- Update the dashboard statistics using skill-dashboard-updater
- Log all actions taken

**Approval Criteria:**
- Requests involving external communication
- Requests with financial implications
- Requests affecting security settings
- Requests marked as high-risk

**Uncertainty Handling:**
- If file type is unrecognized
- If request falls outside defined parameters
- If conflicting instructions are found
- Create UNCERTAIN_[filename].md in data/Needs_Action/ and halt processing