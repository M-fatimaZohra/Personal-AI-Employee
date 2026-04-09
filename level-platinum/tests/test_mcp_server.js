/**
 * test_mcp_server.js — MCP email server unit tests
 *
 * Tests three behaviours:
 *   1. MCP server startup auth — refuses to start without MCP_SERVER_SECRET
 *   2. send_email HITL approval gate — rejects when approval file is absent
 *   3. send_email DRY_RUN mode — succeeds without touching Gmail API
 *
 * Design note:
 *   send_email.js reads VAULT_PATH and DRY_RUN as module-level constants at
 *   import time. Each test scenario spawns a fresh Node.js subprocess with the
 *   required env vars so those constants are set correctly per test.
 *
 * Run: node --test tests/test_mcp_server.js
 */

import { spawnSync } from "child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "fs";
import { tmpdir } from "os";
import { join, dirname } from "path";
import { fileURLToPath, pathToFileURL } from "url";
import assert from "node:assert/strict";
import { test, describe } from "node:test";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const SILVER_ROOT = join(__dirname, "..");
const MCP_INDEX = join(SILVER_ROOT, "mcp-email-server", "index.js");
const SEND_EMAIL_PATH = join(SILVER_ROOT, "mcp-email-server", "tools", "send_email.js");

// file:// URL is required for dynamic ESM imports on Windows
const SEND_EMAIL_URL = pathToFileURL(SEND_EMAIL_PATH).href;

// ── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Spawn an inline ESM script as a Node subprocess with controlled env vars.
 * Returns the spawnSync result (status, stdout, stderr).
 */
function runScript(script, extraEnv = {}) {
  return spawnSync("node", ["--input-type=module"], {
    input: script,
    env: { ...process.env, ...extraEnv },
    encoding: "utf8",
    timeout: 15000,
  });
}

/**
 * Create a temp directory that mimics AI_Employee_Vault structure.
 * Optionally write an approval file inside Approved/.
 * Returns the tmpDir path (caller must clean up with rmSync).
 */
function makeTempVault(approvalFile = null) {
  const tmpDir = mkdtempSync(join(tmpdir(), "fte-test-vault-"));
  const approvedDir = join(tmpDir, "Approved");
  mkdirSync(approvedDir, { recursive: true });
  if (approvalFile) {
    writeFileSync(
      join(approvedDir, approvalFile),
      "# Approval\nstatus: approved\n"
    );
  }
  return tmpDir;
}

// ── Suite 1: MCP Server Startup Authentication ───────────────────────────────

describe("MCP Server — startup authentication", () => {
  test("exits non-zero when MCP_SERVER_SECRET is absent", () => {
    // Set to empty string rather than deleting: dotenv won't override an already-set
    // env var, so "" stays falsy and triggers the FATAL guard in index.js.
    const env = { ...process.env, MCP_SERVER_SECRET: "" };

    const result = spawnSync("node", [MCP_INDEX], {
      env,
      encoding: "utf8",
      timeout: 5000,
    });

    assert.notEqual(result.status, 0, "Expected non-zero exit code");
    assert.ok(
      result.stderr.includes("FATAL"),
      `Expected FATAL in stderr; got: ${result.stderr}`
    );
    assert.ok(
      result.stderr.includes("MCP_SERVER_SECRET"),
      "Expected MCP_SERVER_SECRET mentioned in error"
    );
  });
});

// ── Suite 2: send_email HITL Approval Gate ───────────────────────────────────

describe("send_email — HITL approval gate", () => {
  test("rejects with 'No approval found' when approval file is absent", () => {
    const vaultDir = makeTempVault(); // No approval file
    try {
      const script = `
        import { sendEmail } from '${SEND_EMAIL_URL}';
        const result = await sendEmail({
          to: "test@example.com",
          subject: "Test",
          body: "Hello",
          approval_file: "APPROVAL_missing_abc.md",
        });
        const data = JSON.parse(result.content[0].text);
        if (!data.success && data.error.includes("No approval found")) {
          process.exit(0);
        }
        process.stderr.write("FAIL: " + JSON.stringify(data) + "\\n");
        process.exit(1);
      `;
      const r = runScript(script, { VAULT_PATH: vaultDir, DRY_RUN: "false" });
      assert.equal(r.status, 0, r.stderr);
    } finally {
      rmSync(vaultDir, { recursive: true, force: true });
    }
  });

  test("rejection response has isError: true", () => {
    const vaultDir = makeTempVault();
    try {
      const script = `
        import { sendEmail } from '${SEND_EMAIL_URL}';
        const result = await sendEmail({
          to: "test@example.com",
          subject: "Test",
          body: "Hello",
          approval_file: "APPROVAL_missing.md",
        });
        if (result.isError === true) { process.exit(0); }
        process.stderr.write("FAIL isError=" + result.isError + "\\n");
        process.exit(1);
      `;
      const r = runScript(script, { VAULT_PATH: vaultDir, DRY_RUN: "false" });
      assert.equal(r.status, 0, r.stderr);
    } finally {
      rmSync(vaultDir, { recursive: true, force: true });
    }
  });

  test("rejection error message contains the approval_file filename", () => {
    const vaultDir = makeTempVault();
    const approvalFile = "APPROVAL_specific_xyz.md";
    try {
      const script = `
        import { sendEmail } from '${SEND_EMAIL_URL}';
        const result = await sendEmail({
          to: "test@example.com",
          subject: "Test",
          body: "Hello",
          approval_file: ${JSON.stringify(approvalFile)},
        });
        const data = JSON.parse(result.content[0].text);
        if (data.error && data.error.includes(${JSON.stringify(approvalFile)})) {
          process.exit(0);
        }
        process.stderr.write("FAIL error=" + data.error + "\\n");
        process.exit(1);
      `;
      const r = runScript(script, { VAULT_PATH: vaultDir, DRY_RUN: "false" });
      assert.equal(r.status, 0, r.stderr);
    } finally {
      rmSync(vaultDir, { recursive: true, force: true });
    }
  });

  test("gate passes (no 'No approval found' error) when approval file is present", () => {
    const approvalFile = "APPROVAL_present.md";
    const vaultDir = makeTempVault(approvalFile);
    try {
      const script = `
        import { sendEmail } from '${SEND_EMAIL_URL}';
        const result = await sendEmail({
          to: "test@example.com",
          subject: "Test",
          body: "Hello",
          approval_file: ${JSON.stringify(approvalFile)},
        });
        const data = JSON.parse(result.content[0].text);
        if (data.error && data.error.includes("No approval found")) {
          process.stderr.write("FAIL: gate rejected despite file present\\n");
          process.exit(1);
        }
        process.exit(0);
      `;
      // DRY_RUN=true so we never need real Gmail creds — just testing the gate
      const r = runScript(script, { VAULT_PATH: vaultDir, DRY_RUN: "true" });
      assert.equal(r.status, 0, r.stderr);
    } finally {
      rmSync(vaultDir, { recursive: true, force: true });
    }
  });

  test("approval file in wrong folder (not Approved/) still rejects", () => {
    // Put the file in the vault root, NOT in Approved/ subdir
    const vaultDir = makeTempVault();
    const approvalFile = "APPROVAL_wrong_location.md";
    writeFileSync(join(vaultDir, approvalFile), "# Approval\n"); // vault root, not /Approved
    try {
      const script = `
        import { sendEmail } from '${SEND_EMAIL_URL}';
        const result = await sendEmail({
          to: "test@example.com",
          subject: "Test",
          body: "Hello",
          approval_file: ${JSON.stringify(approvalFile)},
        });
        const data = JSON.parse(result.content[0].text);
        if (!data.success && data.error.includes("No approval found")) {
          process.exit(0);
        }
        process.stderr.write("FAIL: unexpectedly passed gate: " + JSON.stringify(data) + "\\n");
        process.exit(1);
      `;
      const r = runScript(script, { VAULT_PATH: vaultDir, DRY_RUN: "false" });
      assert.equal(r.status, 0, r.stderr);
    } finally {
      rmSync(vaultDir, { recursive: true, force: true });
    }
  });
});

// ── Suite 3: send_email DRY_RUN Mode ─────────────────────────────────────────

describe("send_email — DRY_RUN mode", () => {
  test("returns success with dry_run: true when DRY_RUN=true and approval file exists", () => {
    const approvalFile = "APPROVAL_dry_run.md";
    const vaultDir = makeTempVault(approvalFile);
    try {
      const script = `
        import { sendEmail } from '${SEND_EMAIL_URL}';
        const result = await sendEmail({
          to: "test@example.com",
          subject: "DRY RUN",
          body: "Should not be sent",
          approval_file: ${JSON.stringify(approvalFile)},
        });
        const data = JSON.parse(result.content[0].text);
        if (data.success && data.dry_run === true) { process.exit(0); }
        process.stderr.write("FAIL: " + JSON.stringify(data) + "\\n");
        process.exit(1);
      `;
      const r = runScript(script, { VAULT_PATH: vaultDir, DRY_RUN: "true" });
      assert.equal(r.status, 0, r.stderr);
    } finally {
      rmSync(vaultDir, { recursive: true, force: true });
    }
  });

  test("DRY_RUN response echoes back to, subject, and approval_file", () => {
    const approvalFile = "APPROVAL_echo.md";
    const vaultDir = makeTempVault(approvalFile);
    const to = "echo@example.com";
    const subject = "Echo Check";
    try {
      const script = `
        import { sendEmail } from '${SEND_EMAIL_URL}';
        const result = await sendEmail({
          to: ${JSON.stringify(to)},
          subject: ${JSON.stringify(subject)},
          body: "Body",
          approval_file: ${JSON.stringify(approvalFile)},
        });
        const data = JSON.parse(result.content[0].text);
        if (
          data.to === ${JSON.stringify(to)} &&
          data.subject === ${JSON.stringify(subject)} &&
          data.approval_file === ${JSON.stringify(approvalFile)}
        ) {
          process.exit(0);
        }
        process.stderr.write("FAIL fields: " + JSON.stringify(data) + "\\n");
        process.exit(1);
      `;
      const r = runScript(script, { VAULT_PATH: vaultDir, DRY_RUN: "true" });
      assert.equal(r.status, 0, r.stderr);
    } finally {
      rmSync(vaultDir, { recursive: true, force: true });
    }
  });

  test("DRY_RUN does not set isError on the response", () => {
    const approvalFile = "APPROVAL_no_error.md";
    const vaultDir = makeTempVault(approvalFile);
    try {
      const script = `
        import { sendEmail } from '${SEND_EMAIL_URL}';
        const result = await sendEmail({
          to: "test@example.com",
          subject: "Test",
          body: "Body",
          approval_file: ${JSON.stringify(approvalFile)},
        });
        if (!result.isError) { process.exit(0); }
        process.stderr.write("FAIL isError=" + result.isError + "\\n");
        process.exit(1);
      `;
      // No real Gmail creds — confirms DRY_RUN never touches the Gmail API
      const r = runScript(script, {
        VAULT_PATH: vaultDir,
        DRY_RUN: "true",
        GMAIL_CREDENTIALS_PATH: "/nonexistent/creds.json",
        GMAIL_TOKEN_PATH: "/nonexistent/token.json",
      });
      assert.equal(r.status, 0, r.stderr);
    } finally {
      rmSync(vaultDir, { recursive: true, force: true });
    }
  });

  test("DRY_RUN=false with missing Gmail creds returns Gmail error (not approval error)", () => {
    // Approval file IS present — gate passes — then Gmail fails on missing creds
    const approvalFile = "APPROVAL_creds_test.md";
    const vaultDir = makeTempVault(approvalFile);
    try {
      const script = `
        import { sendEmail } from '${SEND_EMAIL_URL}';
        const result = await sendEmail({
          to: "test@example.com",
          subject: "Test",
          body: "Hello",
          approval_file: ${JSON.stringify(approvalFile)},
        });
        const data = JSON.parse(result.content[0].text);
        // Should fail at Gmail step, not at approval gate
        const isGmailError = (
          !data.success &&
          data.error &&
          (data.error.includes("Gmail") || data.error.includes("credentials") ||
           data.error.includes("token") || data.error.includes("ENOENT"))
        );
        const isApprovalError = data.error && data.error.includes("No approval found");
        if (isGmailError && !isApprovalError) {
          process.exit(0);
        }
        process.stderr.write("FAIL: " + JSON.stringify(data) + "\\n");
        process.exit(1);
      `;
      const r = runScript(script, {
        VAULT_PATH: vaultDir,
        DRY_RUN: "false",
        GMAIL_CREDENTIALS_PATH: "/nonexistent/credentials.json",
        GMAIL_TOKEN_PATH: "/nonexistent/token.json",
      });
      assert.equal(r.status, 0, r.stderr);
    } finally {
      rmSync(vaultDir, { recursive: true, force: true });
    }
  });
});
