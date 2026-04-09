// ecosystem.config.cjs — PM2 configuration for Platinum Tier Local Agent
// This runs on the laptop and manages ALL watchers + full execution
//
// Usage:
//   pm2 start ecosystem.config.cjs    # start both processes
//   pm2 save                          # persist process list
//   pm2 startup                       # survive reboots (run generated command as admin)
//   pm2 logs                          # tail all logs
//   pm2 monit                         # interactive dashboard
//
// Architecture: 2 PM2 processes
//   platinum-local-orchestrator — Python process; manages ALL Python watchers as threads:
//                        FilesystemWatcher, ApprovalWatcher, GmailWatcher,
//                        LinkedInWatcher, FacebookWatcher, InstagramWatcher, TwitterWatcher.
//                        JitterSchedulers for all 4 social platforms run inside this process.
//   whatsapp-watcher   — Node.js Baileys process; independent WebSocket — no Python overlap.

const path = require("path");

// Absolute path to level-platinum/local/
const LOCAL_ROOT = __dirname;

// Python interpreter inside the uv-managed venv.
// On Windows: .venv\Scripts\python.exe
// On Linux/macOS: .venv/bin/python
const PYTHON =
  process.platform === "win32"
    ? path.join(LOCAL_ROOT, ".venv", "Scripts", "python.exe")
    : path.join(LOCAL_ROOT, ".venv", "bin", "python");

// Log directory — inside the Obsidian vault
const LOGS = path.join(LOCAL_ROOT, "..", "AI_Employee_Vault", "Logs");

module.exports = {
  apps: [
    // ─────────────────────────────────────────────────────
    //  Process 1: platinum-local-orchestrator
    //  Full execution mode — watchdog on /Needs_Action,
    //  dispatches skills via claude --print, starts ALL Python watchers
    //  as internal threads, merges cloud status into Dashboard.md,
    //  executes approved actions via MCP + Playwright.
    // ─────────────────────────────────────────────────────
    {
      name: "platinum-local-orchestrator",
      script: path.join(LOCAL_ROOT, "orchestrator.py"),
      interpreter: PYTHON,
      cwd: LOCAL_ROOT,

      // Restart policy
      autorestart: true,
      restart_delay: 3000,
      max_restarts: 10,
      min_uptime: "10s",
      watch: false,

      // Log files
      out_file: path.join(LOGS, "pm2_local_stdout.log"),
      error_file: path.join(LOGS, "pm2_local_error.log"),
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      merge_logs: true,

      // Environment — FULL EXECUTION MODE (no CLOUD_DRAFT_ONLY)
      env: {
        PYTHONUNBUFFERED: "1",
        PYTHONIOENCODING: "utf-8",
        FTE_AUTOMATED_DISPATCH: "1",
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
      script: path.join(LOCAL_ROOT, "whatsapp_watcher.js"),
      interpreter: "node",
      cwd: LOCAL_ROOT,

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

// NOTE: All Python watchers (Gmail, LinkedIn, Facebook, Instagram, Twitter,
// Filesystem, Approval) are managed as daemon threads inside platinum-local-orchestrator.
// They are NOT separate PM2 processes. See orchestrator.py init_watchers().
