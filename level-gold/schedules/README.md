# Schedules — Windows Task Scheduler Registration

This directory contains batch scripts for scheduled tasks. These complement the always-on PM2 processes (`run_watchers.py` + `orchestrator.py`) with time-based triggers.

## Scheduled Tasks Overview

| Script | Schedule | What It Does |
|--------|----------|-------------|
| `gmail_poll.bat` | Every 2 minutes | Single-shot Gmail poll (fallback if PM2 watcher not running) |
| `morning_briefing.bat` | Daily at 08:00 AM | Triggers `/fte-briefing` skill — generates your morning briefing in Obsidian |
| `weekly_review.bat` | Every Sunday at 09:00 AM | Triggers `/fte-linkedin-draft` skill — generates a LinkedIn post draft in `/Plans` |

---

## Registration Commands

> **Run all commands below in an elevated Command Prompt (Run as Administrator).**
> From the repo root — adjust `<ABSOLUTE_PATH_TO_YOUR_REPO>` to your actual path.

### Set your base path (do this once)

```cmd
set GOLD=<ABSOLUTE_PATH_TO_YOUR_REPO>\fte-Autonomus-employ\level-gold
```

---

### Task 1: Gmail Poll — Every 2 Minutes

```cmd
schtasks /create ^
  /tn "GoldFTE-GmailPoller" ^
  /tr "%GOLD%\schedules\gmail_poll.bat" ^
  /sc minute ^
  /mo 2 ^
  /ru "%USERNAME%" ^
  /f
```

**Verify it was created:**
```cmd
schtasks /query /tn "GoldFTE-GmailPoller" /v /fo LIST
```

**Run it manually to test:**
```cmd
schtasks /run /tn "GoldFTE-GmailPoller"
```

---

### Task 2: Morning Briefing — Daily at 08:00 AM

```cmd
schtasks /create ^
  /tn "GoldFTE-MorningBriefing" ^
  /tr "%GOLD%\schedules\morning_briefing.bat" ^
  /sc daily ^
  /st 08:00 ^
  /ru "%USERNAME%" ^
  /f
```

**Verify:**
```cmd
schtasks /query /tn "GoldFTE-MorningBriefing" /v /fo LIST
```

**Run manually:**
```cmd
schtasks /run /tn "GoldFTE-MorningBriefing"
```

---

### Task 3: Weekly Review — Every Sunday at 09:00 AM

```cmd
schtasks /create ^
  /tn "GoldFTE-WeeklyReview" ^
  /tr "%GOLD%\schedules\weekly_review.bat" ^
  /sc weekly ^
  /d SUN ^
  /st 09:00 ^
  /ru "%USERNAME%" ^
  /f
```

**Verify:**
```cmd
schtasks /query /tn "GoldFTE-WeeklyReview" /v /fo LIST
```

**Run manually:**
```cmd
schtasks /run /tn "GoldFTE-WeeklyReview"
```

---

## View All Gold FTE Tasks at Once

```cmd
schtasks /query /fo TABLE | findstr "GoldFTE"
```

---

## Remove Tasks (if needed)

```cmd
schtasks /delete /tn "GoldFTE-GmailPoller"   /f
schtasks /delete /tn "GoldFTE-MorningBriefing" /f
schtasks /delete /tn "GoldFTE-WeeklyReview"   /f
```

---

## Check Logs

Each script writes its own log file next to the `.bat` file:

```
schedules/
├── gmail_poll.log         ← Written after every poll
├── morning_briefing.log   ← Written after every briefing run
└── weekly_review.log      ← Written after every weekly run
```

View the last 20 lines of a log (PowerShell):

```powershell
Get-Content .\schedules\gmail_poll.log -Tail 20
```

---

## Architecture Note

### Why Both PM2 and Task Scheduler?

| Concern | PM2 | Task Scheduler |
|---------|-----|----------------|
| Always-on watchers | ✅ `run_watchers.py` — 24/7 | ❌ Not designed for this |
| Orchestrator heartbeat | ✅ `orchestrator.py` — 30s tick | ❌ Too frequent for Task Scheduler |
| Time-triggered briefings | ❌ No built-in cron | ✅ Daily 8 AM, Weekly Sunday |
| Crash recovery | ✅ Auto-restart | ⚠️ Only retries if configured |
| Survives reboot | ✅ `pm2 startup` | ✅ Built-in |

**PM2 is the primary process manager.** Task Scheduler handles the time-based triggers (morning briefing, weekly review) that PM2 doesn't do natively.

### Fallback Behavior

If `claude` CLI is not on PATH when Task Scheduler fires the `.bat` scripts, the scripts fall back to writing a trigger `.md` file in `/Needs_Action`. The orchestrator will detect it on its next 30-second tick and dispatch the appropriate skill. This means the briefing still runs — just with up to a 30-second delay.
