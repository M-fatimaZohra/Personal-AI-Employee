/**
 * gmail_auth.js — Shared OAuth2 client factory for all Gmail tools.
 *
 * Loads credentials and token from paths specified in environment variables
 * (resolved relative to the level-silver/ project root, one level above mcp-email-server/).
 *
 * Environment variables (loaded from level-silver/.env by index.js):
 *   GMAIL_CREDENTIALS_PATH  path to OAuth client secret JSON  (default: .secrets/gmail_credentials.json)
 *   GMAIL_TOKEN_PATH         path to saved OAuth token JSON    (default: .secrets/gmail_token.json)
 */

import { google } from "googleapis";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

// level-silver/ is one directory above mcp-email-server/
const SILVER_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

/**
 * Build and return an authenticated Google Gmail service client.
 * Throws if credential or token files are missing.
 */
export function getGmailClient() {
  const credentialsPath = path.resolve(
    SILVER_ROOT,
    process.env.GMAIL_CREDENTIALS_PATH || ".secrets/gmail_credentials.json"
  );
  const tokenPath = path.resolve(
    SILVER_ROOT,
    process.env.GMAIL_TOKEN_PATH || ".secrets/gmail_token.json"
  );

  if (!fs.existsSync(credentialsPath)) {
    throw new Error(
      `Gmail credentials not found at ${credentialsPath}. ` +
      "Download from Google Cloud Console and save as .secrets/gmail_credentials.json"
    );
  }
  if (!fs.existsSync(tokenPath)) {
    throw new Error(
      `Gmail token not found at ${tokenPath}. ` +
      "Run: uv run python gmail_watcher.py --auth-only"
    );
  }

  const credentials = JSON.parse(fs.readFileSync(credentialsPath, "utf8"));
  const token = JSON.parse(fs.readFileSync(tokenPath, "utf8"));

  const { client_id, client_secret, redirect_uris } =
    credentials.installed ?? credentials.web;

  const auth = new google.auth.OAuth2(client_id, client_secret, redirect_uris[0]);
  auth.setCredentials(token);

  return google.gmail({ version: "v1", auth });
}

/**
 * Build an RFC 2822 message and return its base64url-encoded form,
 * which is what the Gmail API expects for `raw`.
 */
export function buildRaw(to, subject, body) {
  const message = [
    `To: ${to}`,
    `Subject: ${subject}`,
    "Content-Type: text/plain; charset=utf-8",
    "MIME-Version: 1.0",
    "",
    body,
  ].join("\r\n");
  return Buffer.from(message).toString("base64url");
}
