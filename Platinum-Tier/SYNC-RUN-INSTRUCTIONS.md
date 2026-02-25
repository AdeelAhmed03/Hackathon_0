# Platinum Tier Sync - Run Instructions

## Overview
This document provides instructions for running the Git sync system between local and cloud AI Employee Vault systems. The sync system ensures coordination between Cloud Executive (drafts/triage) and Local Executive (approvals/execution) agents.

## Git Sync Setup (Phase 1 - Recommended)

### 1. Prerequisites
```bash
# Ensure Git is installed
git --version

# Ensure the vault directory is a Git repository
cd /path/to/ai-employee-vault
git init  # If not already initialized
```

### 2. Configure Remote Repository
```bash
# Add your shared repository (ensure it's private and secure)
git remote add origin https://your-private-repo.git

# Set up proper git configuration
git config user.name "AI Employee Vault"
git config user.email "vault@your-domain.com"
```

### 3. Install Python Dependencies
```bash
# Create virtual environment
python3 -m venv sync-env
source sync-env/bin/activate  # On Windows: sync-env\Scripts\activate

# Install required packages
pip install psutil schedule
```

## Git Sync Usage

### 1. One-time Sync
```bash
# Run one sync cycle and exit
python3 git_sync.py --one-time

# Run as cloud (pull then push)
python3 git_sync.py --cloud --one-time

# Run as local (pull only)
python3 git_sync.py --local --one-time
```

### 2. Continuous Daemon Mode
```bash
# Run as daemon on cloud (synchronize every 15 minutes by default)
python3 git_sync.py --cloud --daemon

# Run as daemon on local (pull every 10 minutes)
python3 git_sync.py --local --daemon --interval 600

# Run with custom interval (30 minutes)
python3 git_sync.py --daemon --interval 1800
```

### 3. Check Sync Status
```bash
# Check current sync status
python3 git_sync.py --status
```

### 4. Test Mode
```bash
# Test sync functionality without performing actual sync
python3 git_sync.py --test-mode
```

## Syncthing Alternative Setup (Phase 2)

### 1. Install Syncthing
```bash
# On Ubuntu/Debian
sudo apt install syncthing

# On CentOS/RHEL
sudo dnf install syncthing

# Or download from https://syncthing.net/
```

### 2. Configure Syncthing
```bash
# Copy the provided configuration
cp syncthing-config.xml ~/.config/syncthing/config.xml

# Or generate a new config with proper exclusions
# The provided config already excludes sensitive files
```

### 3. Start Syncthing
```bash
# Start Syncthing service
syncthing -gui-address="http://localhost:8384"

# Access the web interface at http://localhost:8384
# Default API key needs to be updated in the config file
```

### 4. Configure Devices
1. Access Syncthing web interface (http://localhost:8384)
2. Add the other device (Cloud or Local) using its device ID
3. Share the AI Employee Vault data folder between devices
4. Ensure the ignore patterns match the .gitignore file

## Integration with Orchestrators

### 1. Cloud Orchestrator Integration
Add to `watcher/orchestrator_cloud.py`:
```python
# Add as a managed service
self.service_configs["cloud_sync_watcher"] = {
    "script": "git_sync.py --cloud --daemon",
    "restart_delay": 10,
    "max_restarts": 3
}
```

### 2. Local Orchestrator Integration
Add to `watcher/orchestrator_local.py`:
```python
# Add as a managed service
self.service_configs["local_sync_watcher"] = {
    "script": "git_sync.py --local --daemon",
    "restart_delay": 10,
    "max_restarts": 3
}
```

## Security Considerations

### 1. No Secrets Sync
The configuration ensures that no sensitive data is synchronized:
- `.env` files and variants
- Credential files (`credentials.json`, `tokens.json`, etc.)
- Session data
- Private keys
- Log files with sensitive content

### 2. Claim-by-Move Protection
The sync system implements claim-by-move conflict detection:
```python
# Before processing any file, check if it's already claimed by the other system
if sync_handler.is_file_in_progress_by_other(file_path):
    logger.warning(f"File {file_path.name} already in progress by other system")
    continue  # Skip this file
```

### 3. Manual Conflict Resolution
If sync conflicts occur, the system creates alert files:
```
data/Needs_Action/SYNC_CONFLICT_<timestamp>.md
```

## Monitor Sync Operations

### 1. Check Sync Logs
```bash
# Check Git sync logs
tail -f data/Logs/git_sync.log

# For systemd services, use journalctl:
sudo journalctl -u cloud-sync.service -f
```

### 2. Monitor Sync Status
```bash
# Regular status checks
python3 git_sync.py --status

# Check Git status
git -C /path/to/vault status
git -C /path/to/vault log --oneline -5
```

## Troubleshooting

### 1. Sync Conflicts
If a sync conflict occurs:

1. Check the conflict alert file in `data/Needs_Action/`
2. Manually resolve Git conflicts:
   ```bash
   git status  # Check conflicted files
   git mergetool  # Use merge tool to resolve
   git add .  # Add resolved files
   git commit -m "Resolve sync conflict"
   git push  # Push resolved changes
   ```
3. Remove the conflict notification file when resolved

### 2. Service Not Running
```bash
# Check if sync process is running
ps aux | grep git_sync
ps aux | grep python.*git_sync

# Restart if needed
pkill -f git_sync
python3 git_sync.py --daemon
```

### 3. Network Issues
```bash
# Test connectivity to Git remote
git ls-remote origin

# For Syncthing, check if other device is reachable
syncthing -home=/path/to/config status
```

## Performance Tuning

### 1. Sync Interval Adjustment
- Default: 15 minutes (900 seconds) - good for most use cases
- Aggressive: 5 minutes (300 seconds) - for rapid changes
- Conservative: 30 minutes (1800 seconds) - for low-bandwidth connections

### 2. Resource Usage
The sync system is designed to be lightweight:
- Low CPU usage during idle periods
- Minimal memory footprint
- Efficient file change detection

## Best Practices

### 1. Regular Monitoring
- Monitor sync logs daily
- Check Git repository health weekly
- Verify that no sensitive files are being synced

### 2. Backup Strategy
- Maintain Git repository backups
- Regular system snapshots
- Test recovery procedures periodically

### 3. Network Security
- Use VPN or private networking when possible
- Secure Git repository with proper authentication
- Monitor network traffic for unusual patterns

## Emergency Procedures

### 1. Sync Failure
1. Check logs for error details
2. Verify network connectivity
3. Check disk space on both systems
4. Run manual sync with `--test-mode` flag
5. If needed, temporarily disable automatic sync and sync manually

### 2. Conflicting Changes
1. Stop both sync systems to prevent further conflicts
2. Manually resolve conflicts on one system
3. Propagate changes to the other system
4. Resume sync operations

## Conclusion

The Git sync system provides secure, reliable synchronization between cloud and local AI Employee Vault systems while maintaining proper security boundaries. The system follows Platinum Tier principles:

- Only markdown/state files are synchronized
- No sensitive credentials are transmitted
- Claim-by-move conflict detection prevents double-processing
- Proper error handling and alerting
- Integration with orchestrator systems for 24/7 operation