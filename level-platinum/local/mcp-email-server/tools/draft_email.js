/**
 * draft_email tool — Create a Gmail draft.
 *
 * Unlike send_email, drafting does NOT require a HITL approval file —
 * it only creates a local Gmail draft; no email is sent.
 *
 * Environment variables:
 *   DRY_RUN  "true" to skip API call and return mock success
 */

import { getGmailClient, buildRaw } from "./gmail_auth.js";

const DRY_RUN = process.env.DRY_RUN === "true";

/**
 * @param {object} args
 * @param {string} args.to       Recipient email address
 * @param {string} args.subject  Email subject
 * @param {string} args.body     Email body (plain text)
 */
export async function draftEmail({ to, subject, body }) {
  // ── DRY_RUN ───────────────────────────────────────────────────────────────
  if (DRY_RUN) {
    process.stderr.write(
      `[mcp-email-server][DRY_RUN] draft_email → to=${to} subject="${subject}"\n`
    );
    return {
      content: [{
        type: "text",
        text: JSON.stringify({
          success: true,
          dry_run: true,
          draft_id: "dry_run_draft_id",
          to,
          subject,
          message: "DRY_RUN active — draft logged but not created.",
        }),
      }],
    };
  }

  // ── Create Gmail draft ────────────────────────────────────────────────────
  try {
    const gmail = getGmailClient();
    const raw = buildRaw(to, subject, body);
    const res = await gmail.users.drafts.create({
      userId: "me",
      requestBody: { message: { raw } },
    });

    process.stderr.write(
      `[mcp-email-server] draft_email OK → draft_id=${res.data.id} to=${to}\n`
    );
    return {
      content: [{
        type: "text",
        text: JSON.stringify({
          success: true,
          draft_id: res.data.id,
          to,
          subject,
        }),
      }],
    };
  } catch (err) {
    process.stderr.write(`[mcp-email-server] draft_email ERROR: ${err.message}\n`);
    return {
      content: [{
        type: "text",
        text: JSON.stringify({
          success: false,
          error: `Gmail draft creation failed: ${err.message}`,
          to,
          subject,
        }),
      }],
      isError: true,
    };
  }
}
