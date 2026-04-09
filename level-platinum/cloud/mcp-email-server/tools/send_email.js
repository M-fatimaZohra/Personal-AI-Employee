/**
 * send_email tool — Send an email via Gmail API.
 *
 * Security contract (HITL-gated):
 *   1. Caller must provide the approval_file filename.
 *   2. This tool verifies the file exists in <VAULT_PATH>/Approved/ before sending.
 *   3. If the file is absent → reject with "No approval found" error.
 *   4. If DRY_RUN=true → log intent and return success without sending.
 *   5. On success → the approval file is NOT moved here; approval_watcher.py handles Done/.
 *
 * Environment variables (from level-silver/.env):
 *   VAULT_PATH   path to AI_Employee_Vault (default: ../AI_Employee_Vault relative to mcp-email-server/)
 *   DRY_RUN      "true" to skip sending
 */

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { getGmailClient, buildRaw } from "./gmail_auth.js";

// SILVER_ROOT = level-silver/ (two levels above tools/)
const SILVER_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
// Always resolve VAULT_PATH relative to SILVER_ROOT so cwd doesn't matter
const VAULT_PATH = path.resolve(
  SILVER_ROOT,
  process.env.VAULT_PATH || "AI_Employee_Vault"
);

const DRY_RUN = process.env.DRY_RUN === "true";

/**
 * @param {object} args
 * @param {string} args.to             Recipient email address
 * @param {string} args.subject        Email subject
 * @param {string} args.body           Email body (plain text)
 * @param {string} args.approval_file  Filename of approval file in Approved/ (e.g. APPROVAL_abc.md)
 */
export async function sendEmail({ to, subject, body, approval_file }) {
  // ── INVARIANT-2: Cloud agent SEND_ALLOWED check ───────────────────────────
  // Cloud agent must NEVER send emails — only draft them
  if (process.env.SEND_ALLOWED === "false") {
    return {
      content: [{
        type: "text",
        text: JSON.stringify({
          success: false,
          error: "Cloud agent cannot send. Draft only. SEND_ALLOWED=false enforces draft-only mode.",
          to,
          subject,
          approval_file,
        }),
      }],
      isError: true,
    };
  }

  // ── HITL gate: approval file must exist in /Approved ──────────────────────
  const approvedPath = path.join(VAULT_PATH, "Approved", approval_file);
  if (!fs.existsSync(approvedPath)) {
    return {
      content: [{
        type: "text",
        text: JSON.stringify({
          success: false,
          error: `No approval found: '${approval_file}' does not exist in Approved/. ` +
                 "The user must move the file from Pending_Approval/ to Approved/ before sending.",
          approval_file,
        }),
      }],
      isError: true,
    };
  }

  // ── DRY_RUN: log but do not send ───────────────────────────────────────────
  if (DRY_RUN) {
    process.stderr.write(
      `[mcp-email-server][DRY_RUN] send_email → to=${to} subject="${subject}" approval_file=${approval_file}\n`
    );
    return {
      content: [{
        type: "text",
        text: JSON.stringify({
          success: true,
          dry_run: true,
          to,
          subject,
          approval_file,
          message: "DRY_RUN active — email logged but not sent.",
        }),
      }],
    };
  }

  // ── Send via Gmail API ─────────────────────────────────────────────────────
  try {
    const gmail = getGmailClient();
    const raw = buildRaw(to, subject, body);
    const res = await gmail.users.messages.send({
      userId: "me",
      requestBody: { raw },
    });

    process.stderr.write(
      `[mcp-email-server] send_email OK → message_id=${res.data.id} to=${to}\n`
    );

    // ── Inbox sync: archive the original thread after sending ─────────────────
    // Remove INBOX + UNREAD labels so the thread leaves the inbox automatically.
    // This is non-fatal: a failed archive never blocks the send success response.
    const sentThreadId = res.data.threadId;
    if (sentThreadId) {
      try {
        await gmail.users.threads.modify({
          userId: "me",
          id: sentThreadId,
          requestBody: { removeLabelIds: ["INBOX", "UNREAD"] },
        });
        process.stderr.write(
          `[mcp-email-server] inbox_sync OK → archived thread ${sentThreadId}\n`
        );
      } catch (archiveErr) {
        // Log but do not fail — the email was already sent successfully
        process.stderr.write(
          `[mcp-email-server] inbox_sync WARN → could not archive thread ${sentThreadId}: ${archiveErr.message}\n`
        );
      }
    }

    return {
      content: [{
        type: "text",
        text: JSON.stringify({
          success: true,
          message_id: res.data.id,
          thread_id: res.data.threadId,
          thread_archived: !!sentThreadId,
          to,
          subject,
          approval_file,
        }),
      }],
    };
  } catch (err) {
    process.stderr.write(`[mcp-email-server] send_email ERROR: ${err.message}\n`);
    return {
      content: [{
        type: "text",
        text: JSON.stringify({
          success: false,
          error: `Gmail send failed: ${err.message}`,
          to,
          subject,
          approval_file,
        }),
      }],
      isError: true,
    };
  }
}
