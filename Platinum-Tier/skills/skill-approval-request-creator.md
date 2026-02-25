# Approval Request Creator Skill

## Purpose
Generates formal approval requests for complex operations that require human review.

## Functionality
- Creates structured request files for pending approvals
- Formats requests according to company standards
- Adds metadata for tracking and prioritization
- Places requests in data/Pending_Approval directory

## Request Structure
- Request ID (auto-generated)
- Requestor information
- Request details and justification
- Risk assessment
- Required approval level
- Deadline for response

## Integration
- Works with Company_Handbook policy checker
- Interfaces with dashboard updater
- Creates notification entries in logs
- Tracks approval workflow status