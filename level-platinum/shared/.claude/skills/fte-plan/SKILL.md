---
name: fte-plan
description: Create or continue a structured multi-domain Plan for a complex task. Detects workflows spanning email + Odoo + social media. In continue mode, executes the next unchecked step of an active plan. Use when a Needs_Action item requires multiple steps or external actions.
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Write, Edit, Bash, mcp__odoo__get_financial_summary, mcp__odoo__create_invoice, mcp__odoo__create_partner, mcp__email__send_email, mcp__email__draft_email
argument-hint: "<filename in Needs_Action> | continue <plan_filename>"
---

# Create or Continue Task Plan — Gold FTE

You are the `gold-fte` AI Employee. Create or continue a structured execution plan.

## Mode Detection

Parse `$ARGUMENTS`:
- Starts with `"continue "` → **CONTINUE MODE**: resume plan at next unchecked step
- Otherwise → **CREATE MODE**: create a new plan for a Needs_Action item

---

## CREATE MODE

### Step C1 — Read the trigger item

- If `$ARGUMENTS` provided, read `AI_Employee_Vault/Needs_Action/**/$ARGUMENTS` (search recursively)
- Otherwise read the most recent unplanned high-priority item in Needs_Action (recursive scan)
- If nothing found: report "Nothing to plan" and stop

### Step C2 — Read context

- Read `AI_Employee_Vault/Company_Handbook.md` for applicable rules
- Read `AI_Employee_Vault/Business_Goals.md` if it exists
- Check `AI_Employee_Vault/Plans/**/*.md` for existing PLAN_<item_stem>*.md — if found, report it and stop

### Step C3 — Detect workflow type

Classify the item as one of:

**Single-domain** (one system):
- Email only: reply, forward, archive
- File only: read, summarise, archive
- Social only: reply to notification

**Multi-domain** (two or more systems — detect by keywords in subject/body):
- `email + odoo`: keywords → "invoice", "quote", "payment", "billing", "contract", "order", "receipt"
- `email + social`: keywords → "announce", "share on", "post about", "publish", "promote"
- `odoo + social`: keywords → "paid", "deal closed", "new client", "revenue milestone"
- `full multi-domain`: all three systems involved

### Step C4 — Generate steps with system labels

Each step MUST include a system tag `[email]`, `[odoo]`, `[social]`, or `[internal]`.

**Single-domain email plan**:
```
- [x] [internal] Read and classify: email from <sender>
- [ ] [internal] Draft reply — invoke /fte-gmail-reply (requires_approval: true)
- [ ] [email] Send reply via Email MCP (requires_approval: true)
- [ ] [internal] Log completion and archive
```

**Multi-domain: email + odoo (e.g. invoice request)**:
```
- [x] [internal] Read and classify: invoice request from <client>
- [ ] [internal] Extract invoice details: client name, service, amount
- [ ] [odoo] Create invoice in Odoo via mcp__odoo__create_invoice (requires_approval: true)
- [ ] [email] Send invoice confirmation email to client (requires_approval: true)
- [ ] [internal] Schedule follow-up check in 30 days: add FOLLOWUP_<stem>.md to Plans/
- [ ] [internal] Log completion and archive
```

**Multi-domain: email + odoo + social (e.g. new client announcement)**:
```
- [x] [internal] Read and classify: new client onboarding from <client>
- [ ] [odoo] Create client as partner in Odoo via mcp__odoo__create_partner (requires_approval: true)
- [ ] [odoo] Create onboarding invoice in Odoo (requires_approval: true)
- [ ] [email] Send welcome email to client (requires_approval: true)
- [ ] [social] Draft social announcement post — invoke /fte-social-post (requires_approval: true)
- [ ] [internal] Log completion and archive
```

**Follow-up plan** (created by multi-domain plans for invoice tracking):
```
- [ ] [odoo] Check invoice payment status via mcp__odoo__list_transactions
- [ ] [internal] If paid: mark plan complete and cancel this follow-up
- [ ] [email] If unpaid after 30 days: send reminder email (requires_approval: true)
- [ ] [internal] Log result and archive
```

### Step C5 — Write plan file

Determine domain subdirectory based on trigger file type:
- EMAIL_* → `Plans/email/`
- WHATSAPP_* → `Plans/whatsapp/`
- SOCIAL_FB_*, SOCIAL_IG_*, TWITTER_*, LINKEDIN_NOTIF_* → `Plans/social/`
- ODOO_* → `Plans/odoo/`
- FILE_* → `Plans/general/`

Write to `AI_Employee_Vault/Plans/<domain>/PLAN_<item_stem>.md`:

```yaml
---
type: plan
plan_id: <first-8-chars-of-sha256-of-trigger-filename>
trigger_file: <original filename in Needs_Action>
workflow_type: <single_domain | multi_domain_email_odoo | multi_domain_email_social | multi_domain_full>
systems_involved: [<email|odoo|social|internal> ...]
status: in_progress
created_at: <ISO timestamp>
completed_at: null
current_step: 1
total_steps: <N>
requires_approval: <true if any step needs approval, else false>
---

## Objective

<One-sentence description of what this plan achieves>

## Context

- **From**: <sender / source>
- **Type**: <email | message | file>
- **Priority**: <priority from trigger file>
- **Workflow**: <workflow_type>
- **Handbook rules applied**: <rule names, or "none">

## Steps

- [x] [internal] Read and classify: <trigger file type>
- [ ] [<system>] <Step description> (requires_approval: <true|false>)
...
- [ ] [internal] Log completion and archive

## Notes

<Special considerations, approval requirements, follow-up schedule>
```

### Step C6 — Update trigger file and log

- Edit trigger file in Needs_Action: update frontmatter with:
  ```yaml
  status: in_progress
  plan_file: Plans/PLAN_<stem>.md
  plan_created_at: <ISO timestamp>
  ```
  **CRITICAL**: `status: in_progress` prevents the orchestrator from re-dispatching this file on the next tick and creating duplicate plans.
- Log: `{"action":"plan_created","actor":"fte-plan","source":"<trigger>","destination":"PLAN_<stem>.md","result":"success","details":"<workflow_type>: N steps, M require approval"}`

### Step C7 — Report

Print: plan filename, workflow type, number of steps, which steps require approval, recommended first action.

---

## CONTINUE MODE

`$ARGUMENTS` = `"continue <plan_filename>"`

### Step K1 — Load the plan

- Extract plan filename from arguments (e.g. `continue PLAN_EMAIL_abc123.md`)
- Read `AI_Employee_Vault/Plans/<plan_filename>`
- If plan has `status: complete`, report "Plan already complete" and stop

### Step K2 — Find next unchecked step

Scan the Steps section for the first line matching `- [ ] [<system>]`. This is the step to execute now.

If no unchecked steps found:
- Update plan frontmatter: `status: complete`, `completed_at: <ISO>`
- Log completion and stop

### Step K3 — Execute the step

**For `[internal]` steps** (no external action):
- Classify, summarise, or archive as described
- If step says "Schedule follow-up": create `FOLLOWUP_<stem>.md` in Plans/ using the follow-up plan template from C4
- Mark step complete

**For `[odoo]` steps**:

*Check invoice payment* (T077 — follow-up cancellation):
- Call `mcp__odoo__list_transactions` or `mcp__odoo__get_financial_summary`
- If MCP call fails: do NOT mark step `[x]` — leave `[ ]` so orchestrator retries next tick; append to plan Notes: `⚠️ [<ISO>] Odoo MCP unavailable — step will retry on next orchestrator tick`; log `{"action":"mcp_error","actor":"fte-plan","source":"mcp__odoo__list_transactions","result":"error","details":"<error>"}` and stop K3
- If invoice status = paid → mark this step AND any remaining payment-follow-up steps as `[CANCELLED - invoice paid]`
- Delete or archive the FOLLOWUP plan if it exists
- If invoice unpaid → proceed to next step (draft reminder email)

*Create invoice*:
- If `requires_approval: true`:
  - Check if `AI_Employee_Vault/Approved/APPROVAL_odoo_<plan_id>.md` exists → if yes, proceed to call MCP
  - If NOT in Approved/: write `AI_Employee_Vault/Pending_Approval/odoo/APPROVAL_odoo_<plan_id>.md` with invoice details, then update plan frontmatter `status: awaiting_approval` — **STOP K3 here, do not re-create the file on next tick**
- If approval exists in Approved/: call `mcp__odoo__create_invoice` with the approved details, then set plan `status: in_progress`
- If `mcp__odoo__create_invoice` fails: do NOT mark step `[x]`; append to plan Notes: `⚠️ [<ISO>] Odoo create_invoice failed — <error>. Will retry.`; log the error and stop K3

*Create partner*:
- If `requires_approval: true`:
  - Check if `AI_Employee_Vault/Approved/APPROVAL_odoo_<plan_id>.md` or `APPROVAL_odoo_create_partner_<plan_id>.md` exists → if yes, proceed to call MCP
  - If NOT in Approved/: write to `Pending_Approval/`, update plan frontmatter `status: awaiting_approval` — **STOP K3, do not re-create on next tick**
- If approved: call `mcp__odoo__create_partner`, then set plan `status: in_progress`
- If `mcp__odoo__create_partner` fails: do NOT mark step `[x]`; append to plan Notes with error; log and stop K3

**For `[email]` steps**:
- Draft the email content based on plan context (read trigger file for details)
- If `requires_approval: true`: write `AI_Employee_Vault/Pending_Approval/email/APPROVAL_email_<plan_id>.md`
- If approval exists in Approved/: call `mcp__email__send_email`
- If `mcp__email__send_email` fails: do NOT mark step `[x]`; append to plan Notes: `⚠️ [<ISO>] Email MCP unavailable — <error>. Will retry.`; log `{"action":"mcp_error","actor":"fte-plan","source":"mcp__email__send_email","result":"error","details":"<error>"}` and stop K3

**For `[social]` steps**:
- Dispatch `/fte-social-post <trigger_file>` to draft platform-appropriate posts
- Posts land in Pending_Approval/ automatically via fte-social-post skill

### Step K4 — Mark step complete

Use Edit to change `- [ ] [<system>]` → `- [x] [<system>]` for the executed step in the plan file.

Update frontmatter `current_step` to the next step number.

### Step K5 — Check if plan is complete

Count remaining `- [ ]` lines. If zero:
- Update frontmatter: `status: complete`, `completed_at: <ISO timestamp>`
- Move trigger file from Needs_Action/ to Done/ (rename)
- Log: `{"action":"plan_completed","actor":"fte-plan","details":"<plan_id> all steps complete"}`

### Step K6 — Log and report

```json
{"timestamp":"<ISO>","action":"plan_step_executed","actor":"fte-plan",
 "source":"Plans/<plan_filename>","result":"success",
 "details":"Step executed: [<system>] <description> | Steps remaining: N"}
```

Report: which step was executed, what action was taken, how many steps remain.
