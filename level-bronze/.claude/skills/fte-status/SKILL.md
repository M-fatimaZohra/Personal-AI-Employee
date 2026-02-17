---
name: fte-status
description: Report the AI Employee system health. Shows watcher status, pending item count, folder sizes, and last activity timestamp. Use when the user asks about system status or health.
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Bash(ls *), Bash(wc *)
---

# System Status Report

You are the `bronze-fte` AI Employee. Report system health.

## Steps

1. **Count files** in each vault folder:
   - `AI_Employee_Vault/Needs_Action/*.md` — pending items
   - `AI_Employee_Vault/Done/*.md` — completed items
   - `AI_Employee_Vault/Inbox/*` — inbox items
   - `AI_Employee_Vault/Drop_Box/*` — unprocessed drops

2. **Read the current Dashboard** at `AI_Employee_Vault/Dashboard.md` to check watcher status (look for "Online" or "Offline").

3. **Read the most recent log file** in `AI_Employee_Vault/Logs/` (sorted by name, last file). Get the last entry's timestamp to show "last activity."

4. **Update `AI_Employee_Vault/Dashboard.md`** System Status section with current counts and timestamps.

5. **Log the action**: Append to `AI_Employee_Vault/Logs/YYYY-MM-DD.json`:
   ```json
   {"timestamp":"<ISO>","action":"skill_executed","actor":"fte-status","source":"vault","destination":"Dashboard.md","result":"success","details":"Status check: N pending, M done"}
   ```

6. **Report to the user** in this format:

   ```
   ## AI Employee Health Report
   - Watcher: [Online/Offline] (last check: <timestamp>)
   - Pending items: N
   - Completed items: M
   - Inbox: X
   - Drop Box: Y (unprocessed)
   - Last activity: <timestamp from logs>
   ```
