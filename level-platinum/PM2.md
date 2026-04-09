# PM2 — Process Immortality for Platinum Tier

PM2 keeps both Cloud and Local orchestrators alive 24/7 — auto-restarts on crash, survives reboots.

## Architecture

**Cloud Agent** (Azure VM):
- `platinum-cloud-orchestrator` — Gmail watcher + draft-only orchestrator

**Local Agent** (Laptop):
- `platinum-local-orchestrator` — All 7 watchers + approval execution
- `whatsapp-watcher` — Node.js WhatsApp bridge

## Install

```bash
npm install -g pm2
```

## Cloud Agent (on VM)

```bash
# From ~/cloud/
pm2 start ecosystem.config.cjs
pm2 save
sudo loginctl enable-linger ubuntu  # CRITICAL: survive SSH disconnect
```

## Local Agent (on laptop)

```bash
# From level-platinum/local/
pm2 start ecosystem.config.cjs
pm2 save
pm2 startup  # Windows: run as Administrator
```

## Daily Commands

```bash
pm2 status               # see all processes: online / stopped / errored
pm2 logs                 # tail all logs (Ctrl+C to exit)
pm2 logs platinum-cloud-orchestrator --lines 50
pm2 monit                # live CPU/memory dashboard
pm2 restart all          # rolling restart
pm2 stop all             # stop without removing
pm2 delete all           # stop + remove from list
```

## Recovery After PM2 List Loss

If `pm2 status` shows nothing (e.g. after `pm2 kill` or OS update):

```bash
pm2 resurrect            # restore from last pm2 save
```

## Log Files

Cloud logs: `~/AI_Employee_Vault/Logs/`
Local logs: `level-platinum/AI_Employee_Vault/Logs/`

Both write JSON Lines format (one JSON object per line) for auditability.
