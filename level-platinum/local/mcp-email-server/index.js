/**
 * Silver FTE — Email MCP Server
 *
 * Exposes three Gmail tools to Claude Code:
 *   • send_email    — HITL-gated: validates approval file in /Approved before sending
 *   • draft_email   — Creates a Gmail draft (no approval needed, no email sent)
 *   • search_emails — Searches Gmail and returns metadata + snippet
 *
 * Transport: stdio (Claude Code spawns this process and communicates via stdin/stdout)
 *
 * Security:
 *   - Refuses to start if MCP_SERVER_SECRET is not set in the environment
 *   - DRY_RUN=true logs all actions without executing them
 *   - send_email checks that the approval file exists in /Approved before any send
 *
 * Setup (Claude Code mcp.json):
 *   {
 *     "mcpServers": {
 *       "email": {
 *         "command": "node",
 *         "args": ["<absolute-path-to>/level-silver/mcp-email-server/index.js"],
 *         "env": {
 *           "MCP_SERVER_SECRET": "<your-secret>",
 *           "GMAIL_CREDENTIALS_PATH": ".secrets/gmail_credentials.json",
 *           "GMAIL_TOKEN_PATH": ".secrets/gmail_token.json",
 *           "DRY_RUN": "false"
 *         }
 *       }
 *     }
 *   }
 *   Note: env paths are resolved relative to level-silver/ (parent of this server)
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import dotenv from "dotenv";
import path from "path";
import { fileURLToPath } from "url";

import { sendEmail } from "./tools/send_email.js";
import { draftEmail } from "./tools/draft_email.js";
import { searchEmails } from "./tools/search_emails.js";

// ── Load environment ────────────────────────────────────────────────────────
// Load from level-silver/.env (parent directory) then allow local override
const SILVER_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
dotenv.config({ path: path.join(SILVER_ROOT, ".env") });
dotenv.config({ path: path.join(path.dirname(fileURLToPath(import.meta.url)), ".env") });

// ── Startup security validation ─────────────────────────────────────────────
if (!process.env.MCP_SERVER_SECRET) {
  process.stderr.write(
    "[mcp-email-server] FATAL: MCP_SERVER_SECRET is not set.\n" +
    "  Set it in level-silver/.env or pass it via Claude Code mcp.json env block.\n" +
    "  Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\"\n"
  );
  process.exit(1);
}

process.stderr.write("[mcp-email-server] Starting silver-fte email MCP server...\n");
if (process.env.DRY_RUN === "true") {
  process.stderr.write("[mcp-email-server] DRY_RUN mode active — no emails will be sent.\n");
}

// ── Create MCP server ────────────────────────────────────────────────────────
const server = new McpServer({
  name: "silver-fte-email",
  version: "1.0.0",
});

// ── Tool: send_email ─────────────────────────────────────────────────────────
server.registerTool(
  "send_email",
  {
    title: "Send Email (HITL-gated)",
    description:
      "Send an email via Gmail API. " +
      "REQUIRES a corresponding approval file to exist in AI_Employee_Vault/Approved/ — " +
      "the user must have moved it there from Pending_Approval/. " +
      "Rejects with an error if no approval file is found.",
    inputSchema: z.object({
      to: z.string().describe("Recipient email address"),
      subject: z.string().describe("Email subject line"),
      body: z.string().describe("Email body (plain text)"),
      approval_file: z.string().describe(
        "Filename of the approval file in Approved/ (e.g. APPROVAL_email_reply_abc123.md). " +
        "This file must exist before the email is sent."
      ),
    }),
  },
  async (args) => sendEmail(args)
);

// ── Tool: draft_email ────────────────────────────────────────────────────────
server.registerTool(
  "draft_email",
  {
    title: "Draft Email",
    description:
      "Create a Gmail draft. No email is sent — the draft is saved in Gmail for manual review. " +
      "No approval file is required. Returns the Gmail draft ID.",
    inputSchema: z.object({
      to: z.string().describe("Recipient email address"),
      subject: z.string().describe("Email subject line"),
      body: z.string().describe("Email body (plain text)"),
    }),
  },
  async (args) => draftEmail(args)
);

// ── Tool: search_emails ──────────────────────────────────────────────────────
server.registerTool(
  "search_emails",
  {
    title: "Search Emails",
    description:
      "Search Gmail using Gmail query syntax. " +
      "Returns subject, from, date, and snippet for each match. " +
      "Examples: 'from:boss@company.com is:unread', 'subject:invoice is:important'.",
    inputSchema: z.object({
      query: z.string().describe("Gmail search query string"),
      max_results: z
        .number()
        .int()
        .min(1)
        .max(50)
        .optional()
        .describe("Maximum number of results to return (1–50, default 10)"),
    }),
  },
  async (args) => searchEmails(args)
);

// ── Connect transport and start ──────────────────────────────────────────────
const transport = new StdioServerTransport();
await server.connect(transport);
process.stderr.write("[mcp-email-server] Ready — listening on stdio.\n");
