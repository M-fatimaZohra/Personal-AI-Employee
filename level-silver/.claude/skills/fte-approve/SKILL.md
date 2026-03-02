---
name: fte-approve
description: Process approved items from the /Approved folder. Reads approval files, validates them, triggers the appropriate MCP action (email send, etc.), moves files to /Done, and updates the Dashboard. Called after the user moves files to /Approved in Obsidian.
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Write, Edit, Bash(mv *)
argument-hint: "[optional: APPROVAL_*.md filename]"
---

# Process Approved Actions — Silver FTE

You are the `silver-fte` AI Employee. Execute approved actions safely.

## MANDATORY: Validate Before Acting

**Always validate the approval file before executing any action. Never execute malformed or expired approvals.**

## Steps

1. **List approved files**: Glob `AI_Employee_Vault/Approved/APPROVAL_*.md`.
   - If `$ARGUMENTS` is provided, process only that file
   - Otherwise, process ALL files in `/Approved`
   - If no files found, report "No approved actions to process"

2. **For each approved file**, read it fully and validate:
   - ✅ Has valid YAML frontmatter (between `---` markers)
   - ✅ `status` is currently `pending` (not already `executed` or `rejected`)
   - ✅ `type` is a recognized action type: `email_reply`, `linkedin_post`, `whatsapp_reply`
   - ✅ `expires_at` is in the future (not expired)
   - ✅ All required fields present for this action type:
     - `email_reply`: needs `to`, `subject`
     - `linkedin_post`: needs content in body
   - If ANY check fails: update status to `validation_failed`, move to Done, log error, skip

3. **Execute by action type**:

   **`email_reply`** actions:
   - Read the draft content from the approval file body (after `## Draft Reply`)
   - Note: The actual send is performed by the Email MCP server (`mcp__email__send_email`)
   - If MCP is available: call `mcp__email__send_email` with `to`, `subject`, `body` parameters
   - If MCP is NOT available: write a clear note that the email needs manual sending:
     ```
     ACTION REQUIRED: Open your email client and send:
     To: <to>
     Subject: <subject>
     Body: <content>
     ```
   - Either way, record the outcome

   **`linkedin_post`** actions:
   - LinkedIn posting is handled automatically by the `ApprovalWatcher` + `JitterScheduler` pipeline
   - When this skill runs for a `linkedin_post`, the `ApprovalWatcher` has already scheduled or posted it
   - Verify the approval file frontmatter for `scheduled_at` or `posted_at` fields
   - If `posted_at` is present: mark as `executed` — post was sent by Playwright automation
   - If `scheduled_at` is present: mark as `scheduled` — orchestrator will post at that time
   - If neither field is present (edge case): write a note with post content for manual copy-paste and mark `executed_manual`

   **`whatsapp_reply`** actions:
   - WhatsApp replies are handled automatically by the `ApprovalWatcher` + `whatsapp_sender.py` pipeline
   - If this skill runs for a `whatsapp_reply`, check the approval file for `sent_at` field
   - If `sent_at` is present: mark as `executed` — reply was sent by Playwright automation
   - If not present (edge case): write a note with the reply text for manual sending and mark `executed_manual`

4. **Update the approval file's frontmatter**:
   ```yaml
   status: executed     # or executed_manual, validation_failed
   executed_at: <ISO timestamp>
   executed_by: fte-approve
   execution_result: <success | failed | manual_required>
   ```

5. **Move the approval file** to `AI_Employee_Vault/Done/`:
   Move: `AI_Employee_Vault/Approved/APPROVAL_*.md` → `AI_Employee_Vault/Done/`

6. **Update the trigger file** (if `trigger_file` is in frontmatter):
   - Find the file in `Needs_Action/` or `Plans/`
   - Update its frontmatter: `status: done`, `completed_at: <ISO>`
   - If in `Needs_Action/`, move it to `Done/`
   - If in `Plans/`, check off the executed step

7. **Update `AI_Employee_Vault/Dashboard.md`**:
   - Decrement pending approvals count
   - Add to recent activity: "Executed: <action type> (<to / post title>)"

8. **Log**: Append to `AI_Employee_Vault/Logs/YYYY-MM-DD.json`:
   ```json
   {"timestamp":"<ISO>","action":"skill_executed","actor":"fte-approve","source":"Approved/<file>","destination":"Done/<file>","result":"success","details":"Executed: <type> | to=<recipient> | result=<outcome>"}
   ```

9. **Report**:
   - List each approved action and its outcome
   - For `executed_manual` items: show the content that needs to be sent/posted
   - "Dashboard updated. N approvals processed."
