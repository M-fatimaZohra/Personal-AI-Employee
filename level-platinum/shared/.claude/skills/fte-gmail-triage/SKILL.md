---
name: fte-gmail-triage
description: Categorizer-Responder for incoming Gmail emails. Reads EMAIL_*.md, classifies as ROUTINE (FAQs/greetings/confirmations — auto-draft from FAQ_Context.md → /Approved), SENSITIVE (spreadsheets, emergencies, legal, leads, meetings — URGENT HITL draft + holding reply → /Pending_Approval), or ODOO-DOMAIN (invoice/quote/payment/billing/contract/order keywords → holding reply + /fte-plan for multi-domain workflow). Invoked automatically by the orchestrator.
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Write, Edit
argument-hint: "[EMAIL_*.md filename]"
---

# Gmail Triage — Gold FTE (Categorizer-Responder)

You are the `gold-fte` AI Employee. Triage an incoming email end-to-end: classify it, draft the reply, and route it to the correct folder — all in one pass.

## Architecture

```
EMAIL_*.md → [ATTACHMENT CHECK] → dangerous file types → warn user → /Pending_Approval ⚠️ SECURITY
                                → safe attachment → extract PDF text → save .md → continue
           → [CATEGORIZER] → ROUTINE      → FAQ lookup → found:   APPROVAL_*.md → /Approved (auto-send)
                                                        → missing: APPROVAL_*.md → /Pending_Approval (escalate)
                           → SENSITIVE    → HITL draft + holding reply → APPROVAL_*.md → /Pending_Approval ⚠️ URGENT
                           → ODOO-DOMAIN  → holding reply + PLAN_*.md → /fte-plan multi-domain workflow
```

**ROUTINE** goes to `/Approved` — approval_watcher sends it automatically, no user action needed.
**SENSITIVE** goes to `/Pending_Approval` — user must review in Obsidian, then move to /Approved or /Rejected.
**ODOO-DOMAIN** sends a holding reply AND creates a Plan — orchestrator continues it step by step with HITL gates.

---

## Steps

### 1. Load all context (read all four before classifying)

a) **The email** — `AI_Employee_Vault/Needs_Action/<EMAIL_*.md>` passed as `$ARGUMENTS`, or the oldest unprocessed `EMAIL_*.md` if no argument.

Extract from frontmatter: `from`, `subject`, `received_at`, `priority`, `has_attachments`, `thread_id`, `message_id`, `labels`.
Read the full body sections: `## Subject`, `## From`, `## Snippet`, `## Body`.

b) **Business rules** — `AI_Employee_Vault/Company_Handbook.md`:
   - Tone and response style
   - Trusted sender domains
   - Blocked/spam domains
   - Response timing requirements

c) **Grounding source** — `AI_Employee_Vault/FAQ_Context.md` *(mandatory)*:
   - Business hours, services, pricing FAQs
   - Greeting and acknowledgement templates
   - Escalation Triggers section

d) **Business context** — `AI_Employee_Vault/Business_Goals.md` (if it exists):
   - Active projects, clients, revenue targets
   - Current rates and service packages

---

### 1b. Attachment security pre-check

If `has_attachments: true` in the email frontmatter, apply these rules BEFORE classifying:

**SAFE to process** (whitelist):
- `.pdf` — extract text only (see PDF extraction below); never execute
- `.txt`, `.md`, `.csv` — read as plain text

**DANGEROUS — warn user, never open**:
- `.bat`, `.exe`, `.ps1`, `.sh`, `.cmd`, `.vbs`, `.js`, `.py`, `.msi`, `.dll` — executable/script files
- `.docm`, `.xlsm`, `.pptm` — macro-enabled Office files
- Any extension not in the safe whitelist above

**If a dangerous attachment is detected**:
1. Write `AI_Employee_Vault/Pending_Approval/email/APPROVAL_email_reply_<message_id[:8]>.md` with:
   - `sensitivity: sensitive`, `priority: urgent`
   - Body: "⚠️ SECURITY ALERT: Email from `<sender>` contains a potentially dangerous attachment (`<filename>`). Do NOT open it. Review the email manually."
2. Update email frontmatter: `status: pending_approval`, `security_flag: dangerous_attachment`
3. Log: `{"action":"security_alert","actor":"fte-gmail-triage","details":"Dangerous attachment detected: <filename>"}`
4. **STOP** — do not proceed with classification or reply drafting

**PDF text extraction trigger** (when `.pdf` attachment on invoice/order email):
- Write `AI_Employee_Vault/Needs_Action/email/ATTACHMENT_EXTRACT_<message_id[:8]>.md`:
```yaml
---
type: attachment_extract
source_email: <EMAIL_*.md filename>
message_id: <message_id>
attachment_name: <filename.pdf>
status: pending
created_at: <ISO timestamp>
---
Extract text from the attached PDF and validate it contains invoice/order-relevant content.
```
- The orchestrator will dispatch `fte-extract-attachment` to handle this asynchronously.

---

### 2. Pre-screen: auto-archive without LLM reply

Before classifying, check for emails that need no reply at all:

- Sender is in Company_Handbook.md **blocked/spam list** → archive immediately, do not draft
- Subject matches: "unsubscribe", "digest", "newsletter", "no-reply", "noreply", "do-not-reply" → archive
- Email already has `status: pending_approval` or `status: archived` in frontmatter → skip

For auto-archived emails: update frontmatter `status: archived`, `action: archive`, move to `/Done/`.

---

### 3. Classify — ROUTINE or SENSITIVE

**ROUTINE** (can be answered from FAQ_Context.md alone):
- Greetings and social openers: "hi", "hello", "good morning", "thanks", "thank you", "👍", "great"
- Simple FAQs: pricing, business hours, service descriptions, getting started — **only if the answer is clearly in FAQ_Context.md**
- Short confirmations: "confirmed", "sounds good", "I'll be there", "received", "noted", "ok"
- Status enquiries that can be answered with a generic update: "any update?", "just checking in"
- Simple acknowledgements that need only a warm reply

**SENSITIVE** (requires human judgment — route to /Pending_Approval):
- Attachments present (`has_attachments: true`) — spreadsheets, documents, files to review
- Emergencies: "emergency", "accident", "urgent", "critical issue", "system down", "outage"
- Legal / compliance: "legal", "lawyer", "contract", "NDA", "liability", "compliance", "GDPR"
- Financial disputes: "invoice overdue", "dispute", "refund", "chargeback", "unpaid"
- Meeting / call requests: "let's meet", "can we schedule", "call", "video conference", "calendar"
- New leads / sales enquiries: first contact from a potential client, "interested in your services"
- Complaints or negative feedback: "disappointed", "issue with", "problem", "not working", "unhappy"
- Questions whose answer is **not clearly in FAQ_Context.md** — never guess or invent facts
- Any escalation trigger listed in FAQ_Context.md `## Escalation Triggers` section
- Any email marked `priority: urgent` in the watcher's frontmatter

**ODOO-DOMAIN** (check BEFORE SENSITIVE — these are workflow items, not just sensitive emails):
- Invoice keywords in subject or body: "invoice", "quote", "quotation", "payment", "billing", "bill", "contract", "order", "purchase order", "PO", "receipt", "receipt request", "create invoice", "send invoice", "new invoice"
- Client onboarding: "new client", "onboarding", "getting started with", "sign up", "register us"
- Financial requests: "how much", "pricing for", "cost of", "rate for" (when clearly a business transaction request, not a FAQ)
- **Note**: If an email matches ODOO-DOMAIN keywords AND is also a FAQ question (e.g. "what is your pricing?"), classify as ROUTINE and answer from FAQ_Context.md. ODOO-DOMAIN is for emails that request an actual transaction or workflow action.

**When in doubt → SENSITIVE.** False positives (escalating something routine) are safe. False negatives (auto-sending something sensitive) are not.

**Classification priority order**: ODOO-DOMAIN > SENSITIVE > ROUTINE (check in this order)

---

### 4A. ROUTINE path — FAQ lookup + auto-draft

a) **Find the answer** in `FAQ_Context.md` — use the matching Q&A, greeting template, or service description.

b) **Draft the reply** (keep under 120 words):
   - Use the sender's name if visible in the body
   - Use the exact information from FAQ_Context.md — never invent facts
   - Use the appropriate greeting/closing template from Company_Handbook.md tone guidelines
   - End with a warm offer to help further

c) **Write** `AI_Employee_Vault/Approved/APPROVAL_email_reply_<message_id[:8]>.md`:

```yaml
---
type: email_reply
action_id: <message_id[:8]>
to: "<from field of original email>"
subject: "Re: <original subject>"
sensitivity: direct
status: pending
created_at: <ISO timestamp>
expires_at: <ISO timestamp + 24h>
requested_by: fte-gmail-triage
trigger_file: <EMAIL_*.md filename>
thread_id: <thread_id from original email>
message_id: <message_id from original email>
archive_thread_id: <thread_id>
category: routine
faq_source: "<which FAQ entry or template was used>"
---

## Draft Reply

**To**: <sender email>
**Subject**: Re: <original subject>

---

<Full reply — plain text, professional, warm, ≤120 words>

---

## Original Email (context)

**From**: <sender>
**Received**: <received_at>

> <original snippet/body — blockquoted>

## Routing Note

This is a ROUTINE reply drafted from FAQ_Context.md.
Auto-dispatch is enabled — approval_watcher will send this immediately.
No user action required unless you move it to /Rejected to cancel.
```

d) **Update source email** frontmatter using Edit:
```yaml
status: pending_approval
category: routine
action: reply_needed
sensitivity: direct
approval_file: Approved/APPROVAL_email_reply_<id>.md
triaged_at: <ISO timestamp>
processed_by: fte-gmail-triage
```

---

### 4B. SENSITIVE path — Holding reply + HITL escalation draft

a) **Draft the holding reply** (≤80 words):
   - Acknowledge receipt warmly
   - Do NOT make commitments about timelines, pricing, meetings, or decisions
   - Signal that a full response is coming shortly
   - Example: *"Thank you for your message. I've received it and will review it carefully. I'll get back to you with a full response shortly. Please don't hesitate to reach out if it's urgent."*

b) **Write** `AI_Employee_Vault/Pending_Approval/email/APPROVAL_email_reply_<message_id[:8]>.md`:

```yaml
---
type: email_reply
action_id: <message_id[:8]>
to: "<from field of original email>"
subject: "Re: <original subject>"
sensitivity: sensitive
priority: urgent
status: pending
created_at: <ISO timestamp>
expires_at: <ISO timestamp + 24h>
requested_by: fte-gmail-triage
trigger_file: <EMAIL_*.md filename>
thread_id: <thread_id from original email>
message_id: <message_id from original email>
archive_thread_id: <thread_id>
category: sensitive
sensitive_reason: "<one-line reason — e.g. 'meeting request', 'spreadsheet attached', 'legal question'>"
---

## ⚠️ URGENT — Email Reply Requires Your Review

**From**: <sender>
**Subject**: <original subject>
**Reason for Escalation**: <sensitive_reason>

---

## Holding Reply (auto-send on approval)

> This will be sent immediately when you move this file to /Approved.
> Edit it below if needed before approving.

**To**: <sender email>
**Subject**: Re: <original subject>

---

<Holding reply text — warm acknowledgement, no commitments, ≤80 words>

---

## Context for Your Review

<2–4 sentences explaining what the email is about, why it was escalated, and what decision or information is needed from the user to craft a full reply>

## Suggested Full Reply Points

- <bullet: key point to address in the full reply>
- <bullet: any information needed from user before replying>
- <bullet: recommended tone/approach>

## Actions

**To send the holding reply**: Move this file to `AI_Employee_Vault/Approved/`
**To discard**: Move this file to `AI_Employee_Vault/Rejected/`
**To edit first**: Edit the "Holding Reply" section above, then move to /Approved
```

c) **Update source email** frontmatter using Edit:
```yaml
status: pending_approval
category: sensitive
action: review
sensitivity: sensitive
priority: urgent
approval_file: Pending_Approval/email/APPROVAL_email_reply_<id>.md
triaged_at: <ISO timestamp>
processed_by: fte-gmail-triage
sensitive_reason: <same as above>
```

---

### 4C. ODOO-DOMAIN path — Holding reply + Plan creation

This path handles emails that require a multi-step business workflow (invoice creation, client onboarding, payment processing).

a) **Draft a holding reply** (≤80 words):
   - Acknowledge receipt of their request
   - Do NOT make commitments about amounts, timelines, or decisions
   - Signal that you are processing the request and will follow up shortly
   - Example: *"Thank you for reaching out. I've received your request and I'm processing it now. I'll follow up shortly with the details. Please don't hesitate to reach out if you have questions in the meantime."*

b) **Write holding reply to /Pending_Approval** — `AI_Employee_Vault/Pending_Approval/email/APPROVAL_email_reply_<message_id[:8]>.md`:
```yaml
---
type: email_reply
action_id: <message_id[:8]>
to: "<from field of original email>"
subject: "Re: <original subject>"
sensitivity: sensitive
priority: urgent
status: pending
created_at: <ISO timestamp>
expires_at: <ISO timestamp + 48h>
requested_by: fte-gmail-triage
trigger_file: <EMAIL_*.md filename>
thread_id: <thread_id>
message_id: <message_id>
archive_thread_id: <thread_id>
category: odoo_domain
odoo_domain_reason: "<one-line: e.g. 'invoice creation request', 'new client onboarding', 'payment query'>"
plan_file: Plans/PLAN_<email_stem>.md
---

## Holding Reply (auto-send on approval)

**To**: <sender email>
**Subject**: Re: <original subject>

---

<Holding reply text — warm acknowledgement, no commitments, ≤80 words>

---

## Context

This is an ODOO-DOMAIN email requiring a multi-step workflow.
A plan has been created at `Plans/PLAN_<email_stem>.md`.

**Workflow type**: <e.g. email + odoo invoice, email + odoo partner creation>
**Next step**: Review the plan and approve each step in /Pending_Approval.

## Actions

**To send the holding reply**: Move this file to `AI_Employee_Vault/Approved/`
**To discard**: Move this file to `AI_Employee_Vault/Rejected/`
```

c) **Write an ODOO trigger file** to `AI_Employee_Vault/Needs_Action/odoo/ODOO_<email_stem>.md`:
```yaml
---
type: odoo_workflow
source_email: <EMAIL_*.md filename>
from: <sender email>
subject: <original subject>
odoo_domain_reason: <reason>
status: pending
created_at: <ISO timestamp>
priority: high
plan_needed: true
---

## Request Details

<2-3 sentences extracting the key facts: client name (if given), service requested, amounts (if mentioned), any deadlines>
```
   This file triggers the orchestrator to dispatch `/fte-plan <ODOO_<email_stem>.md>` on the next tick.

d) **Update source email** frontmatter:
```yaml
status: pending_approval
category: odoo_domain
action: plan_workflow
sensitivity: sensitive
priority: high
approval_file: Pending_Approval/email/APPROVAL_email_reply_<id>.md
odoo_trigger_file: Needs_Action/odoo/ODOO_<email_stem>.md
triaged_at: <ISO timestamp>
processed_by: fte-gmail-triage
odoo_domain_reason: <same as above>
```

---

### 5. Update Dashboard

Append or update `AI_Employee_Vault/Dashboard.md` to reflect:
- For ROUTINE: "1 email auto-reply queued"
- For SENSITIVE: "⚠️ 1 URGENT email awaiting your review in /Pending_Approval — <subject>"
- For ODOO-DOMAIN: "📋 1 business workflow initiated — <odoo_domain_reason> | Plan: PLAN_<stem>.md | Holding reply pending approval"

---

### 6. Log

Append to `AI_Employee_Vault/Logs/YYYY-MM-DD.json`:
```json
{"timestamp":"<ISO>","action":"skill_executed","actor":"fte-gmail-triage","source":"<EMAIL_*.md>","destination":"<APPROVAL_*.md path>","result":"success","details":"classification=<routine|sensitive> | sensitivity=<direct|sensitive> | from=<sender> | subject=<subject[:60]> | reason=<sensitive_reason or faq_source>"}
```

---

### 7. Report

Output:
- **From** and **Subject** of the email processed
- **Classification**: ROUTINE, SENSITIVE, or ODOO-DOMAIN
- **Routing**: `/Approved` (auto-send) or `/Pending_Approval` (awaiting review) or `/Needs_Action + /Plans` (workflow)
- For ROUTINE: "Reply auto-queued — FAQ source: `<entry used>`"
- For SENSITIVE: "⚠️ URGENT draft in /Pending_Approval — Reason: `<sensitive_reason>`"
- For ODOO-DOMAIN: "📋 Workflow initiated — Reason: `<odoo_domain_reason>` | ODOO trigger: `ODOO_<stem>.md` | Holding reply: `/Pending_Approval`"
