# skill-approval-executor

## Purpose
Process approval requests and execute the approved actions using local MCP servers and credentials. This skill handles the execution of cloud-generated drafts after human approval.

## Trigger
When files are moved to `/Approved/` directory from `/Pending_Approval/local/`

## Input
- Approval request file with YAML frontmatter containing action details
- Action type (email, social, payment, etc.)
- Action parameters and content
- Human approval status and any modifications

## Process
1. Parse approval request file and extract action details
2. Validate approval status and approved parameters
3. Route to appropriate MCP server based on action type:
   - Email: Use email-mcp with local credentials to send
   - Social: Use social-mcp with local credentials to post
   - Payment: Use odoo-mcp with local credentials to execute
4. Execute action with local secrets and credentials
5. Handle success/error responses
6. Update dashboard with execution results

## Output
- Execution status (success/failure)
- Response from MCP server
- Updated dashboard metrics
- Audit log entry of execution
- Completed task moved to `/Done/local/`

## Dependencies
- skill-mcp-email, skill-social-integrator, skill-odoo-mcp
- Local secrets and credentials
- Dashboard update capability
- Audit logging system