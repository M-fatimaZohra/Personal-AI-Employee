# Tasks: Silver Tier — Functional Assistant

**Input**: Design documents from `/specs/002-silver-tier/`
**Prerequisites**: plan.md (required), spec.md (required), Bronze tier complete (001-bronze-tier)
**Working Directory**: `/level-silver` (copy of `/level-bronze` + Silver extensions)
**Agent Name**: `silver-fte`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US7)
- **[SEC]**: Security-critical task — requires validation before proceeding
- Include exact file paths in descriptions

---

## Phase 0: Security Foundation (CRITICAL — BLOCKS ALL WORK)

**Purpose**: Establish security infrastructure before any code is written. All secrets management, gitignore patterns, and credential handling MUST be in place first.

**⚠️ SECURITY GATE**: No implementation work can begin until all Phase 0 tasks pass validation.

- [X] T001 [SEC] Create root-level `.gitignore` additions for Silver tier — add patterns for `level-silver/.env`, `level-silver/.env.*`, `level-silver/.secrets/`, `level-silver/AI_Employee_Vault/Logs/*.json`, `level-silver/AI_Employee_Vault/Done/*.md`, `level-silver/AI_Employee_Vault/Needs_Action/*.md`, `level-silver/AI_Employee_Vault/Pending_Approval/*.md`, `level-silver/AI_Employee_Vault/Approved/*.md`, `level-silver/AI_Employee_Vault/Rejected/*.md`, `level-silver/AI_Employee_Vault/Plans/*.md`, `level-silver/mcp-email-server/node_modules/`, `level-silver/mcp-email-server/.env`
- [X] T002 [SEC] Create `level-silver/.env.example` template with all required environment variables (GMAIL_CREDENTIALS_PATH, GMAIL_TOKEN_PATH, GMAIL_QUERY, MCP_SERVER_PORT, MCP_SERVER_SECRET, DRY_RUN, GMAIL_POLL_INTERVAL, APPROVAL_EXPIRY_SECONDS, WA_SESSION_PATH, WA_MAX_UNREAD_CHATS, LINKEDIN_SESSION_DIR, LI_HEADLESS, LI_CHECK_INTERVAL, LI_MAX_NOTIFS, LI_GENERATE_DRAFTS, LI_POST_TOPICS) — commit this file to git as documentation
- [X] T003 [SEC] Create `level-silver/.secrets/` directory with `.gitignore` containing `*` (ignore all files inside) — this directory will hold OAuth credentials and tokens
- [X] T004 [SEC] Validate gitignore patterns — create dummy files in all sensitive locations (`.env`, `.secrets/test.json`, `Logs/test.json`, `Done/test.md`) and verify `git status` shows none of them as untracked

**Security Checkpoint**: Run `git status` — NO sensitive patterns should appear. All vault data, secrets, and .env files must be gitignored.

---

## Phase 1: Environment Setup & Migration

**Purpose**: Copy Bronze tier to Silver, update project metadata, install dependencies.

- [X] T005 Copy entire `/level-bronze` directory to `/level-silver` — preserve all Bronze functionality as the foundation
- [X] T006 Update `level-silver/pyproject.toml` — change `name = "silver-fte"`, update description to "Silver Tier Functional Assistant — Gmail, WhatsApp, LinkedIn, MCP, HITL, scheduling"
- [X] T007 [P] Install Python dependencies via `uv add`: `google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2`, `python-dotenv`, `watchdog`, `playwright`
- [X] T008 [P] Create `level-silver/mcp-email-server/` directory and initialize Node.js project with `npm init -y`
- [X] T009 [P] Install Node.js MCP dependencies: `npm install @modelcontextprotocol/sdk googleapis dotenv`
- [X] T010 Run `uv sync` and verify all Python dependencies resolve correctly
- [X] T011 Create `level-silver/.env` from `.env.example` template (user fills in real values later)

**Checkpoint**: `uv sync` succeeds, `npm install` succeeds, `.env` file exists (with placeholders), all gitignore patterns active.

---

## Phase 2: Foundational (Security & Infrastructure)

**Purpose**: Core security and infrastructure modules that ALL user stories depend on. HITL approval system, ID tracking, backoff retry, enhanced logging.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T012 [SEC] Implement `level-silver/id_tracker.py` — persistent JSON-based storage for processed message IDs (Gmail, WhatsApp, LinkedIn). Functions: `is_processed(category, id)`, `mark_processed(category, id)` — category-keyed JSON file at `level-silver/.state/processed_ids.json` (gitignored via pattern `level-silver/.state/`)
- [X] T013 [SEC] Implement `level-silver/backoff.py` — exponential backoff retry decorator for API calls. Function: `@retry_with_backoff(max_retries=5, base_delay=1, max_delay=300)`. Logs all retry attempts. Used by Gmail watcher and MCP dispatch in approval_watcher.
- [X] T014 [SEC] Create vault folder structure extensions — create `level-silver/AI_Employee_Vault/Plans/`, `level-silver/AI_Employee_Vault/Pending_Approval/`, `level-silver/AI_Employee_Vault/Approved/`, `level-silver/AI_Employee_Vault/Rejected/` directories
- [X] T015 [SEC] Create `level-silver/AI_Employee_Vault/Business_Goals.md` template with sections: Revenue Targets, Active Projects, Key Metrics, LinkedIn Content Themes
- [X] T016 Update `level-silver/dashboard_updater.py` — extended to show all 5 watchers (Filesystem, Gmail, WhatsApp, LinkedIn, Approval) with Offline default, Pending Approvals count, Plans count, priority-sorted pending items, result icons in activity log
- [X] T017 Update `level-silver/AI_Employee_Vault/Company_Handbook.md` — add email response rules (tone, timing, auto-approve thresholds), social media posting rules, approval requirements

**Checkpoint**: All new vault folders exist, ID tracker works, backoff decorator tested, dashboard shows 3 watcher slots, handbook has email/social rules.

---

## Phase 3: User Story 1 — Gmail Watcher (Priority: P1) 🎯 CORE

**Goal**: Gmail Watcher polls Gmail API for unread important emails and creates `EMAIL_<id>.md` action files in `/Needs_Action` within 2 minutes.

**Independent Test**: Configure Gmail OAuth, start watcher, send yourself an important email, verify `EMAIL_<id>.md` appears in `/Needs_Action` with correct frontmatter and body.

**Security**: OAuth tokens in `.secrets/`, never in code. All API errors logged, never expose credentials in logs.

### Implementation for User Story 1

- [X] T018 [SEC] [US1] Implement `level-silver/gmail_watcher.py` — extends `BaseWatcher`. `__init__` loads OAuth credentials from `.secrets/client_secret.json`. Uses `google-auth` for OAuth 2.0 flow. On first run, opens browser for user login, saves token to `.secrets/gmail_token.json`.
- [X] T019 [SEC] [US1] Implement `check_for_updates()` in `GmailWatcher` — calls Gmail API `users().messages().list()` with selective query (is:unread is:important, excludes social/updates/promotions/forums). Returns full message dicts. Deduplicates via persistent .state/gmail_processed_ids.json.
- [X] T020 [US1] Implement `create_action_file(item)` in `GmailWatcher` — applies security blacklist (OTP/verification codes) and digest blacklist (Instagram/Facebook/Quora/Medium). Extracts subject, sender, body. Writes `EMAIL_<message_id>.md` to `/Needs_Action` with YAML frontmatter.
- [X] T021 [US1] Implement `start()` and `stop()` in `GmailWatcher` — `start()` authenticates, then calls `super().start()` (inherited polling loop). `stop()` logs shutdown and updates dashboard.
- [X] T022 [SEC] [US1] Add OAuth token refresh logic — on expired token, auto-refresh via `google-auth`. If refresh fails, logs error and raises for graceful shutdown.
- [X] T023 [US1] Update `level-silver/run_watchers.py` — GmailWatcher enabled if `.secrets/client_secret.json` exists, skipped gracefully if not. Both watchers run in separate threads via base_watcher run() loop.

**Security Checkpoint**:
- [ ] Verify `.secrets/gmail_credentials.json` and `.secrets/gmail_token.json` are gitignored
- [ ] Verify no credentials appear in logs (check `Logs/*.json`)
- [ ] Verify OAuth refresh works (manually expire token and test)

**Checkpoint**: Gmail watcher polls every 2 minutes, creates EMAIL_*.md files, deduplicates, logs all actions, updates dashboard.

---

## Phase 4: User Story 2 — HITL Approval Workflow (Priority: P1) 🎯 SECURITY GATE

**Goal**: All external actions write to `/Pending_Approval` first. User reviews in Obsidian and moves to `/Approved` or `/Rejected`. Approval Watcher detects the move and triggers or cancels the action.

**Independent Test**: Manually create an approval file in `/Pending_Approval`, move it to `/Approved`, verify Approval Watcher detects it within 30 seconds and logs the approval.

**Security**: This is the MANDATORY human gate. No bypass path exists. All external actions MUST go through this workflow.

### Implementation for User Story 2

- [X] T024 [SEC] [US2] Implement `level-silver/approval_watcher.py` — extends `BaseWatcher`. Monitors `/Pending_Approval`, `/Approved`, `/Rejected` folders using watchdog. On file move to `/Approved`: reads approval file, validates action_type, triggers corresponding action (email send, LinkedIn post, etc.), moves file to `/Done` with status=executed. On file move to `/Rejected`: logs rejection, moves to `/Done` with status=rejected.
- [X] T025 [SEC] [US2] Implement approval file expiration logic in `ApprovalWatcher` — on each poll, check all files in `/Pending_Approval` for `expires_at` timestamp. If expired, move to `/Done` with status=expired, log expiration event.
- [X] T026 [SEC] [US2] Implement approval validation — before executing any approved action, verify: (1) file has valid YAML frontmatter, (2) action_type is recognized, (3) all required fields present (to, subject, content for emails), (4) no malformed data. If validation fails, move to `/Rejected` with error details.
- [X] T027 [US2] Update `run_watchers.py` — add `ApprovalWatcher` to the orchestrator. Run in separate thread alongside Filesystem and Gmail watchers.

**Security Checkpoint**:
- [ ] Verify no action executes without a file in `/Approved`
- [ ] Verify expired approvals are caught and logged
- [ ] Verify malformed approval files are rejected safely

**Checkpoint**: Approval workflow operational. Files moved to `/Approved` trigger actions. Files moved to `/Rejected` are logged. Expired files are caught.

---

## Phase 4A: Orchestrator — Autonomy Engine (Priority: P0) 🤖 CRITICAL

**Goal**: A single `orchestrator.py` process watches `/Needs_Action` with watchdog. When a new action file appears, it dispatches the correct Claude skill automatically via `subprocess.Popen`. The user never types a skill command.

**Routing table:**
- `EMAIL_*` → `/fte-gmail-triage`
- `WHATSAPP_*` → `/fte-whatsapp-reply`
- `LINKEDIN_NOTIF_*` → `/fte-triage`
- `FILE_*` → `/fte-triage`

**Independent Test**: Drop a file named `EMAIL_test.md` into `/Needs_Action`. Verify orchestrator spawns `claude --print "/fte-gmail-triage EMAIL_test.md"` within 2 seconds.

- [X] T067 Implement `level-silver/orchestrator.py` — watchdog `FileSystemEventHandler` on `AI_Employee_Vault/Needs_Action/`; `SKILL_ROUTING` dict maps filename prefixes to skill names; `on_created` handler calls `subprocess.Popen(["claude", "--print", f"/{skill} {filepath.name}"])` with cwd set to vault parent; startup validates `claude --version` on PATH; in-memory `_in_flight: set[str]` prevents duplicate dispatch for the same filename; logs each dispatch via `logger.log_action`.
- [X] T068 Update `level-silver/run_watchers.py` — document that orchestrator runs as a **separate process** alongside watchers (not imported); add startup note pointing to `ecosystem.config.js` for running both together via PM2.

**Checkpoint**: Orchestrator running, new files in `/Needs_Action` trigger correct skill dispatch, duplicate files not dispatched twice, all dispatches logged.

---

## Phase 4B: Ralph Wiggum Stop Hook — Task Persistence

**Goal**: A Claude Code stop hook intercepts Claude's exit, checks whether the task triggered in this session is complete (file in `/Done`), and re-injects the skill prompt if not. Ensures multi-step tasks run to completion.

**Max re-injection guard**: After 5 re-injections, log critical and allow exit to prevent infinite loops.

- [X] T069 Create `level-silver/.claude/hooks/stop.py` — reads `CLAUDE_HOOK_STOP_REASON` env var; parses current working context to identify the triggering action filename; checks if that file exists in `AI_Employee_Vault/Done/`; if not done and re-injection count < 5, writes the original skill prompt back to stdout (Claude Code hook protocol) to continue; if done or limit reached, exits with code 0 to allow Claude to exit; logs each re-injection and final exit via `logger.log_action`.
- [X] T070 Register the stop hook — add hook registration to `level-silver/.claude/settings.json` (or document the `claude config` command to register `hooks.stop = "uv run python .claude/hooks/stop.py"`); document in QUICKSTART.md.

**Checkpoint**: Stop hook registered; Claude re-invokes skill when action file is not yet in `/Done`; Claude exits cleanly once file reaches `/Done`; max re-injection limit prevents infinite loops.

---

## Phase 4C: PM2 Process Manager — Process Immortality

**Goal**: Both `run_watchers.py` and `orchestrator.py` run under PM2. They restart automatically on crash and survive reboots. Task Scheduler `.bat` scripts handle one-shot scheduled tasks (morning briefing, weekly review).

- [X] T071 Create `level-silver/ecosystem.config.cjs` — PM2 config with two apps: `silver-orchestrator` (interpreter: uv-managed python, script: `orchestrator.py`, cwd: `level-silver/`, `PYTHONUNBUFFERED=1`) and `whatsapp-watcher` (interpreter: `node`, script: `whatsapp_watcher.js`, cwd: `level-silver/`, `NODE_ENV=production`); `restart_delay: 3000/10000`, `max_restarts: 10`; `.cjs` extension required because `package.json` uses `"type": "module"`.
- [X] T083 Update `level-silver/ecosystem.config.cjs` (renamed from `.js` — `"type":"module"` makes `.js` files ESM, breaking CJS `require()`/`module.exports`) — two PM2 apps: `silver-orchestrator` (interpreter: uv python, script: `orchestrator.py`, `restart_delay: 3000`) and `whatsapp-watcher` (interpreter: `node`, script: `whatsapp_watcher.js`, `restart_delay: 10000` — prevents spam-login on internet drop, `max_restarts: 10`, `NODE_ENV: production`); removed `kill_timeout` (Baileys `sock.end()` completes in <1s, no browser teardown needed); logs to `AI_Employee_Vault/Logs/`
- [X] T072 Document PM2 setup — create `level-silver/PM2.md` with: `npm install -g pm2`, `pm2 start ecosystem.config.js`, `pm2 save`, `pm2 startup` (generates OS-level init script), `pm2 logs`, `pm2 monit`, `pm2 resurrect` (recovery after PM2 list loss).

**Checkpoint**: `pm2 start ecosystem.config.js` starts both processes; both restart on crash; `pm2 startup` + `pm2 save` ensures they start on reboot.

---

## Phase 5: User Story 3 — WhatsApp + LinkedIn Watchers (Priority: P1) 🎯 CORE

**Goal**: WhatsApp watcher (Node.js, whatsapp-web.js) receives messages event-driven, writes `WHATSAPP_<chat_id>.md`, and auto-sends approved replies via `client.sendMessage()`. LinkedIn watcher reads your own notifications and writes `LINKEDIN_NOTIF_<id>.md` for mentions/comments via Playwright persistent session.

**Independent Test**: Send a WhatsApp message containing an urgent keyword (e.g. "invoice"), verify `WHATSAPP_*.md` appears in `/Needs_Action`. Approve a reply in Obsidian → verify reply sent automatically. Check LinkedIn notifications page → verify `LINKEDIN_NOTIF_*.md` appears.

**Security**: Sessions stored in `.secrets/` (gitignored). Rate-limited (LinkedIn: 30-min minimum interval). DRY_RUN supported. Both watchers skip gracefully if session directory is missing.

### Implementation

- [X] T028 [US3] ~~SUPERSEDED~~ — `whatsapp_watcher.py` (Playwright) replaced by T078–T082 (`whatsapp_watcher.js`, whatsapp-web.js)
- [X] T032 [US3] ~~DELETED~~ — `whatsapp_sender.py` removed; sending now handled internally by `whatsapp_watcher.js` via `client.sendMessage()`

### WhatsApp Watcher — New Implementation (whatsapp-web.js, Node.js)

- [X] T078 [US3] Create `level-silver/package.json` — Node.js ESM project for `whatsapp_watcher.js`; `"type": "module"`; deps: `@whiskeysockets/baileys`, `pino`, `qrcode-terminal`, `chokidar`, `dotenv`, `fs-extra`; scripts: `"start": "node whatsapp_watcher.js"`, `"setup": "node whatsapp_watcher.js --setup"`; removed: `whatsapp-web.js`, `overrides` (puppeteer pin)
- [X] T079 [US3] Build `level-silver/whatsapp_watcher.js` — Part 1 (Connection Init): ESM imports (`makeWASocket`, `useMultiFileAuthState`, `DisconnectReason`, `fetchLatestBaileysVersion` from `@whiskeysockets/baileys`); `useMultiFileAuthState('.secrets/whatsapp_session')` for session persistence; `makeWASocket({ version, auth: state, logger: pino({ level: 'silent' }) })`; `sock.ev.on('creds.update', saveCreds)`; `sock.ev.on('connection.update')` handles: QR via `qrcode.generate(qr, { small: true })`, reconnect on close, `--setup` auto-exit on `connection === 'open'`
- [X] T080 [US3] Build `level-silver/whatsapp_watcher.js` — Part 2 (Receive): `sock.ev.on('messages.upsert', { messages, type })` handler — type must be `'notify'`; filters groups (`@g.us`) and broadcasts; extracts text from `conversation`, `extendedTextMessage.text`, `imageMessage.caption`; filters by `WA_URGENT_KEYWORDS` env var; deduplicates by Baileys `msg.key.id` via `.state/wa_processed_ids.json`; writes `WHATSAPP_<jid_safe>_<datestamp>.md` to `/Needs_Action/` with YAML frontmatter: `type, chat_id (full JID), chat_name (pushName), message_id, date, status, priority, keywords_matched, source: WhatsApp`
- [X] T081 [US3] Build `level-silver/whatsapp_watcher.js` — Part 3 (Send): chokidar watches `AI_Employee_Vault/Approved/` for `APPROVAL_WA_*.md` (awaitWriteFinish stabilityThreshold: 500ms); on detect: parses YAML frontmatter for `chat_id`, normalizes via `normalizeJid()` (`@c.us` → `@s.whatsapp.net`); extracts reply from `## Proposed Reply` section; sends `sock.sendPresenceUpdate('composing', jid)` → 2s delay → `sock.sendPresenceUpdate('paused', jid)` → `sock.sendMessage(jid, { text: replyText })`; moves file to `/Archive/` with `status: sent`; logs all steps as JSON Lines
- [X] T082 [US3] Build `level-silver/whatsapp_watcher.js` — Part 4 (Setup + Shutdown): `--setup` CLI flag (`IS_SETUP = process.argv.includes('--setup')`) — when connection opens, calls `sock.end()` and `process.exit(0)`, session already saved by `saveCreds()`; graceful shutdown handlers: `process.on('SIGINT'/'SIGTERM', async () => { await sock.end(); process.exit(0) })` — prevents session file corruption on PM2 restart; `wa_setup.bat` Windows batch helper created for first-time setup; old `whatsapp_sender.py` + `whatsapp_watcher.py` (Python/Playwright) archived to `bin/`

### LinkedIn Watcher (unchanged)

- [X] T029 [US3] Implement `level-silver/linkedin_watcher.py` — extends `BaseWatcher`. Playwright `launch_persistent_context` on `linkedin.com/notifications/`. Enforces 30-minute minimum check interval (`LI_CHECK_INTERVAL = max(_RAW_INTERVAL, 1800)`). Reads only your own notifications. Creates `LINKEDIN_NOTIF_<hash_id>.md` for mention/comment/connection types (high-value only). Low-value types (like, job, other) silently skipped + marked processed.
- [X] T030 [US3] Implement `generate_post_draft()` in `LinkedInWatcher` — reads `Business_Goals.md` + recent `/Done` activity; writes `LINKEDIN_DRAFT_<date>.md` to `/Plans` for HITL review. Never auto-posts. Skips if today's draft already exists.
- [X] T031 [US3] Implement `linkedin_poster.py` with `JitterScheduler` — randomises post time within `POST_WINDOW_START`–`POST_WINDOW_END` (default 09:00–18:00), enforces 23h minimum gap, stores schedule in `.state/linkedin_scheduled.json`. Truncates posts exceeding 3,000 chars and logs the truncation. Uses human-simulation (slow_mo=500ms, character-by-character typing, random pauses).

**Checkpoint**: WhatsApp creates `WHATSAPP_*.md` for matched keywords. LinkedIn creates `LINKEDIN_NOTIF_*.md` for mentions/comments and `LINKEDIN_DRAFT_*.md` in `/Plans`. Orchestrator routes both. JitterScheduler fires approved posts at randomised times.

---

## Phase 6: User Story 4 — Email MCP Server (Priority: P2)

**Goal**: Node.js MCP server exposes `send_email`, `draft_email`, `search_emails` tools to Claude Code. All sends require prior HITL approval.

**Independent Test**: Start MCP server, configure Claude Code to use it, invoke `send_email` tool from Claude, verify email is sent (or logged in DRY_RUN).

**Security**: MCP server validates `MCP_SERVER_SECRET` on every request. Rejects unauthenticated calls.

### Implementation for User Story 4

- [X] T033 [SEC] [US4] Implement `level-silver/mcp-email-server/index.js` — MCP server entry point. Loads `.env` (MCP_SERVER_SECRET, GMAIL_CREDENTIALS_PATH, GMAIL_TOKEN_PATH). Validates incoming requests against secret. Rejects with 401 if invalid.
- [X] T034 [SEC] [US4] Implement `send_email` tool in `mcp-email-server/tools/send_email.js` — accepts (to, subject, body). Before sending: (1) check if corresponding approval file exists in `/Approved`, (2) if not, reject with error "No approval found", (3) if approved, send via Gmail API, (4) log result, (5) move approval file to `/Done`.
- [X] T035 [US4] Implement `draft_email` tool in `mcp-email-server/tools/draft_email.js` — accepts (to, subject, body). Creates a draft in Gmail via API. Returns draft ID. Logs action.
- [X] T036 [US4] Implement `search_emails` tool in `mcp-email-server/tools/search_emails.js` — accepts (query). Searches Gmail via API. Returns list of matching emails (subject, from, date, snippet). Logs query.
- [X] T037 [SEC] [US4] Add DRY_RUN support to MCP server — if `DRY_RUN=true` in `.env`, log all actions but don't actually send emails or create drafts. Return success with `dry_run: true` flag.
- [X] T038 [US4] Create Claude Code MCP configuration — document how to add MCP server to `~/.config/claude-code/mcp.json` (or Windows equivalent) with command, args, and env variables.

**Security Checkpoint**:
- [ ] Verify MCP server rejects requests without valid secret
- [ ] Verify `send_email` rejects calls without prior approval
- [ ] Verify DRY_RUN mode logs but doesn't send

**Checkpoint**: MCP server running, Claude can call tools, send_email requires approval, DRY_RUN works.

---

## Phase 7: User Story 5 — Claude Reasoning Loop (Priority: P2)

**Goal**: Claude creates `PLAN_<task>.md` files in `/Plans` with checkboxed steps for multi-step tasks. Plans mark approval-required steps explicitly.

**Independent Test**: Place a complex email in `/Needs_Action`, invoke `/fte-plan` skill, verify a `PLAN_<task>.md` appears with steps and approval markers.

### Implementation for User Story 5

- [X] T039 [P] [US5] Create `/fte-plan` skill in `level-silver/.claude/skills/fte-plan/SKILL.md` — instructions for Claude to: (1) read item from `/Needs_Action`, (2) decompose into steps, (3) mark steps that require approval (email sends, posts, payments), (4) write `PLAN_<task_id>.md` to `/Plans` with YAML frontmatter (type: plan, plan_id, trigger_file, status: in_progress, created_at) and checkboxed steps in body.
- [X] T040 [US5] Update `/fte-process` skill — when processing a complex item, check if a plan exists in `/Plans`. If yes, follow the plan steps. If a step requires approval, create approval file and pause. If no plan, create one first via `/fte-plan`.
- [ ] T041 [US5] Implement plan completion logic — when all steps in a plan are checked off, move plan file to `/Done` with status=completed, update dashboard.

**Checkpoint**: Plans are created for complex tasks, approval-required steps are marked, plans are followed step-by-step.

---

## Phase 8: User Story 6 — LinkedIn Content Drafting (Priority: P2)

**Goal**: Claude drafts LinkedIn posts based on `Business_Goals.md` and writes them to `/Plans` for manual posting.

**Independent Test**: Invoke `/fte-linkedin-draft` skill, verify a `LINKEDIN_DRAFT_<date>.md` appears with professional post content.

### Implementation for User Story 6

- [X] T042 [P] [US6] Create `/fte-linkedin-draft` skill in `level-silver/.claude/skills/fte-linkedin-draft/SKILL.md` — instructions for Claude to: (1) read `Business_Goals.md`, (2) read recent activity from `/Done` and `/Logs`, (3) draft a professional LinkedIn post (150-300 words), (4) suggest hashtags, (5) write `LINKEDIN_DRAFT_<date>.md` to `/Plans` with YAML frontmatter (type: linkedin_draft, status: draft, created_at, hashtags).
- [X] T043 [US6] Update approval workflow — when user moves LinkedIn draft to `/Approved`, update status to "ready_to_post" and move to `/Done`. Dashboard shows "1 LinkedIn post ready — post manually".

**Checkpoint**: LinkedIn drafts are generated, user reviews and approves, dashboard shows ready-to-post count.

---

## Phase 9: User Story 7 — Scheduled Tasks (Priority: P3)

**Goal**: Windows Task Scheduler runs periodic tasks (Gmail polling, morning briefing, weekly review).

**Independent Test**: Register a scheduled task, verify it runs at the scheduled time and creates expected output.

### Implementation for User Story 7

- [X] T044 [P] [US7] Create `level-silver/schedules/gmail_poll.bat` — batch script that runs `uv run python gmail_watcher.py --once` (single poll, then exit). Logs output to `schedules/gmail_poll.log`.
- [X] T045 [P] [US7] Create `level-silver/schedules/morning_briefing.bat` — batch script that triggers `/fte-briefing` skill via Claude Code CLI (if available) or writes a trigger file that the orchestrator detects.
- [X] T046 [P] [US7] Create `level-silver/schedules/weekly_review.bat` — batch script that triggers `/fte-linkedin-draft` skill.
- [X] T047 [US7] Create `/fte-briefing` skill in `level-silver/.claude/skills/fte-briefing/SKILL.md` — instructions for Claude to: (1) read overnight emails from `/Needs_Action`, (2) count pending approvals, (3) read active plans, (4) write `BRIEFING_<date>.md` to `/Plans` with summary and suggested actions.
- [X] T048 [US7] Document Task Scheduler registration — create `level-silver/schedules/README.md` with `schtasks` commands to register all scheduled tasks (Gmail every 2 min, briefing daily 8 AM, review weekly Sunday 9 AM).

**Checkpoint**: Scheduled tasks registered, Gmail polls automatically, briefings generated on schedule.

---

## Phase 10: Enhanced Agent Skills (Silver Extensions)

**Purpose**: Update Bronze skills to handle EMAIL_ and MSG_ types, create new Silver-specific skills.

- [X] T049 [P] Update `/fte-triage` skill — extend to classify EMAIL_ and MSG_ types. Apply email-specific rules from handbook (urgent keywords, client domains, time-sensitive). Update dashboard with email/message counts.
- [X] T050 [P] Update `/fte-status` skill — show status for all 5 watchers (Filesystem, Gmail, WhatsApp, LinkedIn, Approval), pending approvals count, plans count, scheduled LinkedIn post time, last activity per watcher.
- [X] T051 [P] Create `/fte-gmail-triage` skill in `level-silver/.claude/skills/fte-gmail-triage/SKILL.md` — specialized email triage. Classifies emails by type (client, vendor, personal, spam), applies handbook rules, updates priorities.
- [X] T052 [P] Create `/fte-gmail-reply` skill in `level-silver/.claude/skills/fte-gmail-reply/SKILL.md` — drafts email replies. Reads email from `/Needs_Action`, reads handbook for tone/rules, drafts professional reply, writes `APPROVAL_email_reply_<id>.md` to `/Pending_Approval`.
- [X] T053 [P] Implement `level-silver/.claude/skills/fte-whatsapp-reply/SKILL.md` — reads `WHATSAPP_*.md` + `Company_Handbook.md` + `FAQ_Context.md`; classifies ROUTINE (greeting, FAQ, ack, yes/no) vs SENSITIVE (payment, legal, invoice, contract); ROUTINE → writes `APPROVAL_whatsapp_<id>.md` **directly to `/Approved/`** (chokidar picks it up → auto-sends, zero HITL); SENSITIVE → writes to `/Pending_Approval/` for user review in Obsidian; logs `sensitivity: routine|sensitive` + `sensitivity_reason` in frontmatter
- [X] T054 [P] Create `/fte-approve` skill in `level-silver/.claude/skills/fte-approve/SKILL.md` — processes approved items. Reads files from `/Approved`, triggers MCP actions, logs results, moves to `/Done`.

**Checkpoint**: All 10 Silver skills operational (3 Bronze enhanced + 7 new Silver).

---

## Phase 11: Testing & Validation

**Purpose**: Comprehensive testing of all Silver components.

- [X] T055 [P] Create `level-silver/tests/test_gmail_watcher.py` — mock Gmail API, test message fetching, deduplication, action file creation, OAuth refresh.
- [X] T056 [P] Create `level-silver/tests/test_whatsapp_watcher.py` + `test_linkedin_watcher.py` — mock Playwright sessions; test create_action_file (frontmatter, dedup, priority, DRY_RUN), keyword gating (WhatsApp), notification type filtering (LinkedIn), JitterScheduler rate-limit constant, generate_post_draft. 45 tests total, all passing.
- [X] T057 [P] Create `level-silver/tests/test_approval_watcher.py` — test approval detection, expiration logic, validation, action triggering.
- [X] T058 [P] Create `level-silver/tests/test_id_tracker.py` — test persistent ID storage, deduplication across restarts.
- [X] T059 [P] Create `level-silver/tests/test_mcp_server.js` — test MCP server authentication, send_email approval check, DRY_RUN mode. (10/10 JS tests pass; conftest.py added to fix DRY_RUN=true in .env breaking file-write tests)
- [X] T060 Run all tests: `uv run pytest tests/ -v` (Python) and `npm test` (Node.js MCP server). All tests must pass. (155 Python + 10 JS = 165 total, all passing)

**Checkpoint**: All tests pass. No regressions in Bronze functionality.

---

## Phase 12: Security Audit & Documentation

**Purpose**: Final security validation and documentation.

- [X] T061 [SEC] Security audit — verify all secrets gitignored, no credentials in logs, no hardcoded tokens, all API calls use retry with backoff, all external actions require HITL approval.
- [X] T062 [SEC] Create `level-silver/SECURITY.md` — document: (1) credential setup, (2) what's gitignored and why, (3) HITL workflow, (4) how to rotate tokens, (5) DRY_RUN usage, (6) incident response (what to do if credentials leak).
- [X] T063 Update `level-silver/README.md` — full Silver tier usage guide: setup, credentials, watchers, skills, scheduling, HITL workflow, troubleshooting.
- [X] T064 Create `level-silver/QUICKSTART.md` — step-by-step: (1) copy Bronze, (2) install Python deps (`uv sync`), (3) install Node.js deps (`npm install`), (4) setup .env, (5) Gmail OAuth (`gmail_watcher.py --auth-only`), (6) WhatsApp QR scan (`node whatsapp_watcher.js --setup`), (7) LinkedIn login (`linkedin_watcher.py --setup`), (8) MCP server (`npm install` in mcp-email-server/), (9) first run via PM2 (`pm2 start ecosystem.config.js`), (10) test HITL workflow.
- [X] T065 Update root `README.md` — add Silver tier section with features, requirements, and link to level-silver/README.md.

**Checkpoint**: All documentation complete, security audit passed.

---

## Phase 14: WhatsApp & LinkedIn Watchers (Playwright-based, personal use)

**Purpose**: Two additional perception channels — WhatsApp (keyword-gated, read-only) and LinkedIn (rate-limited, draft-only). Both use Playwright with persistent sessions to avoid repeated logins.

**⚠️ ToS Note**: WhatsApp ToS (Section 7) and LinkedIn ToS (Section 8.2) restrict automated access. These are implemented for personal/educational hackathon use ONLY with safeguards: read-only, rate-limited, keyword-gated, session-persistent.

- [X] T073 ~~SUPERSEDED~~ — `whatsapp_watcher.py` (Playwright) replaced by `whatsapp_watcher.js` (whatsapp-web.js Node.js). See T078–T082.
- [X] T074 Implement `level-silver/linkedin_watcher.py` — extends `BaseWatcher`. Playwright `launch_persistent_context` on `linkedin.com/notifications/`. 30-minute minimum interval enforced. Reads ONLY your own notifications. Creates `LINKEDIN_NOTIF_<id>.md` for mentions/comments. `generate_post_draft()` writes `LINKEDIN_DRAFT_<date>.md` to `/Plans` for HITL review (never auto-posts).
- [X] T075 Update `level-silver/orchestrator.py` SKILL_ROUTING — add `WHATSAPP_` and `LINKEDIN_NOTIF_` entries. Conditional startup for both watchers.
- [X] T076 Update `level-silver/run_watchers.py` — add LinkedInWatcher with conditional startup (WhatsApp is now Node.js via PM2, not started here).
- [X] T077 Update `level-silver/.env.example` — add WhatsApp and LinkedIn env vars.

**Checkpoint**: Both watchers start if sessions exist, skip gracefully if not. WhatsApp creates WHATSAPP_*.md for urgent keywords. LinkedIn creates LINKEDIN_NOTIF_*.md and LINKEDIN_DRAFT_*.md in /Plans. Orchestrator routes both.

---

## Phase 13: End-to-End Validation

**Purpose**: Full system integration test.

- [X] T066 End-to-end test: (1) Start all 5 watchers via PM2, (2) send yourself an important Gmail → verify `EMAIL_*.md` in `/Needs_Action`, (3) send WhatsApp message with urgent keyword → verify `WHATSAPP_*.md`, (4) check LinkedIn notifications page → verify `LINKEDIN_NOTIF_*.md` for a mention, (5) drop a file in `Drop_Box` → verify `FILE_*.md`, (6) invoke `/fte-gmail-reply` → verify `APPROVAL_*.md` in `/Pending_Approval`, (7) move to `/Approved` → verify `fte-approve` skill fires and email sends via MCP, (8) verify file reaches `/Done` with status=executed, (9) check all Logs/*.json entries, (10) verify Dashboard.md updated with correct watcher statuses. ✅ VERIFIED 2026-03-02 — full pipeline confirmed live (WhatsApp send, Gmail send, LinkedIn post, PM2 automation).

**Final Checkpoint**: Full Silver tier pipeline works end-to-end. All 7 user stories validated.

---

## Dependencies & Execution Order

### Revised Build Priority (Autonomy-First)

| # | Phase | What | Why |
|---|-------|------|-----|
| 1 | Phase 2 | `id_tracker.py` + `backoff.py` | Foundation — unblocks watcher stability |
| 2 | Phase 4 | `approval_watcher.py` | Closes the HITL loop |
| 3 | Phase 4A | `orchestrator.py` | THE autonomy engine — auto-invokes skills |
| 4 | Phase 10 | All 10 Agent Skills | The reasoning layer the orchestrator calls |
| 5 | Phase 4B | Ralph Wiggum stop hook | Multi-step task persistence |
| 6 | Phase 4C + Phase 5 | PM2 setup + WhatsApp + LinkedIn watchers | Additional channels + process immortality |
| 7 | Phase 6 | MCP email server | The "hands" for sending |

### Phase Dependencies

- **Phase 0 (Security Foundation)**: No dependencies — MUST complete first, BLOCKS all other work
- **Phase 1 (Environment Setup)**: Depends on Phase 0 — BLOCKS all implementation
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user stories
- **Phase 3 (Gmail Watcher)**: Depends on Phase 2
- **Phase 4 (HITL Approval)**: Depends on Phase 2
- **Phase 4A (Orchestrator)**: Depends on Phase 4 (needs approval_watcher operational before orchestrator dispatches skills that write to /Pending_Approval)
- **Phase 4B (Stop Hook)**: Depends on Phase 4A (hook only meaningful once orchestrator invokes skills)
- **Phase 4C (PM2)**: Depends on Phase 4A (both processes must exist before configuring PM2)
- **Phase 5 (WhatsApp + LinkedIn)**: Depends on Phase 4A (orchestrator must know WHATSAPP_ and LINKEDIN_NOTIF_ routing)
- **Phase 6 (MCP)**: Depends on Phase 4 (approval_watcher must be operational)
- **Phase 7-9 (Plans, LinkedIn, Scheduling)**: Depend on Phase 4A + skills
- **Phase 10 (Skills)**: Depends on Phase 4A — skills must exist before orchestrator can call them
- **Phase 11 (Testing)**: Depends on Phase 10 completion
- **Phase 12 (Security Audit)**: Depends on Phase 11 completion
- **Phase 13 (E2E Validation)**: Depends on Phase 12 completion

### Critical Path (Autonomous MVP)

1. Phase 0 (Security) → Phase 1 (Setup) → Phase 2 (Foundation)
2. Phase 3 (Gmail) + Phase 4 (HITL) → Phase 4A (Orchestrator) → Phase 10 (Skills)
3. Phase 4B (Stop Hook) + Phase 4C (PM2) + Phase 5 (WhatsApp + LinkedIn)
4. Phase 6 (MCP) → Phase 11 (Tests) → Phase 12 (Security Audit) → Phase 13 (E2E)

This delivers: Gmail + HITL + Orchestrator + Skills = **fully autonomous email assistant**.

### Parallel Opportunities

After Phase 2 completes:
- Phase 3 (Gmail), Phase 4 (HITL) can run in parallel
- After Phase 4A (Orchestrator): Phase 4B (Stop Hook), Phase 4C (PM2), Phase 5 (WhatsApp + LinkedIn) can run in parallel
- After Phase 4+4A: Phase 6 (MCP), Phase 7 (Plans), Phase 8 (LinkedIn) can run in parallel
- All skills in Phase 10 can be created in parallel
- All tests in Phase 11 can run in parallel

---

## Task Summary

| Phase | Story | Tasks | Parallel | Security-Critical |
|-------|-------|-------|----------|-------------------|
| Security Foundation | — | T001–T004 | T002, T003 | ALL |
| Environment Setup | — | T005–T011 | T007, T008, T009 | — |
| Foundational | — | T012–T017 | T012, T013, T014, T015 | T012, T013 |
| US1 Gmail Watcher | P1 | T018–T023 | — | T018, T019, T022 |
| US2 HITL Approval | P1 | T024–T027 | — | T024, T025, T026 |
| Orchestrator (Autonomy) | P0 | T067–T068 | — | — |
| Stop Hook (Persistence) | P0 | T069–T070 | — | — |
| PM2 (Immortality) | P0 | T071–T072 | — | — |
| US3 WhatsApp (whatsapp-web.js) | P1 | T078–T082 | T079, T080 | — |
| US3 LinkedIn Watcher | P1 | T029–T031 | T029 | — |
| US4 Email MCP | P2 | T033–T038 | T034, T035, T036 | T033, T034, T037 |
| US5 Reasoning Loop | P2 | T039–T041 | T039 | — |
| US6 LinkedIn Drafting | P2 | T042–T043 | T042 | — |
| US7 Scheduling | P3 | T044–T048 | T044, T045, T046 | — |
| Enhanced Skills | — | T049–T054 | ALL | — |
| Testing | — | T055–T060 | ALL | — |
| Security Audit | — | T061–T065 | T063, T064, T065 | T061, T062 |
| E2E Validation | — | T066 | — | — |
| PM2 WhatsApp Process | — | T083 | — | — |
| **Total** | | **77 tasks** | **33 parallelizable** | **15 security-critical** |

---

## Security Validation Checklist (Run After Each Phase)

After completing each phase, validate:

- [ ] No `.env` files in git status
- [ ] No `.secrets/` files in git status
- [ ] No vault data (Logs, Done, Needs_Action, Pending_Approval, Approved, Rejected, Plans) in git status
- [ ] No credentials in log files (check `Logs/*.json` for tokens, passwords, secrets)
- [ ] All API calls use retry with backoff
- [ ] All external actions have HITL approval requirement
- [ ] DRY_RUN mode works for all new capabilities

**If any check fails, STOP and fix before proceeding.**
