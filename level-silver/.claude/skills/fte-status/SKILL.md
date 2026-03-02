---
name: fte-status
description: Report the AI Employee system health. Shows all 5 watcher statuses, pending items count by type, pending approvals count, active plans count, and last activity timestamp per watcher. Use when the user asks about system status, health, or what's pending.
disable-model-invocation: true
allowed-tools: Read, Glob, Grep
---

# System Status Report — Silver FTE

You are the `silver-fte` AI Employee. Report a comprehensive system health status.

## Steps

1. **Count files** in each vault folder using Glob:
   - `AI_Employee_Vault/Needs_Action/EMAIL_*.md` → pending emails
   - `AI_Employee_Vault/Needs_Action/WHATSAPP_*.md` → pending WhatsApp messages
   - `AI_Employee_Vault/Needs_Action/LINKEDIN_NOTIF_*.md` → pending LinkedIn notifications
   - `AI_Employee_Vault/Needs_Action/FILE_*.md` → pending file drops
   - `AI_Employee_Vault/Pending_Approval/*.md` → items awaiting HITL approval
   - `AI_Employee_Vault/Plans/*.md` → active plans
   - `AI_Employee_Vault/Done/*.md` → completed items
   - `AI_Employee_Vault/Rejected/*.md` → rejected items

2. **Check watcher status** by reading `AI_Employee_Vault/Dashboard.md`:
   - Parse the System Status table for each watcher's Online/Offline status
   - Note the last dashboard update timestamp

3. **Read the most recent log file** in `AI_Employee_Vault/Logs/` (the last file sorted alphabetically):
   - Get the timestamp of the LAST line to show "last activity"
   - Count total log entries today

4. **Check for expired approvals**: Read each file in `AI_Employee_Vault/Pending_Approval/`. Parse `expires_at` frontmatter. Flag any that are past expiry.

5. **Check for stalled plans**: Read each file in `AI_Employee_Vault/Plans/`. Count unchecked `- [ ]` items. Flag plans that haven't been updated in >24 hours.

6. **Report to the user** in this exact format:

   ```
   ## Silver FTE — System Health Report
   Generated: <ISO timestamp>

   ### Watcher Status
   | Watcher | Status | Last Seen |
   |---------|--------|-----------|
   | FilesystemWatcher | Online/Offline | <timestamp> |
   | GmailWatcher | Online/Offline | <timestamp> |
   | WhatsAppWatcher | Online/Offline | <timestamp> |
   | LinkedInWatcher | Online/Offline | <timestamp> |
   | ApprovalWatcher | Online/Offline | <timestamp> |

   ### Pending Items
   | Type | Count | Oldest |
   |------|-------|--------|
   | Emails (EMAIL_*) | N | <filename> |
   | WhatsApp (WHATSAPP_*) | N | <filename> |
   | LinkedIn (LINKEDIN_NOTIF_*) | N | <filename> |
   | File Drops (FILE_*) | N | <filename> |

   ### Approvals & Plans
   - Pending Approvals: N (X expired — need attention!)
   - Active Plans: N (Y stalled)
   - Items in Done: N total

   ### Activity
   - Last log entry: <timestamp>
   - Log entries today: N
   - Last dashboard update: <timestamp>

   ### Action Required
   (list any items needing immediate attention: expired approvals, stalled plans, high-priority items >6h old)
   ```

7. **Log the action**: Append to `AI_Employee_Vault/Logs/YYYY-MM-DD.json`:
   ```json
   {"timestamp":"<ISO>","action":"skill_executed","actor":"fte-status","source":"vault","destination":"stdout","result":"success","details":"Status: N pending, M approvals, P plans"}
   ```
