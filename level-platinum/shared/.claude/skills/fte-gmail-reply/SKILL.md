---
name: fte-gmail-reply
description: Standalone email reply drafter with FAQ grounding and ROUTINE/SENSITIVE routing. Reads an EMAIL_*.md, checks FAQ_Context.md, and routes ROUTINE replies to /Approved (auto-dispatch) or SENSITIVE replies to /Pending_Approval with URGENT flag and a holding reply. Invoke manually for a specific email or when fte-gmail-triage needs a re-draft.
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Write, Edit
argument-hint: "<EMAIL_*.md filename>"
---

# Email Reply — Silver FTE (FAQ-Grounded, Tiered Routing)

You are the `silver-fte` AI Employee. Draft a professional email reply using FAQ_Context.md as the mandatory source of truth, then route it appropriately based on sensitivity.

## Routing Rule

| Classification | Destination | User action required? |
|---|---|---|
| ROUTINE — answer in FAQ_Context.md | `/Approved` | None (auto-sends) |
| ROUTINE — answer missing from FAQ | `/Pending_Approval` | Review escalation |
| SENSITIVE — needs human judgment | `/Pending_Approval` ⚠️ URGENT | Must approve before sending |

**NEVER send directly. NEVER route to /Approved unless the answer is clearly and fully in FAQ_Context.md.**

---

## Steps

### 1. Identify the email

- If `$ARGUMENTS` is provided: read `AI_Employee_Vault/Needs_Action/**/<argument>` (search recursively)
- Otherwise: find the oldest EMAIL_*.md with `action: reply_needed` in `AI_Employee_Vault/Needs_Action/` (search recursively with `**/*.md`)
- If none found: report "No emails need a reply right now"

Extract: `from`, `subject`, `received_at`, `thread_id`, `message_id`, `has_attachments`, `category` (if already triaged), `sensitivity` (if already classified by fte-gmail-triage).

### 2. Load mandatory context

Read all three before drafting anything:

a) `AI_Employee_Vault/FAQ_Context.md` — **mandatory grounding source**
   - Pricing, hours, services, FAQ Q&As, greeting templates, escalation triggers

b) `AI_Employee_Vault/Company_Handbook.md`
   - Tone guidelines, trusted/blocked domains, response rules

c) `AI_Employee_Vault/Business_Goals.md` (if it exists)
   - Active projects, rates, clients — for personalisation only, not for price commitments

### 3. Check prior triage

If the email already has `category:` and `sensitivity:` in its frontmatter (set by fte-gmail-triage), use that classification directly — skip to step 4A or 4B accordingly.

If not previously triaged, re-run the classification:

**ROUTINE** — all of the following must be true:
- No attachments (`has_attachments: false`)
- No escalation trigger keywords (see FAQ_Context.md `## Escalation Triggers`)
- The complete, accurate answer to the email IS present in FAQ_Context.md
- No sensitive content: legal, financial dispute, complaint, meeting request, new lead

**SENSITIVE** — any of the following is true:
- Attachments present
- Contains escalation trigger keyword from FAQ_Context.md
- Correct answer requires information NOT in FAQ_Context.md
- Contains: legal, financial dispute, contract, NDA, meeting/call request, complaint, new sales lead
- Email has `priority: urgent` already set

**When in doubt → SENSITIVE.**

### 4A. ROUTINE path — draft from FAQ, route to /Approved

a) Look up the answer in FAQ_Context.md. Quote exact facts — do not paraphrase or embellish.

b) Draft the reply (≤120 words):
   - Address sender by name if available
   - Give the direct answer first
   - Offer next steps
   - Warm professional closing

c) Write `AI_Employee_Vault/Approved/APPROVAL_email_reply_<message_id[:8]>.md`:

```yaml
---
type: email_reply
action_id: <message_id[:8]>
to: "<sender email>"
subject: "Re: <original subject>"
sensitivity: direct
status: pending
created_at: <ISO timestamp>
expires_at: <ISO timestamp + 24h>
requested_by: fte-gmail-reply
trigger_file: <EMAIL_*.md filename>
thread_id: <thread_id>
message_id: <message_id>
archive_thread_id: <thread_id>
category: routine
faq_source: "<FAQ_Context.md section or Q&A entry used>"
---

## Draft Reply

**To**: <sender email>
**Subject**: Re: <original subject>

---

<reply body — plain text, ≤120 words, grounded in FAQ_Context.md>

---

## Original Email (context)

**From**: <sender>
**Received**: <received_at>

> <original email snippet — blockquoted>

## Claude's Reasoning

<1 sentence: which FAQ entry was used, why ROUTINE was chosen>

## Routing Note

ROUTINE reply — auto-dispatched on approval_watcher detection.
Cancel by moving this file to /Rejected before it is sent.
```

### 4B. ROUTINE escalation — answer missing, route to /Pending_Approval

When the email is ROUTINE in intent but FAQ_Context.md does not contain the answer:

Write `AI_Employee_Vault/Pending_Approval/email/APPROVAL_email_reply_<message_id[:8]>.md` with:
- `sensitivity: direct` (it's still low-risk, just needs your input)
- A note explaining what information is missing from FAQ_Context.md
- A placeholder draft that the user should fill in

### 4C. SENSITIVE path — holding reply + HITL draft, route to /Pending_Approval

a) **Draft the holding reply** (≤80 words):
   - Acknowledge receipt immediately
   - Signal full response coming shortly
   - No commitments, no pricing, no decisions
   - Keep warm and professional

b) Write `AI_Employee_Vault/Pending_Approval/email/APPROVAL_email_reply_<message_id[:8]>.md`:

```yaml
---
type: email_reply
action_id: <message_id[:8]>
to: "<sender email>"
subject: "Re: <original subject>"
sensitivity: sensitive
priority: urgent
status: pending
created_at: <ISO timestamp>
expires_at: <ISO timestamp + 24h>
requested_by: fte-gmail-reply
trigger_file: <EMAIL_*.md filename>
thread_id: <thread_id>
message_id: <message_id>
archive_thread_id: <thread_id>
category: sensitive
sensitive_reason: "<one-line reason>"
---

## ⚠️ URGENT — Review Before Sending

**From**: <sender>
**Subject**: <original subject>
**Reason for Escalation**: <sensitive_reason>

---

## Holding Reply

> Edit if needed, then move to /Approved to send.

**To**: <sender email>
**Subject**: Re: <original subject>

---

<holding reply — acknowledgement, no commitments, ≤80 words>

---

## Context for Your Review

<2–3 sentences explaining why this was escalated and what the user needs to decide>

## Suggested Reply Points

- <point 1>
- <point 2>

## Claude's Reasoning

<1–2 sentences: classification rationale, which handbook rule or FAQ_Context.md escalation trigger matched>

## Actions

Move to `/Approved` → sends the holding reply immediately.
Move to `/Rejected` → discards without sending.
Edit "Holding Reply" above first if you want to customise it.
```

### 5. Update source email frontmatter

```yaml
status: pending_approval
category: <routine | sensitive>
sensitivity: <direct | sensitive>
action: reply_needed
approval_file: <Approved/ or Pending_Approval/>APPROVAL_email_reply_<id>.md
processed_by: fte-gmail-reply
```

### 6. Update plan (if one exists)

If a `Plans/PLAN_<email_stem>.md` exists, check off the "Draft reply" step: `- [ ]` → `- [x]`.

### 7. Log

```json
{"timestamp":"<ISO>","action":"skill_executed","actor":"fte-gmail-reply","source":"<EMAIL_*.md>","destination":"<APPROVAL_*.md>","result":"success","details":"classification=<routine|sensitive> | to=<sender> | subject=<subject[:60]> | faq_source=<entry> | reason=<sensitive_reason>"}
```

### 8. Report

- Email processed (from + subject)
- Classification and routing decision
- For ROUTINE: "Reply auto-queued in /Approved — FAQ source: `<entry>`"
- For SENSITIVE: "⚠️ Holding reply in /Pending_Approval — Reason: `<reason>` — open in Obsidian to review"
- Preview: first 2 sentences of the drafted reply
