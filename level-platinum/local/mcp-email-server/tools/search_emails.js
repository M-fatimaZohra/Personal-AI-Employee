/**
 * search_emails tool — Search Gmail using Gmail query syntax.
 *
 * Returns subject, from, date, and snippet for each result.
 * Fetches metadata only (no full body) to keep responses fast.
 *
 * DRY_RUN has no special behaviour here (read-only operation — safe to run always).
 */

import { getGmailClient } from "./gmail_auth.js";

/**
 * @param {object} args
 * @param {string} args.query        Gmail search query (e.g. "from:boss@company.com is:unread")
 * @param {number} [args.max_results] Max results to return (1–50, default 10)
 */
export async function searchEmails({ query, max_results = 10 }) {
  try {
    const gmail = getGmailClient();

    // List matching message IDs
    const listRes = await gmail.users.messages.list({
      userId: "me",
      q: query,
      maxResults: max_results,
    });

    const messages = listRes.data.messages ?? [];
    if (messages.length === 0) {
      return {
        content: [{
          type: "text",
          text: JSON.stringify({ success: true, query, results: [], count: 0 }),
        }],
      };
    }

    // Fetch metadata (headers + snippet) for each message in parallel
    const results = await Promise.all(
      messages.map(async ({ id }) => {
        const detail = await gmail.users.messages.get({
          userId: "me",
          id,
          format: "metadata",
          metadataHeaders: ["From", "To", "Subject", "Date"],
        });
        const headerMap = Object.fromEntries(
          (detail.data.payload?.headers ?? []).map(h => [h.name, h.value])
        );
        return {
          id,
          thread_id: detail.data.threadId ?? null,
          from: headerMap["From"] ?? "",
          to: headerMap["To"] ?? "",
          subject: headerMap["Subject"] ?? "(no subject)",
          date: headerMap["Date"] ?? "",
          snippet: detail.data.snippet ?? "",
        };
      })
    );

    return {
      content: [{
        type: "text",
        text: JSON.stringify({ success: true, query, results, count: results.length }),
      }],
    };
  } catch (err) {
    process.stderr.write(`[mcp-email-server] search_emails ERROR: ${err.message}\n`);
    return {
      content: [{
        type: "text",
        text: JSON.stringify({
          success: false,
          error: `Gmail search failed: ${err.message}`,
          query,
        }),
      }],
      isError: true,
    };
  }
}
