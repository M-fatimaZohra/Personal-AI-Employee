# Feature Specification: Silver Tier — Functional Assistant

**Feature Branch**: `002-silver-tier`
**Created**: 2026-02-18
**Status**: Draft
**Input**: User description: "Create specifications for silver tier level. Make sure write correct information with $0 cost working. Security is top priority. We will make copy of bronze in new /silver folder and continue work there for silver tier."
**Prerequisite**: Bronze tier complete (001-bronze-tier) — filesystem watcher, 3 agent skills, vault, dashboard, handbook, logging

## Constraints & Non-Goals

### Constraints
- **$0 cost**: All services, APIs, and tools must be free-tier or open-source. No paid subscriptions, no paid API keys.
- **Security first**: No credentials in code or vault. All secrets via environment variables. All external actions require human approval. DRY_RUN mode for all new capabilities.
- **Bronze as foundation**: Silver tier copies `/level-bronze` to `/level-silver` and extends it. Bronze remains untouched.
- **Local-first**: All data stays on the local machine. No cloud storage of personal data.
- **Windows 11 environment**: Must work on Windows 11 with Python 3.13+ via `uv`.

### Non-Goals
- Paid API access (no Google Workspace paid plans, no LinkedIn premium API)
- Cloud deployment (Platinum tier scope)
- Playwright-based WhatsApp automation (replaced by Baileys Node.js bridge using `@whiskeysockets/baileys`)
- whatsapp-web.js / Puppeteer-based WhatsApp approach (bot-detection failure — superseded by Baileys)
- Autonomous actions without human approval (Gold/Platinum scope)
- Odoo integration (Gold tier scope)
- Ralph Wiggum autonomous loop (Gold tier scope)

### Assumptions
- User has a personal Gmail account (free, not Google Workspace)
- User has a LinkedIn account (free tier)
- User has Node.js v24+ installed for MCP server
- Gmail API free tier (15,000 queries/day) is sufficient for personal use
- LinkedIn does not offer free API posting for personal accounts — drafting + manual posting approach used
- WhatsApp watcher is a Node.js ESM process using `@whiskeysockets/baileys` (not Playwright, not whatsapp-web.js) — QR scan once via `qrcode-terminal`, session persists via `useMultiFileAuthState` in `.secrets/whatsapp_session/`; single process handles both receiving messages and sending approved replies autonomously; WhatsApp treats it as a real linked device (pure WebSocket, no browser/CDP)
- Windows Task Scheduler used for scheduling (free, built-in)

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Gmail Watcher Detects and Triages Emails (Priority: P1)

As a user, I want my AI employee to monitor my Gmail inbox for new important/unread emails and create action files in the vault so I can see them in Obsidian and decide how to respond.

**Why this priority**: Email is the most common communication channel for both personal and business affairs. Monitoring Gmail turns the AI from a file-processing tool into a real communication assistant. This is the core Silver upgrade.

**Independent Test**: Configure Gmail OAuth credentials, start the Gmail watcher, receive an email marked as important, verify an `EMAIL_<id>.md` file appears in `/Needs_Action` with correct sender, subject, date, and content. Verify Dashboard.md updates to show the email.

**Acceptance Scenarios**:

1. **Given** the Gmail watcher is running with valid credentials, **When** a new unread important email arrives, **Then** an `EMAIL_<id>.md` file is created in `/Needs_Action` within 2 minutes with YAML frontmatter (type: email, from, subject, received, priority, status: needs_action) and email body content.
2. **Given** the Gmail watcher has processed an email, **When** the same email is checked again on the next poll, **Then** it is not processed a second time (deduplication via processed IDs).
3. **Given** the Gmail watcher cannot reach the Gmail API, **When** a network error occurs, **Then** the watcher logs the error, waits with exponential backoff, and retries without crashing.
4. **Given** no valid credentials are configured, **When** the watcher starts, **Then** it logs a clear error message and exits gracefully without exposing credential details.

---

### User Story 2 — Human-in-the-Loop Approval Workflow (Priority: P1)

As a user, I want the AI to write approval request files for sensitive actions (sending emails, posting content, payments) and wait for me to approve or reject them by moving files in Obsidian, so I always have final say over external actions.

**Why this priority**: HITL is a hackathon requirement and the core safety mechanism. Without it, the AI cannot safely perform any external action. This is the trust layer.

**Independent Test**: Trigger a sensitive action (e.g., email reply), verify an approval file appears in `/Pending_Approval`. Move it to `/Approved/` and verify the system detects the approval and triggers the action. Move a different file to `/Rejected/` and verify it is logged and no action is taken.

**Acceptance Scenarios**:

1. **Given** Claude determines an action requires approval (per handbook rules), **When** it creates the action plan, **Then** it writes an `APPROVAL_<action>_<date>.md` file in `/Pending_Approval` with full details (action type, recipient, content preview, reason, expiration).
2. **Given** an approval file exists in `/Pending_Approval`, **When** the user moves it to `/Approved`, **Then** the approval watcher detects the move within 30 seconds, triggers the approved action, logs the result, and moves the file to `/Done`.
3. **Given** an approval file exists in `/Pending_Approval`, **When** the user moves it to `/Rejected`, **Then** the system logs the rejection with reason and moves the file to `/Done` without taking the action.
4. **Given** an approval file has an expiration time, **When** the expiration passes without user action, **Then** the system logs an expiration event and moves the file to `/Done` with status "expired".

---

### User Story 3 — Second Watcher: WhatsApp Web (Priority: P1)

As a user, I want my AI employee to monitor WhatsApp Web for messages matching configured keywords and create action files in the vault, so I have a second communication channel feeding my AI employee alongside Gmail.

**Why this priority**: The hackathon requires 2+ watchers. WhatsApp is the dominant messaging platform for business communication. The `whatsapp-web.js` Node.js bridge replaces Playwright — it uses WhatsApp Web's internal protocol (not CDP/browser automation), shows QR in terminal for one-time setup, and persists session via LocalAuth. The same bridge process both receives messages and sends approved replies autonomously, completing the full perception→action loop without a second MCP server.

**Independent Test**: Run `node whatsapp_watcher.js --setup`, scan QR in terminal, send a message containing a configured keyword (e.g., "urgent", "invoice") via another device, verify a `WHATSAPP_<chat_id>.md` file appears in `/Needs_Action`. For replies: approve an `APPROVAL_WA_*.md` file in Obsidian (move to `/Approved/`), verify the watcher auto-sends it via `sock.sendMessage()` without the user touching the phone.

**Acceptance Scenarios**:

1. **Given** the WhatsApp watcher is running with a valid Baileys session (`useMultiFileAuthState` in `.secrets/whatsapp_session/`), **When** a new message arrives matching a configured keyword, **Then** a `WHATSAPP_<chat_id>.md` file is created in `/Needs_Action` with YAML frontmatter (type: whatsapp_message, chat_id, chat_name, message_id, date, keywords_matched, priority, status: needs_action, source: WhatsApp).
2. **Given** the watcher receives a message with a high-priority keyword (e.g., "urgent", "invoice", "payment", "emergency", "critical"), **When** the action file is created, **Then** the priority is set to "high".
3. **Given** an `APPROVAL_WA_*.md` file is moved to `/Approved`, **When** the watcher detects it via chokidar, **Then** it normalizes the JID to `@s.whatsapp.net`, sends a 2-second composing presence (stealth), sends the reply via `sock.sendMessage()`, and moves the file to `/Archive`.
4. **Given** no session exists or `.secrets/whatsapp_session/` is empty, **When** the watcher starts with `--setup` flag, **Then** it displays a QR code in the terminal via `qrcode-terminal`, waits for scan, saves session via `useMultiFileAuthState`, and exits automatically.
5. **Given** PM2 sends a SIGINT/SIGTERM signal to restart the watcher, **When** the signal is received, **Then** the watcher calls `sock.end()` to close the WebSocket cleanly before exiting, preventing session corruption.

---

### User Story 4 — Email MCP Server for Sending (Priority: P2)

As a user, I want an MCP server that Claude can call to draft and send emails via Gmail, so the AI can take action on email-related tasks after I approve them.

**Why this priority**: The hackathon requires one working MCP server. Email sending is the most practical action that completes the Gmail watcher loop (receive email → triage → draft reply → approve → send).

**Independent Test**: Configure the MCP server, trigger a send-email action from Claude, verify the email is sent (or logged in DRY_RUN mode). Verify the action is logged in the vault.

**Acceptance Scenarios**:

1. **Given** the email MCP server is running and Claude has a draft email approved, **When** Claude calls the `send_email` tool, **Then** the email is sent via Gmail API and the result is logged.
2. **Given** DRY_RUN mode is enabled, **When** Claude calls `send_email`, **Then** the email is logged but not actually sent, and the log entry includes `dry_run: true`.
3. **Given** the MCP server receives a send request without prior HITL approval, **When** it checks the approval status, **Then** it rejects the request and logs a security violation.

---

### User Story 5 — Claude Reasoning Loop with Plan.md (Priority: P2)

As a user, I want Claude to create structured Plan.md files when processing complex tasks (multi-step actions like "reply to client and generate invoice"), so I can see the AI's reasoning and approve the plan before execution.

**Why this priority**: Plans make the AI's reasoning visible and auditable. They bridge the gap between "read a file" and "take complex action" by decomposing work into checkable steps.

**Independent Test**: Place a complex action file in `/Needs_Action` (e.g., an email requesting an invoice). Invoke the planning skill. Verify a `PLAN_<task>.md` appears in `/Plans` with checkboxes, dependencies, and approval requirements marked.

**Acceptance Scenarios**:

1. **Given** a complex item in `/Needs_Action` that requires multiple steps, **When** the planning skill is invoked, **Then** a `PLAN_<task>.md` file is created in `/Plans` with checklist steps, each marked as auto-approve or requires-approval.
2. **Given** a plan with approval-required steps, **When** Claude reaches that step, **Then** it creates an approval file in `/Pending_Approval` and pauses the plan execution.
3. **Given** a plan is fully completed, **When** all steps are checked off, **Then** the plan file is moved to `/Done` and the Dashboard is updated.

---

### User Story 6 — LinkedIn Content Drafting (Priority: P2)

As a user, I want my AI employee to draft LinkedIn posts about my business based on my goals and recent activity, so I can review and manually post them to generate leads — at zero cost.

**Why this priority**: LinkedIn posting is a hackathon requirement. Since LinkedIn's free API does not support posting for personal accounts, the AI drafts posts in the vault for manual copy-paste. This fulfills the requirement while staying at $0 cost.

**Independent Test**: Invoke the LinkedIn drafting skill. Verify a `LINKEDIN_DRAFT_<date>.md` file appears in `/Plans` with a ready-to-post message. Copy-paste it to LinkedIn manually.

**Acceptance Scenarios**:

1. **Given** a `Business_Goals.md` file exists in the vault, **When** the LinkedIn drafting skill is invoked, **Then** a `LINKEDIN_DRAFT_<date>.md` file is created with a professional post tailored to the user's business goals.
2. **Given** the user wants to review the draft, **When** the file is created, **Then** it includes the draft text, suggested hashtags, and a "ready to post" status in frontmatter.
3. **Given** the user approves the draft, **When** they move it to `/Approved`, **Then** it is logged as "posted" and moved to `/Done` (actual posting is manual).

---

### User Story 7 — Scheduled Tasks via Task Scheduler (Priority: P3)

As a user, I want scheduled tasks (morning briefing, periodic Gmail checks, weekly review) that run automatically via Windows Task Scheduler, so the AI works even when I'm not actively prompting it.

**Why this priority**: Scheduling transforms the AI from reactive to proactive. It's the final Silver requirement and builds on all other components.

**Independent Test**: Register a scheduled task that runs the Gmail watcher every 5 minutes. Verify it executes on schedule and creates action files when emails arrive.

**Acceptance Scenarios**:

1. **Given** a scheduled task is registered for Gmail polling, **When** the scheduled time arrives, **Then** the Gmail watcher runs, checks for new emails, and creates action files if any are found.
2. **Given** a morning briefing is scheduled for 8:00 AM, **When** the scheduled time arrives, **Then** a briefing skill generates a summary of pending items, recent activity, and overnight emails.
3. **Given** a scheduled task fails, **When** the error occurs, **Then** it is logged and the next scheduled run is not affected.

---

### Edge Cases

- **Gmail API rate limit hit**: Watcher backs off exponentially, logs the rate limit, resumes on next interval. Never crashes.
- **WhatsApp message has no text (media-only)**: Action file notes "[Media message — no text content]" in the body; matched_keywords will be empty.
- **Approval file moved to wrong folder**: System ignores files not in `/Approved` or `/Rejected`. No action taken, logged as warning.
- **MCP server crashes mid-action**: Email send failure is logged, approval file remains in `/Approved` with status "failed", user is notified via Dashboard.
- **Duplicate emails across polls**: Gmail watcher tracks processed message IDs persistently (file-based) to prevent duplicates across restarts.
- **Credentials expire mid-operation**: Watcher logs auth error, pauses operation, updates Dashboard to show "Auth Error — re-authenticate required".
- **Plan.md references unavailable data**: Plan step is marked as "blocked" with reason, human notified.
- **Multiple watchers writing to Needs_Action simultaneously**: Each watcher uses unique prefixes (EMAIL_, WHATSAPP_, LINKEDIN_NOTIF_, FILE_) so no filename collisions occur.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST copy the Bronze tier `/level-bronze` to `/level-silver` as the starting point, preserving all Bronze functionality.
- **FR-002**: System MUST implement a Gmail Watcher that polls for unread important emails via Gmail API (free tier, OAuth 2.0) and creates `EMAIL_<id>.md` action files in `/Needs_Action`.
- **FR-003**: System MUST implement a WhatsApp Watcher (`whatsapp_watcher.js`) — a Node.js ESM process using `@whiskeysockets/baileys` that: (a) receives keyword-matched messages via `sock.ev.on('messages.upsert')` and creates `WHATSAPP_<id>.md` files in `/Needs_Action`; (b) watches `/Approved` for `APPROVAL_WA_*.md` files via chokidar and sends replies autonomously via `sock.sendMessage()` after a 2-second composing presence; (c) persists session via `useMultiFileAuthState` in `.secrets/whatsapp_session/`; (d) handles SIGINT/SIGTERM gracefully via `sock.end()` to prevent session corruption; (e) deduplicates by Baileys message key ID; (f) normalizes JIDs to `@s.whatsapp.net` format. Replaces the retired Python `whatsapp_watcher.py` and `whatsapp_sender.py` (archived to `bin/`).
- **FR-004**: System MUST implement a Human-in-the-Loop approval workflow using `/Pending_Approval`, `/Approved`, and `/Rejected` vault folders. All external actions require approval.
- **FR-005**: System MUST implement an Approval Watcher that monitors `/Approved` and `/Rejected` folders and triggers or cancels the corresponding action.
- **FR-006**: System MUST implement one MCP server (Email MCP) that exposes `send_email`, `draft_email`, and `search_emails` tools to Claude Code.
- **FR-007**: System MUST implement a planning skill that creates `PLAN_<task>.md` files in `/Plans` with checkboxed steps for multi-step tasks.
- **FR-008**: System MUST implement a LinkedIn drafting skill that generates business posts based on `Business_Goals.md` and writes them to the vault for manual posting.
- **FR-009**: System MUST support scheduled execution via Windows Task Scheduler scripts (`.bat` files) for periodic Gmail checks, morning briefings, and weekly reviews.
- **FR-010**: All credentials (Gmail OAuth tokens, WhatsApp session, LinkedIn session, MCP server secrets) MUST be stored in `.env` files or `.secrets/` directory, never in code or vault. `.env` and `.secrets/` MUST be in `.gitignore`.
- **FR-011**: All new watchers MUST extend the existing `BaseWatcher` abstract class and follow the same logging/dashboard integration pattern as the filesystem watcher.
- **FR-012**: System MUST support DRY_RUN mode for all new capabilities (Gmail sending, WhatsApp replies, MCP actions). When DRY_RUN=true, actions are logged but not executed.
- **FR-013**: All new AI capabilities MUST be implemented as Agent Skills (`.claude/skills/<name>/SKILL.md`).
- **FR-014**: System MUST track processed Gmail message IDs and WhatsApp message IDs persistently (file-based) to prevent duplicate processing across watcher restarts.
- **FR-015**: System MUST implement exponential backoff retry for all API calls (Gmail, MCP) with a maximum of 5 retries and a maximum delay of 5 minutes.
- **FR-016**: Dashboard.md MUST be updated to show status of all watchers (Filesystem, Gmail, WhatsApp, LinkedIn, Approval), pending approvals count, and plan status.

### Key Entities

- **EmailAction**: Represents an email detected by the Gmail Watcher. Attributes: message_id, from, to, subject, received_at, priority, status, snippet, labels.
- **WhatsAppMessage**: Represents a message detected by the WhatsApp Watcher. Attributes: chat_id, chat_name, snippet, matched_keywords, received_at, priority, status.
- **ApprovalRequest**: Represents a pending human approval. Attributes: request_id, action_type (email_send, social_post, payment), details, created_at, expires_at, status (pending, approved, rejected, expired).
- **Plan**: Represents a multi-step reasoning plan. Attributes: plan_id, trigger_file, steps (list with description, status, requires_approval), created_at, completed_at.
- **LinkedInDraft**: Represents a drafted LinkedIn post. Attributes: draft_id, content, hashtags, business_goal_reference, created_at, status (draft, approved, posted).
- **ScheduledTask**: Represents a recurring scheduled job. Attributes: task_name, schedule (cron expression), script_path, last_run, next_run, status.

### Silver Tier Agent Skills

| Skill | Purpose | Trigger |
|-------|---------|---------|
| `fte-gmail-triage` | Classify and prioritize emails in Needs_Action | On-demand or scheduled |
| `fte-gmail-reply` | Draft email replies, write to Pending_Approval | On-demand |
| `fte-whatsapp-reply` | Draft WhatsApp replies, write to Pending_Approval | On-demand |
| `fte-plan` | Create multi-step Plan.md for complex tasks | On-demand |
| `fte-approve` | Process approved items, trigger MCP actions | On-demand or approval-watcher |
| `fte-linkedin-draft` | Generate LinkedIn post drafts from business goals | On-demand or scheduled |
| `fte-briefing` | Generate morning/weekly briefing summary | Scheduled |
| `fte-triage` | (Bronze) Enhanced to handle EMAIL_ and MSG_ types | On-demand |
| `fte-status` | (Bronze) Enhanced to show all watcher statuses | On-demand |
| `fte-process` | (Bronze) Enhanced to handle email and message items | On-demand |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Gmail watcher detects and creates action files for new important emails within 2 minutes of arrival (within polling interval).
- **SC-002**: WhatsApp watcher creates action files in real-time (event-driven via `sock.ev.on('messages.upsert')`) — no polling interval; action file is created within seconds of message receipt.
- **SC-003**: HITL approval workflow completes the full cycle (request → approve → action → done) within 60 seconds of user approval.
- **SC-004**: MCP server successfully sends emails (or logs them in DRY_RUN) when invoked by Claude after HITL approval.
- **SC-005**: All 5 watchers (Filesystem, Gmail, WhatsApp, LinkedIn, Approval) run concurrently without interfering with each other.
- **SC-006**: System operates at $0 cost using only free-tier APIs and open-source tools.
- **SC-007**: No credentials are stored in code, vault markdown, or git history. All secrets in `.env` files.
- **SC-008**: LinkedIn drafting skill generates contextually relevant posts based on Business_Goals.md.
- **SC-009**: Scheduled tasks execute reliably via Windows Task Scheduler at configured intervals.
- **SC-010**: System degrades gracefully when any single watcher or API fails — other components continue operating.
