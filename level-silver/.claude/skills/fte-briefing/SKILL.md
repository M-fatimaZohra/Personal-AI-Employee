---
name: fte-briefing
description: Generate a Morning Briefing or Weekly Review report. Reads overnight emails, pending approvals, active plans, and recent activity. Writes BRIEFING_<date>.md to /Plans with a prioritised summary and suggested actions. Triggered by Task Scheduler at 8 AM daily or manually.
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Write
argument-hint: "[optional: morning | weekly | custom-date YYYY-MM-DD]"
---

# Generate Briefing — Silver FTE

You are the `silver-fte` AI Employee. Generate an executive briefing for the user.

## Context

Briefing types (determined by `$ARGUMENTS` or default to `morning`):
- `morning`: daily briefing — overnight activity + today's priorities
- `weekly`: Sunday weekly review — week's performance + LinkedIn draft trigger

## Steps

1. **Determine briefing type**:
   - `$ARGUMENTS` contains "weekly" → generate weekly review
   - `$ARGUMENTS` contains a date (YYYY-MM-DD) → briefing for that date
   - Default → morning briefing for today

2. **Check for existing briefing**: Glob `AI_Employee_Vault/Plans/BRIEFING_<date>*.md`.
   - If found: report the existing path and ask if you should regenerate
   - Otherwise: proceed with generation

3. **Gather intelligence** (read all sources):

   **a) Pending items in Needs_Action**:
   - Count by type: EMAIL_, MSG_, WHATSAPP_, LINKEDIN_NOTIF_, FILE_
   - List highest-priority items (urgent + high)
   - Note any items older than 6 hours

   **b) Pending Approvals**:
   - Count files in `AI_Employee_Vault/Pending_Approval/`
   - Read each: get `type`, `to`/`subject`, `expires_at`
   - Flag any expiring within 4 hours

   **c) Active Plans**:
   - Count files in `AI_Employee_Vault/Plans/` (exclude BRIEFING_ and LINKEDIN_DRAFT_)
   - For each plan: count unchecked steps, check last-modified date
   - Flag stalled plans (no progress in >12h)

   **d) Recent activity (Logs)**:
   - Read last 20 entries from most recent `AI_Employee_Vault/Logs/YYYY-MM-DD.json`
   - Summarise: N actions executed, N errors, N approvals processed

   **e) For weekly briefing only**:
   - Read ALL log files from the past 7 days
   - Count: emails processed, messages triaged, approvals executed, plans completed
   - Read `AI_Employee_Vault/Business_Goals.md` for goal progress context

4. **Write the briefing** to `AI_Employee_Vault/Plans/BRIEFING_<YYYY-MM-DD>.md`:

   **Morning Briefing format**:
   ```yaml
   ---
   type: briefing
   briefing_type: morning
   generated_at: <ISO timestamp>
   date: <YYYY-MM-DD>
   status: unread
   ---

   # Morning Briefing — <Day, Month DD, YYYY>

   ## Executive Summary

   <2-3 sentence overview: what happened overnight, what needs attention today>

   ## Overnight Activity
   - N new emails (<priority breakdown>)
   - N Telegram messages
   - N WhatsApp messages
   - N approvals processed while you slept

   ## Action Required Today

   ### Urgent (handle within 1 hour)
   | Item | Type | Age | Reason |
   |------|------|-----|--------|
   (items with priority: urgent or expiring approvals)

   ### High Priority (handle today)
   | Item | Type | Action |
   |------|------|--------|
   (items with priority: high)

   ### Pending Approvals
   | File | Type | Expires |
   |------|------|---------|
   (all items in Pending_Approval, sorted by expires_at)

   ## Active Plans
   | Plan | Steps Remaining | Status |
   |------|----------------|--------|

   ## Suggested Actions (in order)
   1. <Most urgent action>
   2. <Second action>
   3. <Third action>

   ## System Status
   - Watchers: <check Dashboard.md for online/offline>
   - Last log entry: <timestamp>
   ```

   **Weekly Review format** (use this when `$ARGUMENTS` is "weekly"):
   ```yaml
   ---
   type: briefing
   briefing_type: weekly
   generated_at: <ISO>
   week: <ISO week number>
   status: unread
   ---

   # Weekly Review — Week of <date>

   ## Week at a Glance
   - Emails processed: N
   - Messages triaged: N
   - Actions approved and executed: N
   - Plans completed: N
   - Plans in progress: N

   ## Goal Progress
   (from Business_Goals.md — current vs targets)

   ## Wins This Week
   (completed items from Done/ folder this week)

   ## Bottlenecks
   (any items stuck >24h, repeated errors in logs)

   ## Proactive Suggestions
   1. <Suggestion based on patterns — e.g. "3 vendor emails unanswered for 2 days">
   2. <Subscription or cost observation if relevant>
   3. <LinkedIn post opportunity based on this week's activity>

   ## This Week's LinkedIn Draft
   → Run `/fte-linkedin-draft weekly-review` to generate a post about this week's highlights
   ```

5. **Update `AI_Employee_Vault/Dashboard.md`**:
   - Add "📋 Briefing ready: Plans/BRIEFING_<date>.md" to Recent Activity section

6. **Log**: Append to `AI_Employee_Vault/Logs/YYYY-MM-DD.json`:
   ```json
   {"timestamp":"<ISO>","action":"skill_executed","actor":"fte-briefing","source":"vault","destination":"Plans/BRIEFING_<date>.md","result":"success","details":"<morning|weekly> briefing generated: N urgent, M approvals pending"}
   ```

7. **Report**:
   - "Briefing saved to `Plans/BRIEFING_<date>.md`"
   - Print the **Executive Summary** and **Action Required** sections directly
   - "Open in Obsidian for full details"
