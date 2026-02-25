#!/bin/bash
# Platinum Tier Cloud Executive Setup Script
# Deploys 24/7 Cloud Executive agent on cloud VM with health monitoring

set -e  # Exit on any error

echo "================================="
echo "AI Employee Vault - Platinum Tier"
echo "Cloud Executive VM Setup"
echo "================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    error "Please run as normal user, not root"
    exit 1
fi

# Configuration
VAULT_DIR="$HOME/ai-employee-vault"
CLOUD_DIR="$VAULT_DIR/Platinum-Tier"

log "Step 1: System Prerequisites Check"
log "Checking system requirements..."

# Check system architecture
ARCH=$(uname -m)
if [[ "$ARCH" != "x86_64" && "$ARCH" != "aarch64" ]]; then
    error "Unsupported architecture: $ARCH"
    exit 1
fi

log "Architecture: $ARCH"

log "Step 2: Installing System Dependencies"

# Update package lists
sudo apt update

# Install essential packages
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    nodejs \
    npm \
    git \
    curl \
    wget \
    vim \
    htop \
    tmux \
    supervisor \
    jq \
    psutils

# Install Python packages globally
pip3 install --user psutil schedule watchdog

log "Step 3: Setting up Python Virtual Environment"

# Create virtual environment for the AI Employee Vault
python3 -m venv "$HOME/ai-employee-env"
source "$HOME/ai-employee-env/bin/activate"

# Install Python dependencies
pip install --upgrade pip
pip install psutil schedule watchdog requests tweepy xmlrpc.client

log "Step 4: Cloning AI Employee Vault Repository"

# Create vault directory
mkdir -p "$VAULT_DIR"
cd "$VAULT_DIR"

# Clone the repository (assuming it exists, or create structure)
if [ -d ".git" ]; then
    log "Updating existing repository..."
    git pull
else
    log "Initializing repository structure..."
    # Create basic directory structure for Platinum Tier
    mkdir -p "$CLOUD_DIR/data/Needs_Action/cloud"
    mkdir -p "$CLOUD_DIR/data/Needs_Action/local"
    mkdir -p "$CLOUD_DIR/data/Plans/cloud"
    mkdir -p "$CLOUD_DIR/data/Plans/local"
    mkdir -p "$CLOUD_DIR/data/Pending_Approval/local"
    mkdir -p "$CLOUD_DIR/data/In_Progress/cloud"
    mkdir -p "$CLOUD_DIR/data/In_Progress/local"
    mkdir -p "$CLOUD_DIR/data/Updates"
    mkdir -p "$CLOUD_DIR/data/Signals"
    mkdir -p "$CLOUD_DIR/data/Done/cloud"
    mkdir -p "$CLOUD_DIR/data/Done/local"
    mkdir -p "$CLOUD_DIR/data/Logs"

    # Create .gitkeep files
    find "$CLOUD_DIR/data" -type d -exec touch {}/.gitkeep \;
fi

log "Step 5: Setting up Cloud Executive Configuration"

# Create a sample environment file (without secrets)
cat > "$CLOUD_DIR/.env.cloud" << 'EOF'
# ─── Cloud Executive Configuration ───
# Cloud VM specific settings for Platinum Tier

# ─── Basic Settings ───
VAULT_DIR=.
LOG_DIR=./data/Logs

# ─── MCP Server Settings ───
# Use placeholder values - these should be configured based on actual endpoints
MCP_EMAIL_HOST=localhost
MCP_EMAIL_PORT=8001
MCP_SOCIAL_HOST=localhost
MCP_SOCIAL_PORT=8002
MCP_ODOO_HOST=localhost
MCP_ODOO_PORT=8003

# ─── Draft-only Mode (Platinum Policy) ───
CLOUD_DRAFT_ONLY=true

# ─── Sync Settings ───
GIT_SYNC_INTERVAL=900  # 15 minutes
GIT_DRY_RUN=false

# ─── Health Monitoring ───
HEALTH_CHECK_INTERVAL=300  # 5 minutes
HEALTH_ALERT_EMAIL=

# ─── A2A Phase 2 (Optional) ───
A2A_PHASE2_ENABLED=false
A2A_HOST=localhost
A2A_PORT=8004

# ─── Logging ───
LOG_LEVEL=INFO
PRESERVE_LOGS_DAYS=30
EOF

log "Step 6: Setting up Git Configuration for Cloud"

# Initialize git if not already done
if [ ! -d ".git" ]; then
    git init
    git config --global user.name "Cloud Executive"
    git config --global user.email "cloud-executive@your-domain.com"

    # Create gitignore to exclude sensitive files
    cat > .gitignore << 'EOF'
# Environment files
.env
.env.local
.env.production
*.env
config.env

# Sensitive files
*.key
*.pem
*.crt
*.secret

# Credentials
credentials.json
tokens.json
passwords.txt
keys/

# Session data
sessions/
*.session

# Local development
.vscode/
.idea/
*.pyc
__pycache__/
*.swp
*.swo

# Logs (but keep the structure)
data/Logs/*.log
!data/Logs/.gitkeep

# Temporary files
tmp/
temp/
*.tmp
*.temp

# OS specific
.DS_Store
Thumbs.db
desktop.ini
EOF
fi

log "Step 7: Testing Cloud Executive Setup"

# Test that the required directories exist
if [ -d "$CLOUD_DIR/data/Needs_Action/cloud" ] && [ -d "$CLOUD_DIR/watcher" ]; then
    log "Cloud Executive directories verified"
else
    warn "Some Cloud Executive directories missing - creating structure"
    mkdir -p "$CLOUD_DIR/watcher"
    mkdir -p "$CLOUD_DIR/agents"
    mkdir -p "$CLOUD_DIR/skills"
fi

# Create a simple test script for health monitoring
cat > "$CLOUD_DIR/cloud-health-check.py" << 'EOF
#!/usr/bin/env python3
"""
Cloud Executive Health Check
Monitors cloud executive health and reports status
"""
import os
import sys
import psutil
import json
from datetime import datetime
from pathlib import Path

def check_health():
    """Check health of Cloud Executive system"""
    health_report = {
        "timestamp": datetime.now().isoformat(),
        "service": "cloud_executive",
        "status": "healthy",
        "details": {}
    }

    # Check system resources
    health_report["details"]["system"] = {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage("/").percent,
        "load_avg": os.getloadavg()
    }

    # Check vault directories
    vault_dir = Path(__file__).parent
    data_dir = vault_dir / "data"

    required_dirs = [
        "Needs_Action/cloud",
        "In_Progress/cloud",
        "Done/cloud",
        "Plans/cloud",
        "Updates",
        "Logs"
    ]

    dir_status = {}
    for dir_path in required_dirs:
        full_path = data_dir / dir_path
        dir_status[dir_path] = full_path.exists()

    health_report["details"]["directories"] = dir_status

    # Check if all required dirs exist
    if not all(dir_status.values()):
        health_report["status"] = "warning"
        health_report["message"] = "Some required directories missing"

    # Check if system resources are within limits
    sys_details = health_report["details"]["system"]
    if sys_details["cpu_percent"] > 80 or sys_details["memory_percent"] > 80 or sys_details["disk_percent"] > 90:
        health_report["status"] = "warning"
        health_report["message"] = "High resource usage detected"

    return health_report

if __name__ == "__main__":
    health = check_health()
    print(json.dumps(health, indent=2))

    # Exit with error code if unhealthy
    if health["status"] in ["warning", "critical"]:
        sys.exit(1)
EOF

chmod +x "$CLOUD_DIR/cloud-health-check.py"

log "Step 8: Setting up Systemd Services"

# Create systemd service for Cloud Executive Orchestrator
sudo tee /etc/systemd/system/cloud-executive.service > /dev/null << EOF
[Unit]
Description=AI Employee Cloud Executive Orchestrator
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$CLOUD_DIR
Environment=PATH=$HOME/ai-employee-env/bin
ExecStart=$HOME/ai-employee-env/bin/python3 $CLOUD_DIR/watcher/orchestrator_cloud.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Create systemd service for Cloud Health Monitor
sudo tee /etc/systemd/system/cloud-health-monitor.service > /dev/null << EOF
[Unit]
Description=AI Employee Cloud Health Monitor
After=network.target cloud-executive.service
Wants=network-online.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$CLOUD_DIR
Environment=PATH=$HOME/ai-employee-env/bin
ExecStart=$HOME/ai-employee-env/bin/python3 $CLOUD_DIR/watcher/cloud_health_monitor.py
Restart=always
RestartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Create systemd timer for health checks
sudo tee /etc/systemd/system/cloud-health-check.timer > /dev/null << EOF
[Unit]
Description=Run Cloud Executive Health Checks
Requires=cloud-health-check.service

[Timer]
OnCalendar=hourly
Persistent=true

[Install]
WantedBy=timers.target
EOF

# Create service for health check execution
sudo tee /etc/systemd/system/cloud-health-check.service > /dev/null << EOF
[Unit]
Description=Execute Cloud Health Check
Wants=cloud-health-check.timer

[Service]
Type=oneshot
User=$USER
WorkingDirectory=$CLOUD_DIR
Environment=PATH=$HOME/ai-employee-env/bin
ExecStart=$HOME/ai-employee-env/bin/python3 $CLOUD_DIR/cloud-health-check.py
StandardOutput=journal
StandardError=journal
EOF

# Reload systemd and enable services
sudo systemctl daemon-reload
sudo systemctl enable cloud-executive.service
sudo systemctl enable cloud-health-monitor.service
sudo systemctl enable cloud-health-check.timer

log "Step 9: Setting up Health Monitoring Cron Job"

# Create a health monitoring script
cat > "$HOME/cloud-monitor.sh" << 'EOF
#!/bin/bash
# Cloud Executive Health Monitor Script

VAULT_DIR="$HOME/ai-employee-vault/Platinum-Tier"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

# Check if services are running
if pgrep -f "orchestrator_cloud.py" > /dev/null; then
    echo "[$DATE] Cloud Executive Orchestrator: RUNNING"
else
    echo "[$DATE] Cloud Executive Orchestrator: NOT RUNNING"
    # Attempt to restart if not running
    systemctl --user restart cloud-executive.service 2>/dev/null || sudo systemctl restart cloud-executive.service
fi

if pgrep -f "cloud_health_monitor.py" > /dev/null; then
    echo "[$DATE] Cloud Health Monitor: RUNNING"
else
    echo "[$DATE] Cloud Health Monitor: NOT RUNNING"
    systemctl --user restart cloud-health-monitor.service 2>/dev/null || sudo systemctl restart cloud-health-monitor.service
fi

# Run health check
if [ -f "$VAULT_DIR/cloud-health-check.py" ]; then
    python3 "$VAULT_DIR/cloud-health-check.py" > /tmp/cloud-health-$(date +%Y%m%d).json 2>&1
fi
EOF

chmod +x "$HOME/cloud-monitor.sh"

# Add to crontab for periodic health checks
(crontab -l 2>/dev/null; echo "*/10 * * * * $HOME/cloud-monitor.sh") | crontab -

log "Step 10: Setting up Log Rotation"

# Create logrotate configuration for Cloud Executive logs
sudo tee /etc/logrotate.d/ai-employee-cloud > /dev/null << EOF
$VAULT_DIR/Platinum-Tier/data/Logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    copytruncate
    notifempty
}
EOF

log "Step 11: Creating Startup Script"

cat > "$HOME/start-cloud-executive.sh" << EOF
#!/bin/bash
# Startup script for Cloud Executive services

cd $CLOUD_DIR

# Activate virtual environment
source $HOME/ai-employee-env/bin/activate

# Start Cloud Executive services using systemd
sudo systemctl start cloud-executive.service
sudo systemctl start cloud-health-monitor.service
sudo systemctl start cloud-health-check.timer

echo "Cloud Executive services started"
echo "Check status with: sudo systemctl status cloud-executive.service"
EOF

chmod +x "$HOME/start-cloud-executive.sh"

cat > "$HOME/stop-cloud-executive.sh" << EOF
#!/bin/bash
# Stop script for Cloud Executive services

# Stop Cloud Executive services
sudo systemctl stop cloud-executive.service
sudo systemctl stop cloud-health-monitor.service
sudo systemctl stop cloud-health-check.timer

echo "Cloud Executive services stopped"
EOF

chmod +x "$HOME/stop-cloud-executive.sh"

cat > "$HOME/status-cloud-executive.sh" << EOF
#!/bin/bash
# Status script for Cloud Executive services

echo "Cloud Executive Service Status:"
echo "================================"

sudo systemctl status cloud-executive.service --no-pager -l
echo ""
sudo systemctl status cloud-health-monitor.service --no-pager -l
echo ""
echo "Health Check Results:"
python3 $CLOUD_DIR/cloud-health-check.py
EOF

chmod +x "$HOME/status-cloud-executive.sh"

log "Step 12: Creating Backup Script"

cat > "$HOME/backup-cloud-executive.sh" << 'EOF
#!/bin/bash
# Backup script for Cloud Executive vault data

VAULT_DIR="$HOME/ai-employee-vault/Platinum-Tier"
BACKUP_DIR="$HOME/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# Create backup archive (excluding logs to save space)
tar --exclude='data/Logs/*' -czf "$BACKUP_DIR/cloud-executive-backup-$DATE.tar.gz" -C "$(dirname "$VAULT_DIR")" "$(basename "$VAULT_DIR")"

echo "Backup created: $BACKUP_DIR/cloud-executive-backup-$DATE.tar.gz"

# Remove backups older than 7 days
find "$BACKUP_DIR" -name "cloud-executive-backup-*.tar.gz" -mtime +7 -delete
EOF

chmod +x "$HOME/backup-cloud-executive.sh"

log "Step 13: Final Configuration"

# Create a startup script that can be run manually if needed
cat > "$HOME/manual-start-cloud.sh" << EOF
#!/bin/bash
# Manual startup for Cloud Executive (if systemd fails)

cd $CLOUD_DIR

# Activate virtual environment
source $HOME/ai-employee-env/bin/activate

# Create directories if they don't exist
mkdir -p data/Needs_Action/cloud
mkdir -p data/In_Progress/cloud
mkdir -p data/Done/cloud
mkdir -p data/Plans/cloud
mkdir -p data/Logs

# Start the Cloud Executive orchestrator in background
nohup python3 ./watcher/orchestrator_cloud.py > cloud_orchestrator.log 2>&1 &

# Start the health monitor in background
nohup python3 ./watcher/cloud_health_monitor.py > cloud_health_monitor.log 2>&1 &

echo "Cloud Executive started manually"
echo "Logs available as cloud_orchestrator.log and cloud_health_monitor.log"
EOF

chmod +x "$HOME/manual-start-cloud-executive.sh"

log "Setup Complete!"

echo ""
echo "=================================="
echo "CLOUD EXECUTIVE SETUP COMPLETED"
echo "=================================="
echo ""
echo "Next Steps:"
echo "=========="
echo "1. Review $CLOUD_DIR/.env.cloud and add your MCP server configurations"
echo "2. Configure Git with your repository: git remote add origin [your-repo-url]"
echo "3. Test the setup: $HOME/status-cloud-executive.sh"
echo "4. Start services: $HOME/start-cloud-executive.sh"
echo ""
echo "Systemd Services:"
echo "- cloud-executive.service: Core orchestrator"
echo "- cloud-health-monitor.service: Health monitoring"
echo "- cloud-health-check.timer: Periodic health checks"
echo ""
echo "Maintenance Scripts:"
echo "- $HOME/start-cloud-executive.sh: Start all services"
echo "- $HOME/stop-cloud-executive.sh: Stop all services"
echo "- $HOME/status-cloud-executive.sh: Check service status"
echo "- $HOME/backup-cloud-executive.sh: Create backup"
echo "- $HOME/cloud-monitor.sh: Manual health check"
echo ""
echo "Health monitoring is set up with:"
echo "- Systemd service monitoring (restarts on failure)"
echo "- Hourly health checks via systemd timer"
echo "- 10-minute cron checks for basic monitoring"
echo "- Log rotation for 30 days"
echo ""
echo "For Oracle Cloud Free Tier (Ampere A1):"
echo "- Services will run within always-free limits"
echo "- Monitor usage to stay within free tier"
echo ""
echo "For AWS (t2.micro):"
echo "- Services will run within free tier limits (first year)"
echo "- Consider t3.micro for better performance"
echo ""
echo "Remember: Cloud Executive operates in DRAFT-ONLY mode"
echo "It generates drafts but never executes sends/posts/payments"
echo "Local system handles all approvals and execution."
echo "=================================="