---
name: fte-odoo-audit
description: Query Odoo financials and report current month revenue, expenses, outstanding and overdue invoices. Updates Dashboard with Odoo snapshot.
argument-hint: "[month YYYY-MM]"
user-invocable: true
allowed-tools:
  - mcp__odoo__get_financial_summary
  - mcp__odoo__list_transactions
  - Read
  - Edit
  - Write
---

# fte-odoo-audit

Query Odoo for the current financial snapshot and update the Dashboard.

## Steps

1. **Get financial summary** — call `mcp__odoo__get_financial_summary` (use $ARGUMENTS as month if provided, else omit for current month)

2. **Format and display** the following in a clear report:
   - Revenue this month: total paid invoices
   - Expenses this month: total paid bills
   - Outstanding invoices: count + total amount
   - Overdue invoices: count + total amount + names (30+ days past due)

3. **Update Dashboard** — append/update the Odoo Financial Snapshot section in `AI_Employee_Vault/Dashboard.md`:
   ```markdown
   ## Odoo Financial Snapshot
   - 💰 Revenue (this month): **$X**
   - 💸 Expenses (this month): **$X**
   - 📄 Outstanding invoices: **N** totalling **$X**
   - ⚠️ Overdue invoices: **N** totalling **$X**
   ```

4. **Flag overdue invoices** — if any invoices are 30+ days overdue, create an action item:
   - Write `ODOO_OVERDUE_<date>.md` to `AI_Employee_Vault/Needs_Action/` with frontmatter:
     ```yaml
     ---
     type: odoo_overdue
     priority: high
     created_at: <ISO timestamp>
     status: pending
     overdue_count: N
     overdue_total: $X
     ---
     ```
   - Body: list each overdue invoice with client name, amount, days overdue

5. **Handle errors gracefully** — if any `mcp__odoo__*` call throws or times out:
   - Do NOT crash or stop — continue to remaining steps using whatever data was already collected
   - Write this exact text to the `## Odoo Financial Snapshot` section in `AI_Employee_Vault/Dashboard.md`:
     ```
     ⚠️ Odoo unavailable — circuit breaker may be open. Run: docker compose up -d (in level-gold/)
     ```
   - Append this entry to `AI_Employee_Vault/Logs/<YYYY-MM-DD>.json`:
     ```json
     {"timestamp":"<ISO>","action":"mcp_error","actor":"fte-odoo-audit","source":"mcp__odoo__get_financial_summary","result":"error","details":"Odoo MCP call failed — <error message>"}
     ```
   - Print: `⚠️ Odoo unavailable — skipping financial data. Dashboard updated with warning.`
   - Skip steps 3 and 4 (no data to write or flag)

## Output

Print a summary:
```
✅ Odoo Financial Snapshot (YYYY-MM)
  Revenue:    $X,XXX
  Expenses:   $X,XXX
  Outstanding: N invoices, $X,XXX total
  Overdue:    N invoices, $X,XXX total
Dashboard updated.
```
