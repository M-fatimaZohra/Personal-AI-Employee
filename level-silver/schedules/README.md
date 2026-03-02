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
> From the repo root — adjust `<ABSOLUTE_PATH_TO_LEVEL_SILVER>` to your actual path.

### Set your base path (do this once)

```cmd
set SILVER=D:\mirab_important\code\Q4_Era_of_New_AICLI\Hackathon\Hackathon2025-2026\Hackathon-0\fte-Autonomus-employ\level-silver
```

---

### Task 1: Gmail Poll — Every 2 Minutes

```cmd
schtasks /create ^
  /tn "SilverFTE-GmailPoller" ^
  /tr "%SILVER%\schedules\gmail_poll.bat" ^
  /sc minute ^
  /mo 2 ^
  /ru "%USERNAME%" ^
  /f
```

**Verify it was created:**
```cmd
schtasks /query /tn "SilverFTE-GmailPoller" /v /fo LIST
```

**Run it manually to test:**
```cmd
schtasks /run /tn "SilverFTE-GmailPoller"
```

---

### Task 2: Morning Briefing — Daily at 08:00 AM

```cmd
schtasks /create ^
  /tn "SilverFTE-MorningBriefing" ^
  /tr "%SILVER%\schedules\morning_briefing.bat" ^
  /sc daily ^
  /st 08:00 ^
  /ru "%USERNAME%" ^
  /f
```

**Verify:**
```cmd
schtasks /query /tn "SilverFTE-MorningBriefing" /v /fo LIST
```

**Run manually:**
```cmd
schtasks /run /tn "SilverFTE-MorningBriefing"
```

---

### Task 3: Weekly Review — Every Sunday at 09:00 AM

```cmd
schtasks /create ^
  /tn "SilverFTE-WeeklyReview" ^
  /tr "%SILVER%\schedules\weekly_review.bat" ^
  /sc weekly ^
  /d SUN ^
  /st 09:00 ^
  /ru "%USERNAME%" ^
  /f
```

**Verify:**
```cmd
schtasks /query /tn "SilverFTE-WeeklyReview" /v /fo LIST
```

**Run manually:**
```cmd
schtasks /run /tn "SilverFTE-WeeklyReview"
```

---

## View All Silver FTE Tasks at Once

```cmd
schtasks /query /fo TABLE | findstr "SilverFTE"
```

---

## Remove Tasks (if needed)

```cmd
schtasks /delete /tn "SilverFTE-GmailPoller"   /f
schtasks /delete /tn "SilverFTE-MorningBriefing" /f
schtasks /delete /tn "SilverFTE-WeeklyReview"   /f
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
