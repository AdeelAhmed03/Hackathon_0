@echo off
REM Platinum Tier System Starter (Windows)

echo AI Employee Vault - Platinum Tier System Starter
echo ===============================================

if "%1"=="cloud" (
    echo Starting Cloud Executive System...
    echo Environment: %VAULT_ENVIRONMENT%

    cd Platinum-Tier
    echo Starting Cloud Orchestrator...
    start /B python watcher/orchestrator_cloud.py ^> data/Logs/cloud_orchestrator.log 2^>^&1

    echo Starting Cloud Watchers...
    start /B python watcher/gmail_watcher.py ^> data/Logs/gmail_watcher.log 2^>^&1
    start /B python watcher/facebook_watcher.py ^> data/Logs/facebook_watcher.log 2^>^&1
    start /B python watcher/instagram_watcher.py ^> data/Logs/instagram_watcher.log 2^>^&1
    start /B python watcher/x_watcher.py ^> data/Logs/x_watcher.log 2^>^&1

    echo Starting Cloud Watchdog...
    start /B python watchdog_cloud.py ^> data/Logs/watchdog_cloud.log 2^>^&1

    echo Cloud system started.
    echo Check logs in data/Logs/ directory

) else if "%1"=="local" (
    echo Starting Local Executive System...
    echo Environment: %VAULT_ENVIRONMENT%

    cd Platinum-Tier
    echo Starting Local Executive Agent...
    start /B python agents/agent-local-executive.py ^> data/Logs/local_executive.log 2^>^&1

    echo Starting Local Watchers...
    start /B python watcher/whatsapp_watcher.py ^> data/Logs/whatsapp_watcher.log 2^>^&1

    echo Starting Local Watchdog...
    start /B python watchdog_local.py ^> data/Logs/watchdog_local.log 2^>^&1

    echo Local system started.
    echo Check logs in data/Logs/ directory

) else if "%1"=="demo" (
    echo Running Platinum Gate Demo Test...
    cd Platinum-Tier
    python demo_test.py --clean

) else (
    echo Usage:
    echo   %0 cloud    - Start Cloud Executive system
    echo   %0 local    - Start Local Executive system
    echo   %0 demo     - Run Platinum Gate demo test
    echo.
    echo Make sure to set VAULT_ENVIRONMENT=cloud or VAULT_ENVIRONMENT=local
    echo before starting the appropriate system.
)