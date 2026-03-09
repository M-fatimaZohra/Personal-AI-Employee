/**
 * list_transactions — Read-only search/filter of Odoo transactions.
 *
 * Supports filtering by:
 *   - start_date, end_date (ISO date strings YYYY-MM-DD)
 *   - type: "invoice" | "bill" | "payment" | "all" (default: "all")
 *   - partner_name: filter by customer/vendor name (partial match)
 *   - limit: max results (default 50)
 */

import { odooCall } from "./odoo_auth.js";

const TYPE_MAP = {
  invoice: "out_invoice",
  bill: "in_invoice",
  payment: null, // handled separately
  all: null,
};

export async function listTransactions({
  start_date,
  end_date,
  type = "all",
  partner_name,
  limit = 50,
} = {}) {
  const domain = [["state", "=", "posted"]];

  if (start_date) domain.push(["invoice_date", ">=", start_date]);
  if (end_date) domain.push(["invoice_date", "<=", end_date]);

  // Type filter
  if (type === "invoice") {
    domain.push(["move_type", "=", "out_invoice"]);
  } else if (type === "bill") {
    domain.push(["move_type", "=", "in_invoice"]);
  } else if (type !== "all") {
    domain.push(["move_type", "in", ["out_invoice", "in_invoice"]]);
  } else {
    domain.push(["move_type", "in", ["out_invoice", "in_invoice"]]);
  }

  const records = await odooCall("account.move", "search_read", {
    domain,
    fields: [
      "name", "move_type", "partner_id", "amount_total",
      "amount_residual", "invoice_date", "invoice_date_due",
      "payment_state", "state",
    ],
    limit,
    order: "invoice_date desc",
  });

  // Optional partner name filter (client-side, Odoo ilike is too slow for large datasets)
  const filtered = partner_name
    ? records.filter((r) =>
        (r.partner_id?.[1] || "").toLowerCase().includes(partner_name.toLowerCase())
      )
    : records;

  return {
    total: filtered.length,
    transactions: filtered.map((r) => ({
      id: r.id,
      name: r.name,
      type: r.move_type === "out_invoice" ? "invoice" : "bill",
      partner: r.partner_id?.[1] || "Unknown",
      amount: r.amount_total,
      amount_due: r.amount_residual,
      date: r.invoice_date,
      due_date: r.invoice_date_due,
      payment_state: r.payment_state,
    })),
  };
}
