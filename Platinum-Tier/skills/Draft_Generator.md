# Draft_Generator

## Extended Skill Definition

### Overview
Draft_Generator creates professional-quality drafts for email replies, social media posts, and Odoo actions while strictly adhering to Platinum Tier draft-only policies. This skill ensures all outputs comply with the separation of duties between cloud (draft) and local (execute) operations.

### Detailed Process Flow

#### Step 1: Content Analysis
- Parse source content to understand context and requirements
- Identify tone, formality level, and appropriate response style
- Extract key information points and action items
- Determine platform-specific requirements (character limits, formatting)

#### Step 2: Template Selection
- **Email Templates**: Professional response, follow-up, escalation, or canned response
- **Social Templates**: LinkedIn post, Facebook update, Twitter thread, or engagement reply
- **Odoo Templates**: Invoice draft, payment draft, customer communication, or internal note

#### Step 3: Draft Creation
- Generate content following selected template
- Apply Platinum Tier compliance rules (no execution, proper approval flow)
- Include appropriate call-to-action that leads to approval workflow
- Ensure content aligns with brand voice and company policies

#### Step 4: Quality Assurance
- Verify character limits and formatting requirements
- Check for compliance with platform-specific rules
- Ensure draft-only nature (no actual execution commands)
- Validate that approval requirements are clearly marked

#### Step 5: Output Generation
- Create draft file in data/Plans/cloud/ with proper naming convention
- Generate approval request in data/Pending_Approval/local/
- Update dashboard with draft status and next steps
- Log all actions via audit system

### Platform-Specific Draft Types

#### Email Drafts
- **Response Drafts**: Professional replies to customer inquiries
- **Follow-up Drafts**: Checking on pending matters
- **Escalation Drafts**: Flagging urgent issues for human attention
- **Template**: Include proper greeting, context reference, clear request, and signature

#### Social Media Drafts
- **LinkedIn Posts**: Professional updates, thought leadership, company news
- **Facebook Content**: Community engagement, promotional material, updates
- **Twitter Content**: Quick updates, engagement responses, trending topics
- **Template**: Platform-appropriate length, hashtags, engagement hooks

#### Odoo Drafts
- **Invoice Drafts**: Properly formatted for approval
- **Customer Communication**: Follow-up on invoices, delivery notifications
- **Internal Notes**: Operational updates for accounting team
- **Template**: Include all required fields, approval flags, and business context

### Examples

#### Example: Email Draft Generation
**Input**: Customer complaint about delayed order
**Process**:
1. Analyze complaint urgency and tone
2. Select professional response template
3. Generate draft acknowledging issue, providing timeline, offering solution
4. Mark for approval as draft-only
5. Include escalation flag if needed

**Output Draft**:
```yaml
---
type: email_draft
platform: email
status: pending_approval
priority: high
to: important.client@example.com
from: cloud-executive
subject: Re: Urgent issue with latest order
approval_required: true
created: 2026-02-21T15:45:00Z
---
Dear [Client Name],

Thank you for reaching out regarding your recent order #12345. We sincerely apologize for the delay you've experienced.

Our team has investigated your order and found it was held up in our quality check process. We've expedited it through our system, and you should receive it by [date].

To make up for this inconvenience, we'd like to offer you [compensation]. We value your business and are committed to preventing similar issues in the future.

Please let us know if this resolution is acceptable or if you need any further assistance.

Best regards,
Cloud Executive Assistant
```

#### Example: Social Media Draft
**Input**: Product milestone to announce
**Output Draft**:
```yaml
---
type: social_draft
platform: linkedin
status: pending_approval
priority: normal
post_type: company_news
approval_required: true
created: 2026-02-21T16:00:00Z
---
We're thrilled to announce that our AI Employee Vault has successfully processed 10,000+ business operations! This milestone reflects our commitment to transforming business automation.

A huge thank you to our customers who trust us with their digital operations. We're excited to continue innovating and supporting businesses with our Platinum Tier solutions.

#Automation #AI #BusinessInnovation #Milestone
```

### Compliance Rules

#### Draft-Only Enforcement
- No actual sends, posts, or payments in generated drafts
- Clear approval requirements marked in YAML frontmatter
- Execution instructions removed from draft content
- Clear pathway to approval workflow defined

#### Content Review
- No confidential business data in social media drafts
- Professional tone maintained across all platforms
- Accurate representation of company position
- Compliance with platform-specific community guidelines

### Error Handling Scenarios

#### Template Error
- **Issue**: Unable to select appropriate template
- **Action**: Use fallback template, flag for review
- **Log**: Record template selection failure for analysis

#### Compliance Violation
- **Issue**: Draft would violate Platinum Tier policies
- **Action**: Do not create draft, flag for human review
- **Log**: Create compliance violation record in audit system

#### Content Generation Failure
- **Issue**: Unable to generate appropriate content
- **Action**: Create minimal draft with clear request for human input
- **Log**: Track content generation failures for improvement

### Integration Points
- **Social MCP**: Applies platform-specific formatting rules
- **Odoo MCP**: Formats accounting drafts correctly
- **Email MCP**: Prepares email drafts for approval
- **Dashboard**: Updates draft creation metrics
- **Audit Logger**: Records all draft generation activity