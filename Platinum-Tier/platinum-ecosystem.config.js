/**
 * PM2 Ecosystem Configuration — AI Employee Vault (Platinum Tier)
 *
 * Start all Platinum services:    pm2 start platinum-ecosystem.config.js
 * Check status:                   pm2 status
 * View logs:                      pm2 logs
 * Stop all:                       pm2 stop all
 * Restart all:                    pm2 restart all
 *
 * Production deployment with cloud/local separation:
 * - Orchestrator: Main process supervisor
 * - Cloud Orchestrator: 24/7 cloud executive agent
 * - Local Orchestrator: Local approval/execution agent
 * - All watchers: Social media, email, and action processors
 */

const path = require("path");
const fs = require("fs");

// Parse .env manually (no npm dependency needed)
const envPath = path.resolve(__dirname, ".env");
const envVars = {};
if (fs.existsSync(envPath)) {
  fs.readFileSync(envPath, "utf-8")
    .split("\n")
    .forEach((line) => {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) return;
      const eqIdx = trimmed.indexOf("=");
      if (eqIdx === -1) return;
      const key = trimmed.slice(0, eqIdx).trim();
      const val = trimmed.slice(eqIdx + 1).trim();
      envVars[key] = val;
    });
}

module.exports = {
  apps: [
    // ── Platinum Tier: Main Orchestrator ──────────────────────────────
    {
      name: "orchestrator",
      script: "orchestrator.py",
      interpreter: "python",
      cwd: __dirname,
      env: {
        ...envVars,
        VAULT_ENVIRONMENT: "cloud",
        DRY_RUN: "false"
      },
      autorestart: true,
      restart_delay: 15000,
      max_restarts: 5,
      watch: false,
      log_file: "data/Logs/pm2-orchestrator.log",
      error_file: "data/Logs/pm2-orchestrator-error.log",
      out_file: "data/Logs/pm2-orchestrator-out.log",
      merge_logs: true,
    },


    // ── Platinum Tier: Watchers ───────────────────────────────────────
    {
      name: "gmail-watcher",
      script: "watcher/gmail_watcher.py",
      interpreter: "python",
      cwd: __dirname,
      env: { ...envVars },
      autorestart: true,
      restart_delay: 10000,
      max_restarts: 10,
      watch: false,
      log_file: "data/Logs/pm2-gmail-watcher.log",
      error_file: "data/Logs/pm2-gmail-watcher-error.log",
      out_file: "data/Logs/pm2-gmail-watcher-out.log",
      merge_logs: true,
    },

    {
      name: "whatsapp-watcher",
      script: "watcher/whatsapp_watcher.py",
      interpreter: "python",
      args: "--headless --login-timeout 300",
      cwd: __dirname,
      env: { ...envVars },
      autorestart: true,
      restart_delay: 15000,
      max_restarts: 5,
      watch: false,
      log_file: "data/Logs/pm2-whatsapp-watcher.log",
      error_file: "data/Logs/pm2-whatsapp-watcher-error.log",
      out_file: "data/Logs/pm2-whatsapp-watcher-out.log",
      merge_logs: true,
    },

    {
      name: "linkedin-watcher",
      script: "watcher/linkedin_watcher.py",
      interpreter: "python",
      cwd: __dirname,
      env: { ...envVars },
      autorestart: true,
      restart_delay: 10000,
      max_restarts: 10,
      watch: false,
      log_file: "data/Logs/pm2-linkedin-watcher.log",
      error_file: "data/Logs/pm2-linkedin-watcher-error.log",
      out_file: "data/Logs/pm2-linkedin-watcher-out.log",
      merge_logs: true,
    },

    {
      name: "needs-action-watcher",
      script: "watcher/needs_action_watcher.py",
      interpreter: "python",
      cwd: __dirname,
      env: { ...envVars },
      autorestart: true,
      restart_delay: 5000,
      max_restarts: 15,
      watch: false,
      log_file: "data/Logs/pm2-needs-action-watcher.log",
      error_file: "data/Logs/pm2-needs-action-watcher-error.log",
      out_file: "data/Logs/pm2-needs-action-watcher-out.log",
      merge_logs: true,
    },

    {
      name: "hitl-watcher",
      script: "watcher/hitl_watcher.py",
      interpreter: "python",
      cwd: __dirname,
      env: { ...envVars },
      autorestart: true,
      restart_delay: 5000,
      max_restarts: 15,
      watch: false,
      log_file: "data/Logs/pm2-hitl-watcher.log",
      error_file: "data/Logs/pm2-hitl-watcher-error.log",
      out_file: "data/Logs/pm2-hitl-watcher-out.log",
      merge_logs: true,
    },

    {
      name: "scheduler",
      script: "watcher/scheduler.py",
      interpreter: "python",
      cwd: __dirname,
      env: { ...envVars },
      autorestart: true,
      restart_delay: 10000,
      max_restarts: 10,
      watch: false,
      log_file: "data/Logs/pm2-scheduler.log",
      error_file: "data/Logs/pm2-scheduler-error.log",
      out_file: "data/Logs/pm2-scheduler-out.log",
      merge_logs: true,
    },

    {
      name: "facebook-watcher",
      script: "watcher/facebook_watcher.py",
      interpreter: "python",
      cwd: __dirname,
      env: { ...envVars },
      autorestart: true,
      restart_delay: 10000,
      max_restarts: 10,
      watch: false,
      log_file: "data/Logs/pm2-facebook-watcher.log",
      error_file: "data/Logs/pm2-facebook-watcher-error.log",
      out_file: "data/Logs/pm2-facebook-watcher-out.log",
      merge_logs: true,
    },

    {
      name: "instagram-watcher",
      script: "watcher/instagram_watcher.py",
      interpreter: "python",
      cwd: __dirname,
      env: { ...envVars },
      autorestart: true,
      restart_delay: 10000,
      max_restarts: 10,
      watch: false,
      log_file: "data/Logs/pm2-instagram-watcher.log",
      error_file: "data/Logs/pm2-instagram-watcher-error.log",
      out_file: "data/Logs/pm2-instagram-watcher-out.log",
      merge_logs: true,
    },

    {
      name: "x-watcher",
      script: "watcher/x_watcher.py",
      interpreter: "python",
      cwd: __dirname,
      env: { ...envVars },
      autorestart: true,
      restart_delay: 10000,
      max_restarts: 10,
      watch: false,
      log_file: "data/Logs/pm2-x-watcher.log",
      error_file: "data/Logs/pm2-x-watcher-error.log",
      out_file: "data/Logs/pm2-x-watcher-out.log",
      merge_logs: true,
    },

    // ── Platinum Tier: Watchdogs ──────────────────────────────────────
    {
      name: "watchdog",
      script: "watchdog.py",
      interpreter: "python",
      cwd: __dirname,
      env: {
        ...envVars,
        VAULT_ENVIRONMENT: "both"
      },
      autorestart: true,
      restart_delay: 30000,
      max_restarts: 3,
      watch: false,
      log_file: "data/Logs/pm2-watchdog.log",
      error_file: "data/Logs/pm2-watchdog-error.log",
      out_file: "data/Logs/pm2-watchdog-out.log",
      merge_logs: true,
    },


    {
      name: "watchdog_local",
      script: "watchdog_local.py",
      interpreter: "python",
      cwd: __dirname,
      env: {
        ...envVars,
        VAULT_ENVIRONMENT: "local"
      },
      autorestart: true,
      restart_delay: 30000,
      max_restarts: 3,
      watch: false,
      log_file: "data/Logs/pm2-watchdog-local.log",
      error_file: "data/Logs/pm2-watchdog-local-error.log",
      out_file: "data/Logs/pm2-watchdog-local-out.log",
      merge_logs: true,
    },
  ],
};