// ecosystem.config.cjs — PM2 configuration for Platinum Tier Cloud Agent
// This runs on the Azure VM and manages ONLY the cloud orchestrator
//
// Usage:
//   pm2 start ecosystem.config.cjs    # start cloud orchestrator
//   pm2 save                          # persist process list
//   pm2 startup                       # survive reboots (run generated command)
//   pm2 logs                          # tail logs
//   pm2 monit                         # interactive dashboard
//
// Architecture: 1 PM2 process only (cloud orchestrator)
//   - Gmail watcher runs as thread inside orchestrator
//   - WhatsApp stays on local machine (device-bound session)
//   - Social media stays on local machine (Azure IPs = bot detection)

const path = require("path");

// Absolute path to cloud/
const CLOUD_ROOT = __dirname;

// Log directory
const LOGS = path.join(CLOUD_ROOT, "AI_Employee_Vault", "Logs");

module.exports = {
  apps: [
    {
      name: "platinum-cloud-orchestrator",
      script: path.join(CLOUD_ROOT, "orchestrator.py"),
      interpreter: "/home/ubuntu/.local/bin/uv",
      interpreter_args: "run python",
      cwd: CLOUD_ROOT,

      // Restart policy
      autorestart: true,
      restart_delay: 3000,
      max_restarts: 10,
      min_uptime: "10s",
      watch: false,
      max_memory_restart: "500M",

      // Log files
      out_file: path.join(LOGS, "pm2_cloud_stdout.log"),
      error_file: path.join(LOGS, "pm2_cloud_error.log"),
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      merge_logs: true,

      // Environment — CRITICAL: CLOUD_DRAFT_ONLY enforces draft-only mode
      env: {
        CLOUD_DRAFT_ONLY: "true",
        PYTHONUNBUFFERED: "1",
        PYTHONIOENCODING: "utf-8",
        FTE_AUTOMATED_DISPATCH: "1",
        // ccr binary lives in ~/.npm-global/bin — must be on PATH for dispatch_skill()
        PATH: "/home/ubuntu/.npm-global/bin:/home/ubuntu/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        // LLM routing handled by CCR (~/.claude-code-router/config.json)
        // No ANTHROPIC_* vars needed here — CCR manages OpenRouter auth
      },
    },
  ],
};

// NOTE: This config is for CLOUD AGENT ONLY.
// Local agent uses a separate ecosystem.config.cjs with all watchers + execution.
