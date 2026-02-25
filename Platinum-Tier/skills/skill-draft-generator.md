# skill-draft-generator

## Purpose
Generate drafts for email replies, social media posts, and Odoo actions following Platinum Tier draft-only policies. Creates structured draft files for human approval workflow.

## Trigger
- Triage results requiring draft creation
- New email requiring response draft
- Social media engagement requiring response draft
- Odoo action requiring draft invoice/payment

## Input
- Source content (email thread, social post, accounting data)
- Draft type (email, social, odoo)
- Context information and required compliance rules
- Platinum Tier Company Handbook policies

## Process
1. **Analyze Source**: Understand content, tone, and required response
2. **Apply Compliance**: Check against Platinum Tier policies
3. **Generate Draft**: Create structured draft content following type-specific templates:
   - Email: Professional tone, clear subject, appropriate response, signature block
   - Social: Platform-specific format, hashtags, engagement strategy
   - Odoo: Proper accounting format, approval flags, business context
4. **Validate**: Ensure draft meets draft-only requirements
5. **Create File**: Save to data/Plans/cloud/ with proper YAML frontmatter
6. **Queue Approval**: Create approval file in data/Pending_Approval/local/

## Output
- Draft file in data/Plans/cloud/ with YAML frontmatter
- Approval request in data/Pending_Approval/local/
- Dashboard updated with draft status
- Audit logs updated via skill-audit-logger

## Dependencies
- skill-file-system-access: Create and write draft files
- skill-approval-request-creator: Generate approval requests
- skill-dashboard-updater: Update draft status
- skill-logger: Log draft creation and compliance checks
- skill-social-integrator: For social media formatting
- skill-odoo-mcp: For Odoo-specific formatting (draft mode)

## Error Handling
- On compliance violation: Flag for human review, do not create draft
- On template error: Use fallback template or move to quarantine
- On approval queue failure: Retry with exponential backoff