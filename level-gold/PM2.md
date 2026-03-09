# PM2 — Process Immortality for Silver FTE

PM2 keeps `run_watchers.py` and `orchestrator.py` alive 24/7 — auto-restarts on crash, survives reboots.

## Install

```bash
npm install -g pm2
```

## Start

```bash
# From level-silver/
pm2 start ecosystem.config.js
```

## Persist Across Reboots

```bash
pm2 save                 # save current process list to ~/.pm2/dump.pm2
pm2 startup              # print the OS-level startup command — run it as Administrator
```

## Daily Commands

```bash
pm2 status               # see both processes: online / stopped / errored
pm2 logs                 # tail all logs (Ctrl+C to exit)
pm2 logs silver-orchestrator --lines 50   # last 50 lines for one process
pm2 monit                # live CPU/memory dashboard
pm2 restart ecosystem.config.js          # rolling restart both processes
pm2 stop ecosystem.config.js             # stop without removing
pm2 delete ecosystem.config.js           # stop + remove from list
```

## Recovery After PM2 List Loss

If `pm2 status` shows nothing (e.g. after `pm2 kill` or OS update):

```bash
pm2 resurrect            # restore from last pm2 save
```

## Log Files

Logs are written inside the vault so they appear alongside other activity:

| File | Contents |
|------|----------|
| `AI_Employee_Vault/Logs/pm2_stdout.log` | Orchestrator stdout |
| `AI_Employee_Vault/Logs/pm2_error.log` | Orchestrator stderr / exceptions |
| `AI_Employee_Vault/Logs/pm2_watchers_stdout.log` | Watchers stdout |
| `AI_Employee_Vault/Logs/pm2_watchers_error.log` | Watchers stderr / exceptions |
