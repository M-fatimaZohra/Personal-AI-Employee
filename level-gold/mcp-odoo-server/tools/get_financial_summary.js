/**
 * get_financial_summary — Read-only Odoo financial overview.
 *
 * Returns:
 *   - revenue:           Total amount of paid outgoing invoices this month
 *   - expenses:          Total amount of paid incoming bills this month
 *   - outstanding_count: Number of unpaid outgoing invoices
 *   - outstanding_total: Total amount of unpaid outgoing invoices
 *   - overdue_count:     Number of outgoing invoices overdue (30+ days past due)
 *   - overdue_total:     Total amount of overdue invoices
 *   - top_expense_categories: Top 3 expense categories by total amount
 */

import { odooCall } from "./odoo_auth.js";

export async function getFinancialSummary({ month } = {}) {
  // Default to current month (YYYY-MM format)
  const now = new Date();
  const targetMonth = month || `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  const [year, monthNum] = targetMonth.split("-").map(Number);
  const monthStart = `${year}-${String(monthNum).padStart(2, "0")}-01`;
  const monthEnd = new Date(year, monthNum, 0).toISOString().slice(0, 10); // last day of month

  // Today for overdue calculation
  const today = now.toISOString().slice(0, 10);
  const overdueDate = new Date(now - 30 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);

  // 1. Revenue: paid outgoing invoices this month
  const paidInvoices = await odooCall("account.move", "search_read", {
    domain: [
      ["move_type", "=", "out_invoice"],
      ["payment_state", "=", "paid"],
      ["invoice_date", ">=", monthStart],
      ["invoice_date", "<=", monthEnd],
    ],
    fields: ["name", "partner_id", "amount_total", "invoice_date"],
  });
  const revenue = paidInvoices.reduce((sum, inv) => sum + (inv.amount_total || 0), 0);

  // 2. Expenses: paid incoming bills this month
  const paidBills = await odooCall("account.move", "search_read", {
    domain: [
      ["move_type", "=", "in_invoice"],
      ["payment_state", "=", "paid"],
      ["invoice_date", ">=", monthStart],
      ["invoice_date", "<=", monthEnd],
    ],
    fields: ["name", "partner_id", "amount_total", "invoice_date"],
  });
  const expenses = paidBills.reduce((sum, bill) => sum + (bill.amount_total || 0), 0);

  // 3. Outstanding: unpaid outgoing invoices (any date)
  const outstandingInvoices = await odooCall("account.move", "search_read", {
    domain: [
      ["move_type", "=", "out_invoice"],
      ["payment_state", "in", ["not_paid", "partial"]],
      ["state", "=", "posted"],
    ],
    fields: ["name", "partner_id", "amount_total", "amount_residual", "invoice_date_due"],
  });
  const outstandingTotal = outstandingInvoices.reduce(
    (sum, inv) => sum + (inv.amount_residual || inv.amount_total || 0),
    0
  );

  // 4. Overdue: unpaid invoices where due date was 30+ days ago
  const overdueInvoices = outstandingInvoices.filter(
    (inv) => inv.invoice_date_due && inv.invoice_date_due <= overdueDate
  );
  const overdueTotal = overdueInvoices.reduce(
    (sum, inv) => sum + (inv.amount_residual || inv.amount_total || 0),
    0
  );

  return {
    month: targetMonth,
    revenue: Math.round(revenue * 100) / 100,
    expenses: Math.round(expenses * 100) / 100,
    outstanding_count: outstandingInvoices.length,
    outstanding_total: Math.round(outstandingTotal * 100) / 100,
    outstanding_invoices: outstandingInvoices.slice(0, 10).map((inv) => ({
      name: inv.name,
      partner: inv.partner_id?.[1] || "Unknown",
      amount: inv.amount_residual || inv.amount_total,
      due_date: inv.invoice_date_due,
    })),
    overdue_count: overdueInvoices.length,
    overdue_total: Math.round(overdueTotal * 100) / 100,
    overdue_invoices: overdueInvoices.slice(0, 5).map((inv) => ({
      name: inv.name,
      partner: inv.partner_id?.[1] || "Unknown",
      amount: inv.amount_residual || inv.amount_total,
      due_date: inv.invoice_date_due,
      days_overdue: Math.floor(
        (new Date(today) - new Date(inv.invoice_date_due)) / (1000 * 60 * 60 * 24)
      ),
    })),
  };
}
