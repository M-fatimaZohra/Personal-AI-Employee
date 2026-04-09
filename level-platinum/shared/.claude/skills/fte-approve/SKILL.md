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
   - ✅ `type` is a recognized action type: `email_reply`, `linkedin_post`, `whatsapp_reply`, `social_post`, `odoo_invoice`, `manual_review`
   - ✅ `expires_at` is in the future (not expired)
   - ✅ All required fields present for this action type:
     - `email_reply`: needs `to`, `subject`
     - `linkedin_post`: needs content in body
   - If ANY check fails: update status to `validation_failed`, move to Done, log error, skip

3. **Execute by action type**:

   **`social_post`** actions:
   - Read `platform` field: `facebook`, `instagram`, or `twitter`
   - Read post content from file body (after `## Post Content`)
   - Read `image_path` from frontmatter (Instagram only — skip IG post if missing)
   - Execute via Python Playwright poster (same pattern as LinkedIn — NO MCP):
     - **Facebook**: Run via Bash:
       ```
       cd level-gold && uv run python facebook_poster.py --approval-file "<filename>" --content "<post_content>"
       ```
     - **Instagram**: Run via Bash (requires image_path in frontmatter):
       ```
       cd level-gold && uv run python instagram_poster.py --approval-file "<filename>" --content "<post_content>" --image-path "<image_path>"
       ```
       If `image_path` is missing or file does not exist: log error, move to Done with status `skipped_no_image`
     - **Twitter**: Run via Bash:
       ```
       cd level-gold && uv run python twitter_poster.py --approval-file "<filename>" --content "<post_content>"
       ```
       Content auto-truncated to 280 chars by the poster if over limit.
   - Each poster opens a real browser, types content character-by-character, and submits.
   - On success: poster moves approval file to Done/ automatically.
   - Each platform is independent — one failing does NOT stop others
   - Log result per platform

   **`odoo_action`** actions (created by fte-plan for individual Odoo steps):
   - Read `action` field from frontmatter: `create_partner` or `create_invoice`
   - Read `plan_file` from frontmatter — you will need to update it after execution
   - **If `action: create_partner`**:
     - Extract partner details from the `## Partner Details` table: name, email, is_company
     - Call `mcp__odoo__create_partner` with `name`, `email`, `is_company`, `approval_file: <current approval filename>`
     - `approval_file` = filename of the current approval file — required by HITL gate
     - On success: note the returned `partner_id` for use in the next step
     - Update `plan_file` in Plans/: mark step containing "Create partner" as `[x]`, set `status: in_progress`, add note with partner_id
     - Set approval file `status: executed`, move to Done
     - On MCP failure: set `status: failed` in approval file, move to Done (do NOT stay in Approved)
   - **If `action: create_invoice`**:
     - Extract invoice details: partner_id, amount, description, due_date
     - Call `mcp__odoo__create_invoice` with those fields
     - On success: mark plan step `[x]`, set plan `status: in_progress`
     - Set approval file `status: executed`, move to Done
     - On MCP failure: set `status: failed`, move to Done

   **`odoo_invoice`** actions (invoice request approved by user):
   - Read the approval file fully — extract the line items table from `## Requested Services / Products`
   - Extract: `client_name`, `from` (email), `subject`, and each row of the table (service, qty, unit_price, subtotal)
   - Check all prices are filled in (no "TBD" remaining) — if any TBD found: set `execution_result: incomplete_pricing`, move to Done with a note "TBD prices not filled in — re-approve after editing"
   - Compute: `total_amount` = sum of all subtotals; `description` = comma-joined service names; `due_date` = today + 30 days (ISO YYYY-MM-DD)

   - **Step A — Create Odoo partner**:
     - Call `mcp__odoo__create_partner` with `name: <client_name>`, `email: <from email address only, strip display name>`, `approval_file: <approval filename>`
     - `approval_file` = the filename of the current approval file (e.g. `APPROVAL_invoice_request_19cc98ef.md`) — required by HITL gate
     - Save the returned `partner_id` integer for Step B
     - If it fails: log error, set `execution_result: odoo_partner_failed`, move to Done — do NOT retry automatically

   - **Step B — Create Odoo invoice**:
     - Call `mcp__odoo__create_invoice` with these exact parameters:
       - `partner_id`: integer returned from Step A
       - `amount`: total_amount (number, e.g. 300)
       - `description`: single string of services (e.g. "Full-Stack Website Development (3-page)")
       - `due_date`: ISO date string YYYY-MM-DD (30 days from today)
       - `approval_file`: the approval filename (e.g. `APPROVAL_invoice_request_19cc98ef.md`)
     - NOTE: Do NOT pass `lines`, `partner_name`, or `partner_email` — the MCP tool does not accept these
     - If MCP call fails: log error, set `execution_result: odoo_invoice_failed`, move to Done with error note
     - On success: save `invoice_number` and `invoice_id` from the response

   - **Step C — Send confirmation email to client**:
     - Draft: "Hi [client_name], your invoice [invoice_number] for [description] ($[amount]) has been created and is due [due_date]. We'll be in touch shortly."
     - Call `mcp__email__send_email` with `to: <from email>`, `subject: "Invoice [invoice_number] — [description]"`, `body: <draft>`
     - If email MCP fails: log, add manual send note to file, continue (do not block)
   - Log all 3 steps with outcomes

   **`manual_review`** actions:
   - These are notifications only — no automated action to take
   - Mark `status: acknowledged`, move to Done
   - Log: `{"action":"manual_review_acknowledged","actor":"fte-approve","details":"User acknowledged manual review item"}`

   **`email_reply`** actions:
   - Read the draft content from the approval file body (after `## Draft Reply`)
   - Note: The actual send is performed by the Email MCP server (`mcp__email__send_email`)
   - If MCP is available: call `mcp__email__send_email` with `to`, `subject`, `body` parameters
   - If `mcp__email__send_email` throws or returns an error:
     - Log the failure:
       ```json
       {"timestamp":"<ISO>","action":"mcp_error","actor":"fte-approve","source":"mcp__email__send_email","result":"error","details":"<error message>"}
       ```
     - Write a manual fallback note to the approval file body:
       ```
       ACTION REQUIRED: MCP send failed. Open your email client and send manually:
       To: <to>
       Subject: <subject>
       Body: <content>
       ```
     - Set `execution_result: manual_required` in the approval file frontmatter
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
   status: executed     # or executed_manual, validation_failed, failed, odoo_invoice_failed
   executed_at: <ISO timestamp>
   executed_by: fte-approve
   execution_result: <success | failed | manual_required>
   ```

5. **Move the approval file** to `AI_Employee_Vault/Done/`:
   Move: `AI_Employee_Vault/Approved/APPROVAL_*.md` → `AI_Employee_Vault/Done/`

   **CRITICAL — ALWAYS move to Done, even on failure.** If the file stays in /Approved, the orchestrator will re-dispatch fte-approve on every 10-second tick, creating duplicate Odoo invoices or duplicate emails. On failure: set `status: failed` in frontmatter, write the error in the body, then move to Done. The user can re-trigger manually if needed.

6. **Update the trigger file** (if `trigger_file` is in frontmatter):
   - Find the file in `Needs_Action/` or `Plans/` (search recursively with `**/*.md`)
   - Update its frontmatter: `status: done`, `completed_at: <ISO>`
   - If in `Needs_Action/`, move it to `Done/`
   - If in `Plans/`: check off the executed step; if ALL steps are now `[x]`, set `status: complete` and move the plan file to `Done/` as well
   - Also move any related `ODOO_*.md` or `ATTACHMENT_EXTRACT_*.md` from `Needs_Action/` to `Done/` if they reference this plan (search recursively)

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
