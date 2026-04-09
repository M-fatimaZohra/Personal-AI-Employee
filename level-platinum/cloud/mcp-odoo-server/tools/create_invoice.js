/**
 * create_invoice — HITL-gated invoice creation in Odoo.
 *
 * Requires an approval file to exist in AI_Employee_Vault/Approved/ before
 * creating the invoice. This enforces the HITL pattern for all write operations.
 *
 * Required params:
 *   - partner_id:    Odoo partner (customer) ID
 *   - amount:        Invoice total amount
 *   - due_date:      Due date (ISO string YYYY-MM-DD)
 *   - approval_file: Filename in Approved/ (e.g. APPROVAL_invoice_abc123.md)
 *
 * Optional params:
 *   - description:   Line item description (default: "Services")
 *   - currency_id:   Odoo currency ID (default: 1 = USD)
 */

import { readFileSync, existsSync } from "fs";
import { join } from "path";
import { odooCall } from "./odoo_auth.js";

const VAULT_PATH = process.env.VAULT_PATH || "AI_Employee_Vault";

export async function createInvoice({
  partner_id,
  amount,
  due_date,
  approval_file,
  description = "Services",
  currency_id = 1,
}) {
  // --- HITL gate: approval file must exist in /Approved ---
  const approvalPath = join(VAULT_PATH, "Approved", approval_file);
  if (!existsSync(approvalPath)) {
    throw new Error(
      `HITL gate: approval file not found at ${approvalPath}. ` +
        `Move the approval file to /Approved/ first.`
    );
  }

  // --- Create invoice in Odoo ---
  // IMPORTANT: Use plain objects for invoice_line_ids — NOT ORM commands [0, 0, {...}].
  // The Odoo 17+ REST API /json/2/ does not support ORM write commands.
  // Sending [[0, 0, {...}]] causes "unhashable type: list" in the Python ORM dispatcher.
  const invoiceData = {
    move_type: "out_invoice",
    partner_id,
    invoice_date_due: due_date,
    currency_id,
    invoice_line_ids: [
      [0, 0, {
        name: description,
        quantity: 1,
        price_unit: amount,
      }],
    ],
  };

  const createResult = await odooCall("account.move", "create", {
    vals_list: [invoiceData],
  });

  // Odoo REST API returns [id] (list) for create with vals_list — normalise to integer.
  const invoiceId = Array.isArray(createResult) ? createResult[0] : createResult;

  // Confirm (post) the invoice so it gets a proper INV/ number
  await odooCall("account.move", "action_post", {
    ids: [invoiceId],
  });

  // Fetch the created invoice details
  const [invoice] = await odooCall("account.move", "search_read", {
    domain: [["id", "=", invoiceId]],
    fields: ["name", "partner_id", "amount_total", "invoice_date_due", "state"],
  });

  return {
    invoice_id: invoiceId,
    invoice_number: invoice?.name || `INV/${invoiceId}`,
    partner_id,
    amount,
    due_date,
    status: invoice?.state || "posted",
  };
}
