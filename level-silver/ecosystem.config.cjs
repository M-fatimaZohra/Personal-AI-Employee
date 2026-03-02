// ecosystem.config.js — PM2 process manager config for Silver FTE
// Usage:
//   pm2 start ecosystem.config.js    # start both processes
//   pm2 save                          # persist process list
//   pm2 startup                       # survive reboots (run the generated command as admin)
//   pm2 logs                          # tail all logs
//   pm2 monit                         # interactive dashboard
//   pm2 restart ecosystem.config.js  # rolling restart
//   pm2 delete ecosystem.config.js   # remove all processes

const path = require("path");

// Absolute path to level-silver/ — ensures .env and AI_Employee_Vault resolve
// correctly regardless of where PM2 was launched from.
const SILVER_ROOT = __dirname;

// Python interpreter inside the uv-managed venv.
// On Windows: .venv\Scripts\python.exe
// On Linux/macOS: .venv/bin/python
const PYTHON =
  process.platform === "win32"
    ? path.join(SILVER_ROOT, ".venv", "Scripts", "python.exe")
    : path.join(SILVER_ROOT, ".venv", "bin", "python");

// Log directory — inside the Obsidian vault so logs appear in the dashboard
const LOGS = path.join(SILVER_ROOT, "AI_Employee_Vault", "Logs");

module.exports = {
  apps: [
    // ─────────────────────────────────────────────────────
    //  Process 1: silver-orchestrator
    //  The autonomy engine — watchdog on /Needs_Action every 30 s,
    //  dispatches skills via claude --print, starts FS/Gmail/LinkedIn
    //  watchers internally. Logs every tick to orchestrator log.
    // ─────────────────────────────────────────────────────
    {
      name: "silver-orchestrator",
      script: path.join(SILVER_ROOT, "orchestrator.py"),
      interpreter: PYTHON,
      cwd: SILVER_ROOT,

      // Restart policy
      autorestart: true,
      restart_delay: 3000,
      max_restarts: 10,
      min_uptime: "10s",
      watch: false,

      // Log files
      out_file: path.join(LOGS, "pm2_stdout.log"),
      error_file: path.join(LOGS, "pm2_error.log"),
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      merge_logs: false,

      // Environment
      env: {
        PYTHONUNBUFFERED: "1",
        PYTHONIOENCODING: "utf-8",
      },
    },

    // ─────────────────────────────────────────────────────
    //  Process 2: whatsapp-watcher
    //  Node.js process — Baileys WebSocket (no browser, no CDP).
    //  Receives messages (event-driven) → writes WHATSAPP_*.md
    //  Watches /Approved/APPROVAL_WA_*.md via chokidar → sock.sendMessage()
    //  SIGINT/SIGTERM → sock.end() → graceful WebSocket teardown.
    // ─────────────────────────────────────────────────────
    {
      name: "whatsapp-watcher",
      script: path.join(SILVER_ROOT, "whatsapp_watcher.js"),
      interpreter: "node",
      cwd: SILVER_ROOT,

      // Restart policy — 10s delay prevents spam-login if internet cuts out
      autorestart: true,
      restart_delay: 10000,
      max_restarts: 10,
      min_uptime: "15s",
      watch: false,

      // Log files
      out_file: path.join(LOGS, "whatsapp_stdout.log"),
      error_file: path.join(LOGS, "whatsapp_error.log"),
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      merge_logs: false,

      // Environment
      env: {
        NODE_ENV: "production",
      },
    },
  ],
};
