# Platinum Tier - End-to-End Run Guide

## System Overview

The Platinum Tier consists of a distributed multi-agent system with:
- **Cloud Executive**: 24/7 cloud-based agent handling triage/drafts
- **Local Executive**: Local approval/execution agent with sensitive credentials
- **Shared Vault**: Git-synced filesystem for coordination
- **A2A Messaging**: Optional direct communication between agents

## Prerequisites

### Cloud Environment Setup
```bash
# Install Python dependencies
pip install schedule

# Configure cloud-specific environment
export VAULT_ENVIRONMENT=cloud
export A2A_PHASE2_ENABLED=false  # Optional: enable A2A Phase 2
export A2A_CLOUD_HOST=127.0.0.1
export A2A_CLOUD_PORT=9100
export MCP_EMAIL_DRY_RUN=true  # For development

# MCP server tokens for cloud operations
# (without sensitive local credentials)
```

### Local Environment Setup
```bash
# Install Python dependencies
pip install schedule

# Configure local-specific environment
export VAULT_ENVIRONMENT=local
export A2A_PHASE2_ENABLED=false  # Optional: enable A2A Phase 2
export A2A_LOCAL_HOST=127.0.0.1
export A2A_LOCAL_PORT=9101

# MCP server tokens for local operations
# (with sensitive credentials for sends/execution)
export MCP_EMAIL_ADDRESS="your-email@gmail.com"
export MCP_EMAIL_APP_PASSWORD="your-app-password"
# WhatsApp, banking credentials, etc.
```

### Git Repository Setup
```bash
# Initialize shared vault repository
cd AI_Employee_Vault
git init
git remote add origin <your-git-remote-url>

# Configure .gitignore to exclude secrets
echo "data/.env*" >> .gitignore
echo ".env*" >> .gitignore
echo "data/whatsapp_session*" >> .gitignore

# Initial commit
git add data/
git commit -m "Initial Platinum Tier vault setup"
git push -u origin main
```

## Running the System

### Method 1: Individual Agent Launch

#### Start Cloud Executive
```bash
# In cloud environment
cd Platinum-Tier
python -c "
import sys
sys.path.insert(0, '.')
from watcher.orchestrator_cloud import CloudExecutiveProcessor
import time

orchestrator = CloudExecutiveProcessor(dry_run=True)  # Set to False in production
orchestrator.start()

try:
    while orchestrator.running:
        time.sleep(60)
except KeyboardInterrupt:
    orchestrator.stop()
"
```

#### Start Local Executive
```bash
# In local environment
cd Platinum-Tier
python -c "
import sys
sys.path.insert(0, '.')
from agents.agent-local-executive import LocalExecutiveAgent
import time

agent = LocalExecutiveAgent()
agent.running = True

try:
    while agent.running:
        # Run one cycle
        agent.sync_pull()
        agent.read_pending_approvals()
        agent.process_updates()

        approved_files = agent.check_for_approvals()
        if approved_files:
            for approved_file in approved_files:
                agent.execute_approved_action(approved_file)

        agent.merge_dashboard_updates()
        agent.process_completed_tasks()
        agent.sync_push()

        time.sleep(30)  # Wait before next cycle
except KeyboardInterrupt:
    agent.running = False
"
```

### Method 2: Using Orchestrator Scripts

#### Cloud Orchestrator
```bash
# Start full cloud system (orchestrator + watchers)
cd Platinum-Tier
python watcher/orchestrator_cloud.py
```

#### Local Orchestrator
```bash
# Start full local system (orchestrator + watchers)
cd Platinum-Tier
python agents/agent-local-executive.py
```

### Method 3: Production Deployment

#### Cloud VM Setup
```bash
# Create cloud startup script
cat > cloud_startup.sh << 'EOF'
#!/bin/bash
cd /path/to/AI_Employee_Vault/Platinum-Tier

# Start cloud orchestrator
python watcher/orchestrator_cloud.py > cloud_orchestrator.log 2>&1 &

# Start cloud-specific watchers
python watcher/gmail_watcher.py > gmail_watcher.log 2>&1 &
python watcher/facebook_watcher.py > facebook_watcher.log 2>&1 &
python watcher/instagram_watcher.py > instagram_watcher.log 2>&1 &
python watcher/x_watcher.py > x_watcher.log 2>&1 &

# Start cloud watchdog
python watchdog_cloud.py > cloud_watchdog.log 2>&1 &

echo "Cloud system started"
EOF

chmod +x cloud_startup.sh
./cloud_startup.sh
```

#### Local System Setup
```bash
# Create local startup script
cat > local_startup.sh << 'EOF'
#!/bin/bash
cd /path/to/AI_Employee_Vault/Platinum-Tier

# Start local orchestrator
python agents/agent-local-executive.py > local_orchestrator.log 2>&1 &

# Start local-specific watchers
python watcher/whatsapp_watcher.py > whatsapp_watcher.log 2>&1 &

# Start local watchdog
python watchdog_local.py > local_watchdog.log 2>&1 &

echo "Local system started"
EOF

chmod +x local_startup.sh
./local_startup.sh
```

## A2A Phase 2 Setup (Optional)

### Enable A2A Messaging
```bash
# Enable on both cloud and local
export A2A_PHASE2_ENABLED=true

# Cloud configuration
export A2A_CLOUD_HOST=0.0.0.0  # Listen on all interfaces if running on VM
export A2A_CLOUD_PORT=9100

# Local configuration
export A2A_LOCAL_HOST=0.0.0.0  # Listen on all interfaces
export A2A_LOCAL_PORT=9101

# If cloud VM has public IP, local connects to it
export A2A_CLOUD_HOST=<your-cloud-vm-ip>
```

### Test A2A Connection
```bash
# Test cloud node
cd Platinum-Tier
python a2a_messaging.py --role cloud

# In another terminal, test local node
cd Platinum-Tier
python a2a_messaging.py --role local

# Send test message
python a2a_messaging.py --send local draft_ready '{"draft_id":"test123","summary":"Test draft"}'
```

## Workflow Demonstration

### Full Cycle Test
1. **Inject Email**: Create file in `data/Needs_Action/cloud/`
2. **Cloud Processing**: Draft created in `data/Plans/cloud/`, approval in `data/Pending_Approval/local/`
3. **Human Approval**: Move file from `Pending_Approval/local/` to `Approved/`
4. **Local Execution**: Local agent executes via MCP, writes result to `Updates/`
5. **Dashboard Merge**: Local merges cloud updates into `Dashboard.md`
6. **Sync**: Git sync propagates completed work back to cloud

### Example: Email Response Cycle
```bash
# 1. Create mock email
cat > "data/Needs_Action/cloud/EMAIL_test_$(date +%Y%m%d_%H%M%S).md" << EOF
---
type: email
action: email_triage
from: test@example.com
subject: Test Inquiry
status: pending
priority: normal
zone: cloud
created: $(date -Iseconds)
---

# Incoming Email

**From:** test@example.com
**Subject:** Test Inquiry

Can you help with this test?

Best regards,
Test User
EOF

# 2. Cloud Executive processes (automatically via orchestrator)
# Creates: DRAFT_email_reply_*.md in Plans/cloud/
# Creates: APPROVE_email_*.md in Pending_Approval/local/

# 3. Human approves by moving file
mv "data/Pending_Approval/local/APPROVE_email_*.md" "data/Approved/"

# 4. Local Executive executes (automatically via agent)
# Sends email via MCP, creates update in Updates/

# 5. Dashboard updated and changes synced via Git
```

## Monitoring and Health Checks

### Check System Status
```bash
# Cloud status
python watcher/orchestrator_cloud.py --status

# Local status
python agents/agent-local-executive.py --status

# Health checks
python watcher/orchestrator_cloud.py --health
python agents/agent-local-executive.py --health

# Git sync status
python watcher/orchestrator_cloud.py --sync
python agents/agent-local-executive.py --single-run  # Triggers sync
```

### Log Monitoring
```bash
# Cloud logs
tail -f data/Logs/cloud_orchestrator.log

# Local logs
tail -f data/Logs/local_executive.log

# A2A logs (if enabled)
tail -f data/Logs/a2a_messaging.log

# Watchdog logs
tail -f data/Logs/watchdog.log
tail -f data/Logs/watchdog_local.log
```

### Dashboard Updates
```bash
# Monitor Dashboard.md for updates
watch -n 5 'cat data/Dashboard.md | head -20'
```

## Troubleshooting

### Common Issues

1. **Git Sync Failures**
   - Check Git configuration and remote access
   - Verify .gitignore excludes secrets
   - Ensure both systems can access remote repository

2. **A2A Messaging Issues**
   - Verify `A2A_PHASE2_ENABLED` is set consistently
   - Check network connectivity between cloud/local
   - Confirm ports are open and not blocked

3. **Claim-by-Move Conflicts**
   - Verify zone-specific directory separation
   - Check file permissions in vault directories
   - Ensure no two processes access same directory

4. **MCP Execution Failures**
   - Verify local credentials are properly configured
   - Check MCP server logs in `data/Logs/`
   - Ensure MCP servers are running

### Recovery Procedures

1. **Quarantined Files**: Move from `data/Quarantine/` back to appropriate queue
2. **Stuck Processes**: Check `In_Progress/` directories, move to `Needs_Action/` if needed
3. **Sync Conflicts**: Manual Git merge, then resume normal operation
4. **Failed Executions**: Retry by moving from `Done/` back to `Approved/` if needed

## Verification Steps

### Complete System Test
```bash
# Run the full demo test
cd Platinum-Tier
python demo_test.py --clean
```

This runs the complete 5-phase verification:
1. Cloud Triage (local offline)
2. Sync Verification
3. Local Approval & Execution
4. Dashboard Merge
5. Audit Verification

### Expected Results
- All 5 phases should PASS
- No errors in orchestrator logs
- Proper file movement between vault directories
- Complete audit trail maintained