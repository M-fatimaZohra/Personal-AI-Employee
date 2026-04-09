---
name: fte-process
description: Process a pending item from Needs_Action — reason about it, apply handbook rules, check or create a plan, update status, and move to Done. Handles EMAIL_, MSG_, WHATSAPP_, LINKEDIN_NOTIF_, and FILE_ types. Use when the user wants to process or complete a pending task.
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Write, Edit, Bash(mv *)
argument-hint: "[optional: filename to process]"
---

# Process Pending Item — Silver FTE

You are the `silver-fte` AI Employee. Process an item through the full pipeline.

## MANDATORY: HITL Gate

**Any action that touches the external world (send email, post content, make payment) MUST write an approval file to `/Pending_Approval` first. NEVER execute external actions directly.**

## Steps

1. **Select the item**:
   - If `$ARGUMENTS` is provided, find the matching file in `AI_Employee_Vault/Needs_Action/` (search recursively with `**/*.md`)
   - Otherwise, pick the highest-priority item (urgent → high → normal → low; oldest first within same priority)
   - If no items exist, report "No pending items" and stop

2. **Read the item** fully — frontmatter and body.

3. **Read `AI_Employee_Vault/Company_Handbook.md`** for applicable rules.

4. **Check for an existing plan** in `AI_Employee_Vault/Plans/` (search recursively with `**/*.md`):
   - Look for a file with `trigger_file: <current item name>` in frontmatter
   - If found: read it, identify the next unchecked step (`- [ ]`), and execute it
   - If NOT found and item is complex (email needing reply, multi-step task): invoke `/fte-plan` instructions mentally and create a plan first

5. **Reason about the item by type**:

   **EMAIL_ items** (forward to /fte-gmail-reply for draft, or classify and archive):
   - Read email body and subject
   - Determine: needs reply? needs forwarding? just archive?
   - If needs reply → do NOT draft here; note in the plan that `/fte-gmail-reply` should be invoked
   - If spam/newsletter → mark `status: archived`, move to Done

   **WHATSAPP_ items** (classify and action):
   - Read message text
   - Determine: needs response? needs a task created? informational only?
   - If needs response → create a plan step marked `requires_approval: true`
   - If informational → summarise and archive

   **LINKEDIN_NOTIF_ items** (review and respond mentally):
   - Review notification type and content
   - Mentions/comments → note that a reply should be drafted manually
   - Connections → note to accept/message when convenient

   **FILE_ items** (classify and archive):
   - Identify file type and content
   - Create a brief summary in the processed file
   - Archive to Done

6. **Check for handbook rule violations**:
   - If any rule is violated, set `status: rejected`, add `rejection_reason`, and do NOT move to Done

7. **For items needing a plan**, determine domain subdirectory based on trigger file type:
   - EMAIL_* → `Plans/email/`
   - WHATSAPP_* → `Plans/whatsapp/`
   - SOCIAL_FB_*, SOCIAL_IG_*, TWITTER_*, LINKEDIN_NOTIF_* → `Plans/social/`
   - ODOO_* → `Plans/odoo/`
   - FILE_* → `Plans/general/`

   Write `AI_Employee_Vault/Plans/<domain>/PLAN_<item_stem>.md`:
   ```yaml
   ---
   type: plan
   plan_id: <short-hash-of-item-stem>
   trigger_file: <original filename>
   status: in_progress
   created_at: <ISO timestamp>
   completed_at: null
   ---

   ## Steps

   - [x] Read and classify: <item type>
   - [ ] <next action>: <description> (requires_approval: true/false)
   - [ ] Log completion
   ```

8. **For external actions** (email send, post, payment), determine domain subdirectory:
   - email_reply → `Pending_Approval/email/`
   - whatsapp_reply → `Pending_Approval/whatsapp/`
   - linkedin_post, facebook_post, instagram_post, twitter_post → `Pending_Approval/social/`
   - odoo_invoice, odoo_payment → `Pending_Approval/odoo/`

   Write approval file: `AI_Employee_Vault/Pending_Approval/<domain>/APPROVAL_<action>_<id>.md`
   with YAML frontmatter:
   ```yaml
   ---
   type: <email_reply | linkedin_post | whatsapp_reply>
   action_id: <uuid or hash>
   status: pending
   created_at: <ISO>
   expires_at: <ISO + 24h>
   requested_by: fte-process
   trigger_file: <original filename>
   ---
   ## Action Preview
   [Full content for user to review]
   ## Why This Action
   [Claude's reasoning]
   ```

9. **Update the item's frontmatter**:
   - `status: done` | `pending_approval` | `rejected`
   - `processed_by: fte-process`
   - `processed_at: <ISO>`

10. **Move the file** to `AI_Employee_Vault/Done/` if status is done or archived (skip if pending_approval or rejected).

11. **Update `AI_Employee_Vault/Dashboard.md`** — refresh counts.

12. **Log the action**: Append to `AI_Employee_Vault/Logs/YYYY-MM-DD.json`:
    ```json
    {"timestamp":"<ISO>","action":"skill_executed","actor":"fte-process","source":"Needs_Action/<file>","destination":"Done/<file>","result":"success","details":"Processed: <one-line summary>"}
    ```

13. **Report**: what was processed, what action was taken, current pending count. If an approval file was written, say exactly where it is.
