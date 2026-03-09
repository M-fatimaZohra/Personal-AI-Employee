---
name: fte-triage
description: Triage all items in the AI Employee vault's Needs_Action folder. Handles EMAIL_, MSG_, WHATSAPP_, LINKEDIN_NOTIF_, SOCIAL_FB_, SOCIAL_IG_, TWITTER_, and FILE_ types. Classifies items, applies Company Handbook rules, updates priorities, and refreshes the Dashboard. Use when the user wants to classify or prioritize pending items.
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Write, Edit
argument-hint: "[optional: filename or type filter e.g. EMAIL_]"
---

# Triage Pending Items — Silver FTE

You are the `silver-fte` AI Employee. Triage all items in the vault's `/Needs_Action` folder.

## Context

Vault root: `AI_Employee_Vault/`
Action files can be:
- `EMAIL_<id>.md` — Gmail messages
- `WHATSAPP_<id>.md` — WhatsApp messages
- `LINKEDIN_NOTIF_<id>.md` — LinkedIn notifications
- `SOCIAL_FB_<id>.md` — Facebook comments/mentions/messages
- `SOCIAL_IG_<id>.md` — Instagram comments/mentions/DMs
- `TWITTER_<id>.md` — Twitter/X mentions/replies/DMs
- `FILE_<name>.md` — File system drops

## Steps

1. **Read the handbook** at `AI_Employee_Vault/Company_Handbook.md` — memorise all rules, urgency keywords, and auto-approve thresholds.

2. **List all files** in `AI_Employee_Vault/Needs_Action/` using Glob (`*.md`). If `$ARGUMENTS` is provided, filter to files matching that string.

3. **For each file**, read it fully and parse the YAML frontmatter. Extract: `type`, `status`, `priority`, `from`, `subject`, `keywords_matched`.

4. **Classify by type**:

   **EMAIL_ files** (`type: email`):
   - Check sender domain against handbook trusted/blocked lists
   - Keywords in subject: "invoice", "urgent", "payment", "contract" → priority: high
   - Keywords in subject: "unsubscribe", "newsletter", "notification" → priority: low
   - Unknown sender + financial keywords → flag for HITL review
   - Set `category`: client | vendor | personal | newsletter | unknown

   **WHATSAPP_ files** (`type: whatsapp_message`):
   - Check `keywords_matched` frontmatter field
   - Any urgent keyword present → priority: high
   - Set `category`: personal | business | unknown

   **LINKEDIN_NOTIF_ files** (`type: linkedin_notification`):
   - `notif_type: mention` → priority: high (someone mentioned you publicly)
   - `notif_type: comment` → priority: normal
   - `notif_type: connection` → priority: normal
   - Set `category`: professional_network

   **FILE_ files** (`type: file_drop`):
   - Check filename extension: .pdf/.docx → document, .csv/.xlsx → data, .py/.js → code, .png/.jpg → image
   - Set `category`: document | data | code | image | other

5. **Apply handbook rules** to each item:
   - For each rule in the handbook, check if it matches the item
   - If a rule applies: add `handbook_rule: <rule name>` to frontmatter and adjust priority accordingly
   - If the item violates a rule (e.g. blocked sender), set `status: flagged` and add `flag_reason`

6. **Update each file's frontmatter** with:
   - `priority`: urgent | high | normal | low (updated based on classification)
   - `category`: the detected category
   - `handbook_rule`: if applicable
   - `triaged_at`: current ISO timestamp
   - `processed_by`: fte-triage

   Use the Edit tool to modify ONLY the frontmatter section (between `---` markers).

7. **Rewrite `AI_Employee_Vault/Dashboard.md`** with:
   ```
   # AI Employee Dashboard
   _Last updated: <ISO timestamp>_

   ## System Status
   | Watcher | Status |
   |---------|--------|
   | FilesystemWatcher | Online / Offline |
   | GmailWatcher | Online / Offline |
   | WhatsAppWatcher | Online / Offline |
   | LinkedInWatcher | Online / Offline |
   | ApprovalWatcher | Online / Offline |

   ## Pending Actions
   | File | Type | Priority | Category |
   |------|------|----------|----------|
   (sorted: urgent > high > normal > low)

   ## Pending Approvals
   Count of files in AI_Employee_Vault/Pending_Approval/

   ## Recent Activity
   (last 10 log entries from Logs/YYYY-MM-DD.json)
   ```

8. **Log the action**: Append a JSON line to `AI_Employee_Vault/Logs/YYYY-MM-DD.json`:
   ```json
   {"timestamp":"<ISO>","action":"skill_executed","actor":"fte-triage","source":"Needs_Action","destination":"Dashboard.md","result":"success","details":"Triaged N items: E emails, M messages, F files"}
   ```

9. **Report to the user**: table of all triaged items with type, category, priority, and any handbook rules applied. Note any flagged items for immediate attention.

If `$ARGUMENTS` matches a specific filename, triage only that file and report its classification.
