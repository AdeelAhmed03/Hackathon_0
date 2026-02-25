#!/bin/bash
# Platinum Tier System Starter

echo "AI Employee Vault - Platinum Tier System Starter"
echo "==============================================="

if [ "$1" = "cloud" ]; then
    echo "Starting Cloud Executive System..."
    echo "Environment: $VAULT_ENVIRONMENT"

    cd Platinum-Tier
    echo "Starting Cloud Orchestrator..."
    python watcher/orchestrator_cloud.py > data/Logs/cloud_orchestrator.log 2>&1 &
    CLOUD_PID=$!

    echo "Starting Cloud Watchers..."
    python watcher/gmail_watcher.py > data/Logs/gmail_watcher.log 2>&1 &
    python watcher/facebook_watcher.py > data/Logs/facebook_watcher.log 2>&1 &
    python watcher/instagram_watcher.py > data/Logs/instagram_watcher.log 2>&1 &
    python watcher/x_watcher.py > data/Logs/x_watcher.log 2>&1 &

    echo "Starting Cloud Watchdog..."
    python watchdog_cloud.py > data/Logs/watchdog_cloud.log 2>&1 &

    echo "Cloud system started with PID: $CLOUD_PID"
    echo "Check logs in data/Logs/ directory"

elif [ "$1" = "local" ]; then
    echo "Starting Local Executive System..."
    echo "Environment: $VAULT_ENVIRONMENT"

    cd Platinum-Tier
    echo "Starting Local Executive Agent..."
    python agents/agent-local-executive.py > data/Logs/local_executive.log 2>&1 &
    LOCAL_PID=$!

    echo "Starting Local Watchers..."
    python watcher/whatsapp_watcher.py > data/Logs/whatsapp_watcher.log 2>&1 &

    echo "Starting Local Watchdog..."
    python watchdog_local.py > data/Logs/watchdog_local.log 2>&1 &

    echo "Local system started with PID: $LOCAL_PID"
    echo "Check logs in data/Logs/ directory"

elif [ "$1" = "demo" ]; then
    echo "Running Platinum Gate Demo Test..."
    cd Platinum-Tier
    python demo_test.py --clean

else
    echo "Usage:"
    echo "  $0 cloud    - Start Cloud Executive system"
    echo "  $0 local    - Start Local Executive system"
    echo "  $0 demo     - Run Platinum Gate demo test"
    echo ""
    echo "Make sure to set VAULT_ENVIRONMENT=cloud or VAULT_ENVIRONMENT=local"
    echo "before starting the appropriate system."
fi