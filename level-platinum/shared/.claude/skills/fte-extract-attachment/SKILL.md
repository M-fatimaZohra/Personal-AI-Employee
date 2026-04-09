---
name: fte-extract-attachment
description: Extract and analyse an email attachment (PDF/txt/md/csv). Reads the extracted text, matches against FAQ_Context.md pricing/services, and writes a structured Pending_Approval for the user to approve — which then triggers Odoo invoice creation via fte-approve.
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Write, Edit, Bash
argument-hint: "[ATTACHMENT_EXTRACT_*.md filename]"
---

# Extract Attachment — Gold FTE

You are the `gold-fte` AI Employee. Process an email attachment, understand the order/request inside it, match it against company pricing, and create a clean approval item for the user.

## Steps

### 1. Read the trigger file

Read `AI_Employee_Vault/Needs_Action/**/<ATTACHMENT_EXTRACT_*.md>` passed as `$ARGUMENTS` (search recursively).

Extract from frontmatter:
- `source_email` — the EMAIL_*.md that triggered this
- `message_id` — Gmail message ID
- `from` — sender email address
- `subject` — email subject
- `attachment_name` — original filename
- `attachment_path` — local path where the file was saved (Inbox/attachments/)
- `attachment_extension` — `.pdf`, `.txt`, `.md`, `.csv`
- `is_invoice_email` — true/false

---

### 2. Read the attachment content

**For `.txt`, `.md`, `.csv`**: Read the file directly using the Read tool — no extraction needed.

**For `.pdf`**: Run extraction via Bash:
```bash
cd /d/mirab_important/code/Q4_Era_of_New_AICLI/Hackathon/Hackathon2025-2026/Hackathon-0/fte-Autonomus-employ/level-gold && uv run python attachment_extractor.py "<attachment_path>" "<attachment_path>.extracted.md"
```
Then read the resulting `<attachment_path>.extracted.md` file.

**If extraction fails (exit code 2 = scanned/image-only PDF)**:
- Write `AI_Employee_Vault/Pending_Approval/email/APPROVAL_attach_review_<message_id[:8]>.md`:
  ```yaml
  ---
  type: manual_review
  from: <sender>
  subject: <subject>
  issue: scanned_pdf_no_text
  status: pending
  created_at: <ISO>
  ---
  ## Attachment Could Not Be Read

  The PDF from **<sender>** (`<filename>`) appears to be a scanned image — no text could be extracted.

  Please open the original email in Gmail and review the attachment manually.

  **Subject**: <subject>
  **From**: <sender>
  ```
- Log the failure and stop.

---

### 3. Read pricing and service context

Read ALL of the following (they are the ground truth for pricing):
- `AI_Employee_Vault/FAQ_Context.md` — services, pricing FAQs, standard rates
- `AI_Employee_Vault/Business_Goals.md` (if it exists) — current rates, active packages
- `AI_Employee_Vault/Company_Handbook.md` — any pricing rules or discounts mentioned

---

### 4. Analyse the attachment content

Parse the attachment text to extract:
- **Client/company name** (if mentioned)
- **Requested services or products** — list each item
- **Quantities** (if specified)
- **Any prices or budgets the client mentioned** (if any)
- **Delivery/timeline requirements** (if any)
- **Special notes or conditions**

Then match each requested service/product against your pricing context (FAQ_Context.md + Business_Goals.md):
- If a matching service is found → use the FAQ price
- If no match → write "Price TBD — not in FAQ" for that line item
- Compute a subtotal for matched items

**Important**: Never invent prices. Only use prices explicitly stated in the FAQ/context files.

---

### 5. Write the structured Pending_Approval

Write `AI_Employee_Vault/Pending_Approval/odoo/APPROVAL_invoice_request_<message_id[:8]>.md`:

```yaml
---
type: odoo_invoice
action_id: <message_id[:8]>
from: "<sender email>"
client_name: "<extracted client name or sender name>"
subject: "<original email subject>"
source_email: <EMAIL_*.md filename>
attachment_file: <attachment_name>
sensitivity: sensitive
priority: high
status: pending
created_at: <ISO timestamp>
expires_at: <ISO timestamp + 72h>
requested_by: fte-extract-attachment
requires_odoo_invoice: true
requires_confirmation_email: true
---

## Invoice Request from <sender>

**From**: <sender email>
**Subject**: <original subject>
**Attachment**: `<attachment_filename>`

---

## Requested Services / Products

| # | Service / Product | Qty | Unit Price | Subtotal | Source |
|---|-------------------|-----|-----------|----------|--------|
| 1 | <service name> | <qty> | <price from FAQ or "TBD"> | <subtotal or "TBD"> | <FAQ entry used or "Not in FAQ"> |
| 2 | ... | | | | |

**Estimated Total**: **$<sum of known items>** *(items marked TBD not included)*

---

## Notes from Attachment

<2-4 sentences summarising the client's request, any special conditions, timeline, or notes>

---

## Items Needing Your Input

<List any line items where price is TBD — user must fill these in before approving>
<List any ambiguities — e.g. "client mentioned 'website package' but FAQ has 3 tiers — which applies?">

---

## Actions

**To create the Odoo invoice and send confirmation email**:
  1. Fill in any TBD prices above (edit this file)
  2. Move this file to `AI_Employee_Vault/Approved/`

**To reject**: Move to `AI_Employee_Vault/Rejected/`

**To edit first**: Edit the table above, then move to Approved/
```

---

### 6. Update the source email file

Edit `AI_Employee_Vault/Needs_Action/<source_email>` frontmatter:
```yaml
attachment_processed: true
approval_file: Pending_Approval/APPROVAL_invoice_request_<message_id[:8]>.md
processed_by: fte-extract-attachment
```

---

### 7. Update trigger file status

Edit the `ATTACHMENT_EXTRACT_*.md` trigger file:
```yaml
status: processed
processed_at: <ISO>
output_file: Pending_Approval/APPROVAL_invoice_request_<message_id[:8]>.md
```

---

### 8. Log

```json
{"timestamp":"<ISO>","action":"skill_executed","actor":"fte-extract-attachment","source":"<ATTACHMENT_EXTRACT_*.md>","destination":"Pending_Approval/APPROVAL_invoice_request_<id>.md","result":"success","details":"Extracted <word_count> words | Matched <N>/<total> line items to FAQ pricing | Client: <name>"}
```

---

### 9. Report

```
Attachment processed: <attachment_name>
From: <sender>
Client: <client_name>
Line items: <N matched to FAQ pricing, M items need manual pricing>
Estimated total: $<amount>
Approval file: Pending_Approval/APPROVAL_invoice_request_<id>.md
Action required: Review pricing in Obsidian, then move to /Approved to create invoice.
```
