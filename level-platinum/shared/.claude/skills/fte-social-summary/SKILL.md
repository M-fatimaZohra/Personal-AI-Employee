---
name: fte-social-summary
description: Generate a social media engagement summary across Facebook, Instagram, and Twitter/X. Reads vault files (Done/, Needs_Action/, Pending_Approval/) directly — no MCP layer (social media uses Python Playwright posters, not MCP). Updates Dashboard with social media row. Use for weekly review or on-demand status check.
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Write
argument-hint: "[optional: days N — look-back window, default 7]"
---

# Social Media Engagement Summary — Gold FTE

You are the `gold-fte` AI Employee. Generate a social media summary report.

## Context

- `$ARGUMENTS`: Optional "days N" to specify look-back window (default: 7 days)
- Summary covers: Facebook, Instagram, Twitter/X independently
- Data source: vault files only (Done/, Needs_Action/, Pending_Approval/) — direct file reads, no MCP

---

## Steps

### 1. Parse Look-Back Window

- If `$ARGUMENTS` contains "days N" → use N days
- Default: 7 days

### 2. File-Based Counts (primary data source — all social data lives in vault files)

Glob and count (search recursively with `**/*.md`):
- `AI_Employee_Vault/Done/SOCIAL_FB_*.md` — Facebook completed
- `AI_Employee_Vault/Done/SOCIAL_IG_*.md` — Instagram completed
- `AI_Employee_Vault/Done/TWITTER_*.md` — Twitter completed
- `AI_Employee_Vault/Needs_Action/**/SOCIAL_FB_*.md` — Facebook pending
- `AI_Employee_Vault/Needs_Action/**/SOCIAL_IG_*.md` — Instagram pending
- `AI_Employee_Vault/Needs_Action/**/TWITTER_*.md` — Twitter pending
- `AI_Employee_Vault/Pending_Approval/**/APPROVAL_social_*.md` — awaiting approval

### 3. Watcher Status Check

Check if the independent watcher scripts exist:
- `level-gold/facebook_watcher.py` exists → "configured"
- `level-gold/instagram_watcher.py` exists → "configured"
- `level-gold/twitter_watcher.py` exists → "configured"

Check session directories:
- `FB_SESSION_DIR` env var set AND directory exists → session valid
- `IG_SESSION_DIR` env var set AND directory exists → session valid
- `TWITTER_SESSION_DIR` env var set AND directory exists → session valid

### 4. Read LinkedIn Data (for comparison)

Count LinkedIn posts this week from Done/:
- `AI_Employee_Vault/Done/LINKEDIN_DRAFT_*.md` — completed LinkedIn posts

### 5. Generate Report

Print the summary:

```
📊 Social Media Summary — Last N Days

PLATFORM      PUBLISHED   PENDING   APPROVALS   SESSION
──────────────────────────────────────────────────────
Facebook      N posts     N tasks   N waiting   ✅/⚠️
Instagram     N posts     N tasks   N waiting   ✅/⚠️
Twitter/X     N posts     N tasks   N waiting   ✅/⚠️
LinkedIn      N posts     —         —           (via linkedin_watcher.py)
──────────────────────────────────────────────────────
TOTAL         N posts     N tasks   N waiting

Platform Status:
  FacebookWatcher:  ✅ configured / ⚠️ session not set up
  InstagramWatcher: ✅ configured / ⚠️ session not set up
  TwitterWatcher:   ✅ configured / ⚠️ session not set up

Recommended Actions:
  (if any session not set up) → Run setup commands
  (if pending tasks > 3) → Run /fte-triage to process social notifications
  (if no posts published) → Run /fte-social-post to draft new content
```

### 6. Update Dashboard

In `AI_Employee_Vault/Dashboard.md`, update or add the Social Media row in Inbox section.

### 7. Log

Append to `AI_Employee_Vault/Logs/<YYYY-MM-DD>.json`:
```json
{"timestamp":"<ISO>","action":"skill_executed","actor":"fte-social-summary","source":"vault","destination":"Dashboard.md","result":"success","details":"Social summary: FB=N, IG=N, TW=N posts published (last 7d)"}
```
