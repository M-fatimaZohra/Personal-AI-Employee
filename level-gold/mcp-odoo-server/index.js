/**
 * mcp-odoo-server — MCP server for Odoo Community accounting integration.
 *
 * Tools (read-only, no approval needed):
 *   - get_financial_summary   Monthly P&L snapshot, outstanding/overdue invoices
 *   - list_transactions       Search/filter invoices and bills
 *
 * Tools (write, HITL-gated — require approval file in /Approved/):
 *   - create_invoice          Create and post a new customer invoice
 *   - create_partner          Create a new customer or vendor
 *
 * Transport: stdio (Claude Code native)
 *
 * Required env vars (set in ~/.claude/settings.json mcpServers.odoo.env):
 *   ODOO_URL      — http://localhost:8069
 *   ODOO_DB       — fte_business
 *   ODOO_API_KEY  — from Settings → Users → Administrator → API Keys
 *   VAULT_PATH    — AI_Employee_Vault (relative to cwd or absolute)
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { config } from "dotenv";
import { validateConnection } from "./tools/odoo_auth.js";
import { getFinancialSummary } from "./tools/get_financial_summary.js";
import { listTransactions } from "./tools/list_transactions.js";
import { createInvoice } from "./tools/create_invoice.js";
import { createPartner } from "./tools/create_partner.js";

// Load .env from parent directory (level-gold/.env)
config({ path: "../.env" });

const server = new McpServer({
  name: "odoo",
  version: "1.0.0",
});

// ---------------------------------------------------------------------------
// Tool: get_financial_summary
// ---------------------------------------------------------------------------
server.tool(
  "get_financial_summary",
  "Get monthly financial overview from Odoo: revenue, expenses, outstanding invoices, overdue invoices. Read-only — no approval needed.",
  {
    month: z
      .string()
      .optional()
      .describe("Month in YYYY-MM format (default: current month)"),
  },
  async ({ month }) => {
    try {
      const summary = await getFinancialSummary({ month });
      return {
        content: [{ type: "text", text: JSON.stringify(summary, null, 2) }],
      };
    } catch (err) {
      return {
        content: [{ type: "text", text: `Error: ${err.message}` }],
        isError: true,
      };
    }
  }
);

// ---------------------------------------------------------------------------
// Tool: list_transactions
// ---------------------------------------------------------------------------
server.tool(
  "list_transactions",
  "Search and filter Odoo invoices and bills by date range, type, and partner. Read-only — no approval needed.",
  {
    start_date: z.string().optional().describe("Start date YYYY-MM-DD"),
    end_date: z.string().optional().describe("End date YYYY-MM-DD"),
    type: z
      .enum(["invoice", "bill", "all"])
      .optional()
      .default("all")
      .describe("Transaction type filter"),
    partner_name: z.string().optional().describe("Filter by customer/vendor name (partial match)"),
    limit: z.number().optional().default(50).describe("Max results (default 50)"),
  },
  async ({ start_date, end_date, type, partner_name, limit }) => {
    try {
      const result = await listTransactions({ start_date, end_date, type, partner_name, limit });
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
      };
    } catch (err) {
      return {
        content: [{ type: "text", text: `Error: ${err.message}` }],
        isError: true,
      };
    }
  }
);

// ---------------------------------------------------------------------------
// Tool: create_invoice  (HITL-gated)
// ---------------------------------------------------------------------------
server.tool(
  "create_invoice",
  "Create and post a customer invoice in Odoo. REQUIRES approval file in AI_Employee_Vault/Approved/ before execution.",
  {
    partner_id: z.number().describe("Odoo partner (customer) ID"),
    amount: z.number().positive().describe("Invoice total amount"),
    due_date: z.string().describe("Due date in YYYY-MM-DD format"),
    approval_file: z
      .string()
      .describe("Filename of approval file in Approved/ (e.g. APPROVAL_invoice_abc123.md)"),
    description: z.string().optional().default("Services").describe("Line item description"),
    currency_id: z.number().optional().default(1).describe("Odoo currency ID (default: 1 = USD)"),
  },
  async ({ partner_id, amount, due_date, approval_file, description, currency_id }) => {
    try {
      const result = await createInvoice({
        partner_id,
        amount,
        due_date,
        approval_file,
        description,
        currency_id,
      });
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
      };
    } catch (err) {
      return {
        content: [{ type: "text", text: `Error: ${err.message}` }],
        isError: true,
      };
    }
  }
);

// ---------------------------------------------------------------------------
// Tool: create_partner  (HITL-gated)
// ---------------------------------------------------------------------------
server.tool(
  "create_partner",
  "Create a new customer or vendor in Odoo. REQUIRES approval file in AI_Employee_Vault/Approved/ before execution.",
  {
    name: z.string().describe("Partner full name"),
    approval_file: z
      .string()
      .describe("Filename of approval file in Approved/ (e.g. APPROVAL_partner_abc123.md)"),
    email: z.string().optional().describe("Contact email (used for deduplication)"),
    phone: z.string().optional().describe("Contact phone number"),
    is_company: z.boolean().optional().default(true).describe("True for company, false for individual"),
    customer_rank: z.number().optional().default(1).describe("1 = customer, 0 = not a customer"),
    supplier_rank: z.number().optional().default(0).describe("1 = vendor, 0 = not a vendor"),
  },
  async ({ name, approval_file, email, phone, is_company, customer_rank, supplier_rank }) => {
    try {
      const result = await createPartner({
        name,
        approval_file,
        email,
        phone,
        is_company,
        customer_rank,
        supplier_rank,
      });
      return {
        content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
      };
    } catch (err) {
      return {
        content: [{ type: "text", text: `Error: ${err.message}` }],
        isError: true,
      };
    }
  }
);

// ---------------------------------------------------------------------------
// Start server
// ---------------------------------------------------------------------------
async function main() {
  // Validate Odoo connection on startup (warn only — don't crash)
  const connected = await validateConnection();
  if (!connected) {
    console.error(
      "[mcp-odoo] WARNING: Cannot connect to Odoo at",
      process.env.ODOO_URL || "http://localhost:8069",
      "— check ODOO_URL, ODOO_DB, ODOO_API_KEY and ensure Docker is running."
    );
  } else {
    console.error("[mcp-odoo] Connected to Odoo — 4 tools ready.");
  }

  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("[mcp-odoo] MCP Odoo Server ready — listening on stdio");
}

main().catch((err) => {
  console.error("[mcp-odoo] Fatal startup error:", err);
  process.exit(1);
});
