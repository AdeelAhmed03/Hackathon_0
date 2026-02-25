# Platinum Tier Cloud Executive - Setup Instructions

## Overview
This document provides instructions to deploy the 24/7 Cloud Executive agent on a cloud VM. The Cloud Executive handles email triage, draft generation, and social media drafts in a distributed Platinum Tier setup.

## System Requirements
- Ubuntu 22.04 LTS
- Minimum: 1 CPU, 6GB RAM (Oracle A1 or AWS t2.micro)
- Recommended: 2 CPU, 8GB RAM for optimal performance
- At least 20GB disk space

## Cloud Provider Options

### Option 1: Oracle Cloud Infrastructure (OCI) - Free Tier
1. Go to https://cloud.oracle.com/
2. Create an account with valid payment method (required for verification)
3. Navigate to "Create a VM Instance"
4. Select "Ubuntu 22.04 LTS"
5. Choose "VM.Standard.A1.Flex" (Ampere A1 with up to 4 OCPUs, 24GB RAM - always free)
6. Configure SSH key access
7. Launch the instance

### Option 2: Amazon Web Services (AWS) - Free Tier
1. Go to https://aws.amazon.com/free/
2. Create an account with valid payment method
3. Navigate to EC2 Dashboard
4. Launch Instance
5. Select "Ubuntu Server 22.04 LTS (HVM)"
6. Choose "t2.micro" or "t3.micro" instance type
7. Configure security group (allow SSH, HTTP, HTTPS)
8. Launch with SSH key

## SSH Access
```bash
# Connect to your VM (replace with your VM's IP address)
ssh -i your-private-key.pem ubuntu@your-vm-ip

# Update system packages
sudo apt update && sudo apt upgrade -y
```

## Deployment Steps

### 1. Install Prerequisites
```bash
# Install Git if not already present
sudo apt install -y git curl wget vim

# Clone this repository or upload the setup script
git clone [your-repo-url]
# OR upload the setup script you created
scp setup-cloud-vm.sh ubuntu@your-vm-ip:~/
```

### 2. Run Setup Script
```bash
# Make the script executable
chmod +x setup-cloud-vm.sh

# Run the setup (this will take 10-15 minutes)
./setup-cloud-vm.sh
```

### 3. Configure Git Sync
```bash
cd ~/ai-employee-vault/Platinum-Tier

# Configure your remote repository
git remote add origin [your-vault-repository-url]

# If using a shared repository, pull initial data
git pull origin main --allow-unrelated-histories

# Configure git for this system
git config user.name "Cloud Executive"
git config user.email "cloud@your-domain.com"
```

### 4. Configure Environment Variables
```bash
# Edit the cloud environment file
vim .env.cloud

# Add your MCP server configurations:
# MCP_EMAIL_HOST=your-email-mcp-host
# MCP_EMAIL_PORT=8001
# MCP_SOCIAL_HOST=your-social-mcp-host
# MCP_SOCIAL_PORT=8002
# etc.
```

### 5. Start Cloud Executive Services
```bash
# Start all services
~/start-cloud-executive.sh

# Check status
~/status-cloud-executive.sh
```

## Service Management

### Start Services
```bash
~/start-cloud-executive.sh
# OR use systemd directly:
sudo systemctl start cloud-executive.service
sudo systemctl start cloud-health-monitor.service
```

### Stop Services
```bash
~/stop-cloud-executive.sh
# OR:
sudo systemctl stop cloud-executive.service
sudo systemctl stop cloud-health-monitor.service
```

### Check Service Status
```bash
~/status-cloud-executive.sh
# OR:
sudo systemctl status cloud-executive.service
sudo systemctl status cloud-health-monitor.service
```

### View Logs
```bash
# Using journalctl (systemd logs)
sudo journalctl -u cloud-executive.service -f
sudo journalctl -u cloud-health-monitor.service -f

# Direct log files
tail -f ~/ai-employee-vault/Platinum-Tier/data/Logs/cloud_orchestrator.log
```

## Health Monitoring

### Systemd Services
The setup creates three systemd services:

1. **cloud-executive.service**: Main orchestrator process
2. **cloud-health-monitor.service**: Health monitoring process
3. **cloud-health-check.timer**: Periodic health check timer (hourly)

### Manual Health Checks
```bash
# Run manual health check
python3 ~/ai-employee-vault/Platinum-Tier/cloud-health-check.py

# Check system status via script
~/cloud-monitor.sh
```

### Log Rotation
Logs are automatically rotated daily and kept for 30 days. Configuration is in `/etc/logrotate.d/ai-employee-cloud`.

## Security Considerations

### 1. Never Store Secrets on Cloud
- Cloud Executive operates in DRAFT-ONLY mode
- No sensitive credentials stored on cloud VM
- Git sync excludes all credential files
- Local system handles all sensitive operations

### 2. Access Control
- Use SSH key authentication only
- Disable password authentication
- Configure security groups/firewall properly
- Regular system updates

### 3. Network Security
- Only allow necessary ports (SSH, application ports)
- Use VPN or private networking when possible
- Monitor network traffic patterns

## Maintenance

### 1. Regular Monitoring
```bash
# Check service status daily
~/status-cloud-executive.sh

# Review logs regularly
sudo journalctl -u cloud-executive.service --since "1 hour ago"

# Check disk space
df -h
```

### 2. Backups
```bash
# Create manual backup
~/backup-cloud-executive.sh

# Automated backups run automatically via cron
# Check backup directory
ls -la ~/backups/
```

### 3. Updates
```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Update Python dependencies
source ~/ai-employee-env/bin/activate
pip install --upgrade psutil schedule watchdog requests tweepy xmlrpc.client
```

## Troubleshooting

### Service Won't Start
```bash
# Check detailed logs
sudo journalctl -u cloud-executive.service -n 50

# Check file permissions
ls -la ~/ai-employee-vault/Platinum-Tier/

# Manual test
source ~/ai-employee-env/bin/activate
cd ~/ai-employee-vault/Platinum-Tier
python3 ./watcher/orchestrator_cloud.py --status
```

### Git Sync Issues
```bash
# Check git status
cd ~/ai-employee-vault/Platinum-Tier
git status
git pull origin main

# Fix any conflicts or issues with local files
```

### High Resource Usage
```bash
# Check current resource usage
htop

# Monitor specific processes
ps aux | grep python

# If needed, restart services
~/stop-cloud-executive.sh
~/start-cloud-executive.sh
```

## Usage in Platinum Tier

### Work-Zone Separation
- **Cloud Executive**: Handles triage, drafts, synchronizes with local
- **Local Executive**: Handles approvals, execution, sensitive operations
- **Sync Protocol**: Git-based, markdown/state files only, no secrets

### File Flow
```
Local System → Git Sync → Cloud Executive → Drafts → Git Sync → Local Approval Queue
```

### Draft-Only Operation
The Cloud Executive:
- Generates email reply drafts → `/data/Plans/cloud/`
- Creates social media drafts → `/data/Plans/cloud/`
- Prepares Odoo action drafts → `/data/Plans/cloud/`
- Creates approval requests → `/data/Pending_Approval/local/`
- NEVER executes sends/posts/payments

## Performance Monitoring

### Key Metrics to Monitor
- CPU usage (should stay below 80%)
- Memory usage (should stay below 80%)
- Disk space (should stay above 10% free)
- Service uptime (should be 99.9%+)

### Setting up Monitoring Alerts
```bash
# Example: Check if services are running (add to monitoring system)
if ! pgrep -f orchestrator_cloud.py > /dev/null; then
    echo "Cloud Executive is not running!"
    # Add alert notification here
fi
```

## Cost Optimization

### Oracle Cloud Free Tier
- VM.Standard.A1.Flex is always free with up to 4 OCPUs and 24GB RAM
- 2TB monthly data transfer included
- Monitor usage at cloud.oracle.com

### AWS Free Tier
- t2.micro (or t3.micro) for first 750 hours/month
- 15 GB data transfer included monthly
- Monitor costs at console.aws.amazon.com

## Emergency Procedures

### Service Failure
1. Check service status: `sudo systemctl status cloud-executive.service`
2. Review logs: `sudo journalctl -u cloud-executive.service -n 100`
3. Restart: `sudo systemctl restart cloud-executive.service`
4. If persistent, use manual start: `~/manual-start-cloud.sh`

### Data Corruption
1. Check git history for recent changes
2. Restore from backup: `tar -xzf backup-file.tar.gz`
3. Run manual health check
4. Restart services

## Conclusion

Your Cloud Executive agent is now set up with:
- 24/7 operation capability
- Health monitoring and auto-restart
- Log management and rotation
- Security best practices
- Backup procedures
- Performance monitoring

Remember that the Cloud Executive operates in draft-only mode as per Platinum Tier security policies, with all sensitive operations handled by the Local Executive system. The distributed operation ensures that sensitive credentials remain isolated while maintaining coordinated operation through the file-based vault system.

For optimal operation, monitor the system regularly and maintain the local/cloud synchronization to ensure seamless Platinum Tier operation.