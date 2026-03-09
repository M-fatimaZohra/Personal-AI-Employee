---
name: fte-audit
description: Generate a weekly CEO Business Performance Briefing. Queries Odoo for 7-day financial summary, scans operational logs for task completion rates, detects bottlenecks, reads Business_Goals.md for goal progress, and includes a social media section (graceful "not configured" if Phase 2B not yet deployed). Writes CEO_BRIEFING_YYYY-MM-DD.md to /Plans. Triggered by Task Scheduler every Sunday at 09:00 or manually.
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Write
argument-hint: "[optional: YYYY-MM-DD to generate briefing for a specific week-end date]"
---

# Generate CEO Weekly Business Performance Briefing — Gold FTE

You are the `gold-fte` AI Employee. Generate a comprehensive weekly CEO briefing that combines financial, operational, and strategic insights.

## Context

- `$ARGUMENTS`: Optional ISO date (YYYY-MM-DD) for week-end date. Defaults to today.
- The briefing covers the **7-day period ending on the target date**.
- Social media section uses progressive enhancement — shows live data if Phase 2B is deployed, gracefully shows "not configured" if not.

---

## Steps

### 1. Determine Target Date and Week Range

- If `$ARGUMENTS` contains a date (YYYY-MM-DD) → use that as `week_end_date`
- Otherwise → use today's date as `week_end_date`
- Compute `week_start_date` = `week_end_date` minus 6 days
- Week label: `YYYY-WNN` (ISO week number)

### 2. Check for Existing CEO Briefing

- Glob `AI_Employee_Vault/Plans/CEO_BRIEFING_<week_end_date>*.md`
- If found: report the existing path and ask if you should regenerate
- Otherwise: proceed

### 3. Gather Intelligence

#### a) Financial Summary — Odoo Weekly (T034 + T035)

Call `mcp__odoo__list_transactions` twice:

**Revenue** (paid invoices this week):
```
start_date: week_start_date
end_date: week_end_date
type: "invoice"
```
- Sum `amount` for all results (these are posted invoices — revenue recognised)
- Count unique partners (customers billed this week)

**Expenses** (paid bills this week):
```
start_date: week_start_date
end_date: week_end_date
type: "bill"
```
- Sum `amount` for all results
- List top 3 vendors by amount

Also call `mcp__odoo__get_financial_summary` (no args) for the **month-to-date snapshot**:
- Outstanding invoices count + total
- Overdue invoices — flag any > 0

If Odoo unreachable: show `⚠️ Odoo unavailable — run docker compose up -d in level-gold/` and continue.

#### b) Operational Metrics — Log Analysis (T036)

Read ALL log files in `AI_Employee_Vault/Logs/` dated within the past 7 days (`YYYY-MM-DD.json` where date >= week_start_date):

Count these action types from the JSON lines:
- `emails_processed`: lines where `"action": "email_triaged"` or `"action": "email_replied"`
- `messages_triaged`: lines where `"action": "whatsapp_triaged"` or `"action": "whatsapp_replied"`
- `approvals_executed`: lines where `"result": "success"` and actor is `"ApprovalWatcher"` or `"fte-approve"`
- `plans_completed`: lines where `"action": "plan_completed"` or `"action": "skill_executed"` with result `"success"`
- `errors_total`: lines where `"result": "error"`
- `linkedin_posts`: lines where `"action": "linkedin_post_success"`

#### c) Task Completion Rate (T036)

Count files in `AI_Employee_Vault/Done/` created within the past 7 days:
- Use Glob `AI_Employee_Vault/Done/*.md` — count all (as proxy for completed tasks)
- Count files currently in `AI_Employee_Vault/Needs_Action/` (pending)
- Completion rate = Done-this-week / (Done-this-week + Pending) × 100

#### d) Bottlenecks Detection (T037)

Read each file in `AI_Employee_Vault/Needs_Action/`:
- Parse YAML frontmatter — get `created_at` timestamp
- Flag items where `(now - created_at) > 48 hours` as **stalled**
- List: filename, type, age in hours, priority

Also scan recent log files for repeated errors (same `action` appearing with `"result": "error"` 3+ times).

#### e) Goal Progress (from Business_Goals.md)

- Read `AI_Employee_Vault/Business_Goals.md`
- If file doesn't exist: show "Business_Goals.md not found — create it to track goals"
- Otherwise: extract current targets and compare to this week's actuals:
  - Revenue target vs actual
  - Any explicit KPIs listed
  - Note progress as: On Track / Behind / Ahead

#### f) Social Media Section — Progressive Enhancement (Phase 2B)

**Detection logic** (do NOT error if missing — graceful degradation):
1. Glob `AI_Employee_Vault/Done/SOCIAL_FB_*.md` — count Facebook posts completed this week
2. Glob `AI_Employee_Vault/Done/SOCIAL_IG_*.md` — count Instagram posts completed this week
3. Glob `AI_Employee_Vault/Done/TWITTER_*.md` — count Twitter posts completed this week
4. Glob `AI_Employee_Vault/Needs_Action/SOCIAL_*.md` — count pending social tasks

If **all counts are 0 AND** no `social_media_watcher.py` exists in `level-gold/`:
→ Mark social section as `status: not_configured`
→ Show the graceful placeholder (see output format below)

If social watcher exists but counts are 0:
→ Show `status: configured_no_activity`

If any social files found:
→ Show actual counts per platform

#### g) Proactive Suggestions (T038)

Generate 3–5 ranked suggestions based on evidence found above:

**Priority logic**:
1. If ANY overdue invoices > 30 days → "Send payment demand letter to [client]" (URGENT)
2. If outstanding invoice count > 3 → "Schedule follow-up calls for N outstanding invoices"
3. If bottlenecks list > 2 items → "Review stalled tasks: [list top 2]"
4. If errors_total > 5 this week → "Investigate recurring error in [action] — N occurrences"
5. If linkedin_posts == 0 this week → "Run /fte-linkedin-draft to maintain posting cadence"
6. If Social Media not configured → "Deploy Phase 2B to enable social media monitoring and posting"
7. If Business_Goals.md missing → "Create Business_Goals.md to enable goal tracking in weekly briefings"

---

### 4. Write CEO Briefing (T039)

Write to `AI_Employee_Vault/Plans/CEO_BRIEFING_<week_end_date>.md`:

```yaml
---
type: ceo_briefing
generated_at: <ISO timestamp>
week_end: <YYYY-MM-DD>
week_start: <YYYY-MM-DD>
week_label: <YYYY-WNN>
status: unread
---

# CEO Weekly Business Performance Briefing
## Week of <Week Start> → <Week End>

---

## Executive Summary

<2-3 sentences: this week's financial performance, top operational highlight, most urgent action needed>

---

## Financial Performance (T034 + T035)

### This Week
| Metric | Amount | Count |
|--------|--------|-------|
| Revenue (invoices issued) | $X | N invoices |
| Expenses (bills recorded) | $X | N bills |
| Net (Revenue − Expenses) | $X | — |

### Top Expenses This Week
1. [Vendor name] — $X
2. [Vendor name] — $X
3. [Vendor name] — $X

### Month-to-Date Snapshot (Odoo)
- 💰 Revenue MTD: **$X**
- 💸 Expenses MTD: **$X**
- 📄 Outstanding: **N invoices**, $X total
- ⚠️ Overdue: **N invoices**, $X total *(flag if N > 0 — requires immediate action)*

---

## Operational Performance (T036)

| Metric | Count |
|--------|-------|
| Emails processed | N |
| Messages triaged | N |
| Approvals executed | N |
| LinkedIn posts published | N |
| Errors encountered | N |
| Tasks completed (Done/) | N |
| Tasks pending (Needs_Action/) | N |
| Completion rate | N% |

---

## Goal Progress

| Goal | Target | Actual | Status |
|------|--------|--------|--------|
| (from Business_Goals.md) | | | On Track / Behind / Ahead |

*(If Business_Goals.md not found: "⚠️ No goals file found — create AI_Employee_Vault/Business_Goals.md to track KPIs")*

---

## Bottlenecks & Stalled Items (T037)

*(Items in Needs_Action older than 48 hours)*

| Item | Type | Age | Priority |
|------|------|-----|----------|
| (filename) | EMAIL_ / WHATSAPP_ / FILE_ | Xh | high/urgent |

*(If none: "✅ No stalled items — inbox clear")*

### Recurring Errors This Week
| Error Action | Occurrences |
|-------------|-------------|
| (action name) | N times |

*(If none: "✅ No recurring errors detected")*

---

## Social Media Performance (Phase 2B)

<!-- PROGRESSIVE ENHANCEMENT: This section auto-populates when social_media_watcher.py is deployed -->

*(If not configured):*
```
⚙️ Social Media Monitoring — Not Yet Configured

Phase 2B deployment required to enable:
  • Facebook post scheduling and engagement tracking
  • Instagram post scheduling and engagement tracking
  • Twitter/X post scheduling and engagement tracking

To activate: run each watcher with --setup flag
  LI_HEADLESS=false uv run python facebook_watcher.py --setup
  LI_HEADLESS=false uv run python instagram_watcher.py --setup
  LI_HEADLESS=false uv run python twitter_watcher.py --setup
```

*(If configured with activity):*
| Platform | Posts Published | Posts Pending |
|----------|----------------|---------------|
| Facebook | N | N |
| Instagram | N | N |
| Twitter/X | N | N |

---

## Proactive Suggestions (T038)

*(Ranked by urgency, evidence-based)*

1. 🔴 [URGENT] (if overdue invoices > 30 days) Send payment demand to [client] — invoice [ID] is [N] days overdue ($X)
2. 🟡 [HIGH] ...
3. 🟢 [NORMAL] ...

---

## System Health

- Odoo: ✅ connected / ⚠️ unavailable
- Last log entry: <timestamp>
- Watchers: <N>/5 online

---

*Generated by gold-fte | Next briefing: <next Sunday date>*
```

### 5. Update Dashboard (T040)

In `AI_Employee_Vault/Dashboard.md`, **prepend** to the Recent Activity table:
```
| <ISO timestamp> | ✅ ceo_briefing_ready | fte-audit | Plans/CEO_BRIEFING_<date>.md — N suggestions, $X revenue |
```

Also update the HITL Queue section to reflect the new briefing is ready:
```
📊 **CEO Briefing ready**: `Plans/CEO_BRIEFING_<week_end_date>.md` — open in Obsidian
```

### 6. Log

Append to `AI_Employee_Vault/Logs/<YYYY-MM-DD>.json`:
```json
{"timestamp":"<ISO>","action":"skill_executed","actor":"fte-audit","source":"vault","destination":"Plans/CEO_BRIEFING_<date>.md","result":"success","details":"CEO briefing generated: $X revenue, N bottlenecks, N suggestions | social: <configured|not_configured>"}
```

### 7. Report to User

Print:
```
✅ CEO Briefing generated: Plans/CEO_BRIEFING_<week_end_date>.md

Executive Summary:
<paste the 2-3 sentence executive summary here>

Top Actions:
1. <suggestion 1>
2. <suggestion 2>
3. <suggestion 3>

Open in Obsidian for full details.
```
