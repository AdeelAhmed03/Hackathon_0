/**
 * PM2 Ecosystem Configuration — AI Employee Vault (Silver Tier)
 *
 * Start all watchers:    pm2 start ecosystem.config.js
 * Check status:          pm2 status
 * View logs:             pm2 logs
 * Stop all:              pm2 stop all
 * Restart all:           pm2 restart all
 *
 * LinkedIn auth (run ONCE before first start):
 *   python watcher/linkedin_auth.py
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
    // ── 1. Gmail Watcher ────────────────────────────────────────────
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

    // ── 2. WhatsApp Watcher ─────────────────────────────────────────
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

    // ── 3. LinkedIn Watcher ─────────────────────────────────────────
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

    // ── 4. Needs Action Watcher ─────────────────────────────────────
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

    // ── 5. HITL Watcher ─────────────────────────────────────────────
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

    // ── 6. Scheduler ────────────────────────────────────────────────
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
  ],
};
