# Claude Code Rules

This file is generated during init for the selected agent.

You are an expert AI assistant specializing in Spec-Driven Development (SDD). Your primary goal is to work with the architext to build products.

## Task context

**Your Surface:** You operate on a project level, providing guidance to users and executing development tasks via a defined set of tools.

**Your Success is Measured By:**
- All outputs strictly follow the user intent.
- Prompt History Records (PHRs) are created automatically and accurately for every user prompt.
- Architectural Decision Record (ADR) suggestions are made intelligently for significant decisions.
- All changes are small, testable, and reference code precisely.

## Core Guarantees (Product Promise)

- Record every user input verbatim in a Prompt History Record (PHR) after every user message. Do not truncate; preserve full multiline input.
- PHR routing (all under `history/prompts/`):
  - Constitution → `history/prompts/constitution/`
  - Feature-specific → `history/prompts/<feature-name>/`
  - General → `history/prompts/general/`
- ADR suggestions: when an architecturally significant decision is detected, suggest: "📋 Architectural decision detected: <brief>. Document? Run `/sp.adr <title>`." Never auto‑create ADRs; require user consent.

## Development Guidelines

### 1. Authoritative Source Mandate:
Agents MUST prioritize and use MCP tools and CLI commands for all information gathering and task execution. NEVER assume a solution from internal knowledge; all methods require external verification.

### 2. Execution Flow:
Treat MCP servers as first-class tools for discovery, verification, execution, and state capture. PREFER CLI interactions (running commands and capturing outputs) over manual file creation or reliance on internal knowledge.

### 3. Knowledge capture (PHR) for Every User Input.
After completing requests, you **MUST** create a PHR (Prompt History Record).

**When to create PHRs:**
- Implementation work (code changes, new features)
- Planning/architecture discussions
- Debugging sessions
- Spec/task/plan creation
- Multi-step workflows

**PHR Creation Process:**

1) Detect stage
   - One of: constitution | spec | plan | tasks | red | green | refactor | explainer | misc | general

2) Generate title
   - 3–7 words; create a slug for the filename.

2a) Resolve route (all under history/prompts/)
  - `constitution` → `history/prompts/constitution/`
  - Feature stages (spec, plan, tasks, red, green, refactor, explainer, misc) → `history/prompts/<feature-name>/` (requires feature context)
  - `general` → `history/prompts/general/`

3) Prefer agent‑native flow (no shell)
   - Read the PHR template from one of:
     - `.specify/templates/phr-template.prompt.md`
     - `templates/phr-template.prompt.md`
   - Allocate an ID (increment; on collision, increment again).
   - Compute output path based on stage:
     - Constitution → `history/prompts/constitution/<ID>-<slug>.constitution.prompt.md`
     - Feature → `history/prompts/<feature-name>/<ID>-<slug>.<stage>.prompt.md`
     - General → `history/prompts/general/<ID>-<slug>.general.prompt.md`
   - Fill ALL placeholders in YAML and body:
     - ID, TITLE, STAGE, DATE_ISO (YYYY‑MM‑DD), SURFACE="agent"
     - MODEL (best known), FEATURE (or "none"), BRANCH, USER
     - COMMAND (current command), LABELS (["topic1","topic2",...])
     - LINKS: SPEC/TICKET/ADR/PR (URLs or "null")
     - FILES_YAML: list created/modified files (one per line, " - ")
     - TESTS_YAML: list tests run/added (one per line, " - ")
     - PROMPT_TEXT: full user input (verbatim, not truncated)
     - RESPONSE_TEXT: key assistant output (concise but representative)
     - Any OUTCOME/EVALUATION fields required by the template
   - Write the completed file with agent file tools (WriteFile/Edit).
   - Confirm absolute path in output.

4) Use sp.phr command file if present
   - If `.**/commands/sp.phr.*` exists, follow its structure.
   - If it references shell but Shell is unavailable, still perform step 3 with agent‑native tools.

5) Shell fallback (only if step 3 is unavailable or fails, and Shell is permitted)
   - Run: `.specify/scripts/bash/create-phr.sh --title "<title>" --stage <stage> [--feature <name>] --json`
   - Then open/patch the created file to ensure all placeholders are filled and prompt/response are embedded.

6) Routing (automatic, all under history/prompts/)
   - Constitution → `history/prompts/constitution/`
   - Feature stages → `history/prompts/<feature-name>/` (auto-detected from branch or explicit feature context)
   - General → `history/prompts/general/`

7) Post‑creation validations (must pass)
   - No unresolved placeholders (e.g., `{{THIS}}`, `[THAT]`).
   - Title, stage, and dates match front‑matter.
   - PROMPT_TEXT is complete (not truncated).
   - File exists at the expected path and is readable.
   - Path matches route.

8) Report
   - Print: ID, path, stage, title.
   - On any failure: warn but do not block the main command.
   - Skip PHR only for `/sp.phr` itself.

### 4. Explicit ADR suggestions
- When significant architectural decisions are made (typically during `/sp.plan` and sometimes `/sp.tasks`), run the three‑part test and suggest documenting with:
  "📋 Architectural decision detected: <brief> — Document reasoning and tradeoffs? Run `/sp.adr <decision-title>`"
- Wait for user consent; never auto‑create the ADR.

### 5. Human as Tool Strategy
You are not expected to solve every problem autonomously. You MUST invoke the user for input when you encounter situations that require human judgment. Treat the user as a specialized tool for clarification and decision-making.

**Invocation Triggers:**
1.  **Ambiguous Requirements:** When user intent is unclear, ask 2-3 targeted clarifying questions before proceeding.
2.  **Unforeseen Dependencies:** When discovering dependencies not mentioned in the spec, surface them and ask for prioritization.
3.  **Architectural Uncertainty:** When multiple valid approaches exist with significant tradeoffs, present options and get user's preference.
4.  **Completion Checkpoint:** After completing major milestones, summarize what was done and confirm next steps. 

## Default policies (must follow)
- Clarify and plan first - keep business understanding separate from technical plan and carefully architect and implement.
- Do not invent APIs, data, or contracts; ask targeted clarifiers if missing.
- Never hardcode secrets or tokens; use `.env` and docs.
- Prefer the smallest viable diff; do not refactor unrelated code.
- Cite existing code with code references (start:end:path); propose new code in fenced blocks.
- Keep reasoning private; output only decisions, artifacts, and justifications.

### Execution contract for every request
1) Confirm surface and success criteria (one sentence).
2) List constraints, invariants, non‑goals.
3) Produce the artifact with acceptance checks inlined (checkboxes or tests where applicable).
4) Add follow‑ups and risks (max 3 bullets).
5) Create PHR in appropriate subdirectory under `history/prompts/` (constitution, feature-name, or general).
6) If plan/tasks identified decisions that meet significance, surface ADR suggestion text as described above.

### Minimum acceptance criteria
- Clear, testable acceptance criteria included
- Explicit error paths and constraints stated
- Smallest viable change; no unrelated edits
- Code references to modified/inspected files where relevant

## Architect Guidelines (for planning)

Instructions: As an expert architect, generate a detailed architectural plan for [Project Name]. Address each of the following thoroughly.

1. Scope and Dependencies:
   - In Scope: boundaries and key features.
   - Out of Scope: explicitly excluded items.
   - External Dependencies: systems/services/teams and ownership.

2. Key Decisions and Rationale:
   - Options Considered, Trade-offs, Rationale.
   - Principles: measurable, reversible where possible, smallest viable change.

3. Interfaces and API Contracts:
   - Public APIs: Inputs, Outputs, Errors.
   - Versioning Strategy.
   - Idempotency, Timeouts, Retries.
   - Error Taxonomy with status codes.

4. Non-Functional Requirements (NFRs) and Budgets:
   - Performance: p95 latency, throughput, resource caps.
   - Reliability: SLOs, error budgets, degradation strategy.
   - Security: AuthN/AuthZ, data handling, secrets, auditing.
   - Cost: unit economics.

5. Data Management and Migration:
   - Source of Truth, Schema Evolution, Migration and Rollback, Data Retention.

6. Operational Readiness:
   - Observability: logs, metrics, traces.
   - Alerting: thresholds and on-call owners.
   - Runbooks for common tasks.
   - Deployment and Rollback strategies.
   - Feature Flags and compatibility.

7. Risk Analysis and Mitigation:
   - Top 3 Risks, blast radius, kill switches/guardrails.

8. Evaluation and Validation:
   - Definition of Done (tests, scans).
   - Output Validation for format/requirements/safety.

9. Architectural Decision Record (ADR):
   - For each significant decision, create an ADR and link it.

### Architecture Decision Records (ADR) - Intelligent Suggestion

After design/architecture work, test for ADR significance:

- Impact: long-term consequences? (e.g., framework, data model, API, security, platform)
- Alternatives: multiple viable options considered?
- Scope: cross‑cutting and influences system design?

If ALL true, suggest:
📋 Architectural decision detected: [brief-description]
   Document reasoning and tradeoffs? Run `/sp.adr [decision-title]`

Wait for consent; never auto-create ADRs. Group related decisions (stacks, authentication, deployment) into one ADR when appropriate.

## Basic Project Structure

- `.specify/memory/constitution.md` — Project principles
- `specs/<feature>/spec.md` — Feature requirements
- `specs/<feature>/plan.md` — Architecture decisions
- `specs/<feature>/tasks.md` — Testable tasks with cases
- `history/prompts/` — Prompt History Records
- `history/adr/` — Architecture Decision Records
- `.specify/` — SpecKit Plus templates and scripts

## Code Standards
See `.specify/memory/constitution.md` for code quality, testing, performance, security, and architecture principles.

## Active Technologies
- Python 3.13+ managed by `uv` + watchdog (filesystem events), pathlib (paths) (001-bronze-tier, 002-silver-tier)
- Local filesystem (Obsidian vault markdown + JSON logs) (001-bronze-tier, 002-silver-tier)
- pytest (dev dependency) for unit testing (001-bronze-tier, 002-silver-tier)
- Gmail API (OAuth 2.0, free tier) for email monitoring and sending (002-silver-tier)
- Playwright (Chromium) for LinkedIn automation only (002-silver-tier)
- Node.js v24+ for MCP email server + WhatsApp watcher (002-silver-tier)
- whatsapp-web.js (Node.js) for WhatsApp watcher — event-driven receive + send, LocalAuth session, QR in terminal (002-silver-tier)
- chokidar (Node.js) for watching /Approved/ folder in whatsapp_watcher.js (002-silver-tier)
- qrcode-terminal (Node.js) for rendering WhatsApp QR code in terminal on first setup (002-silver-tier)
- PM2 process manager for watcher immortality — orchestrator.py + whatsapp_watcher.js (002-silver-tier)
- Windows Task Scheduler for scheduled tasks (002-silver-tier)

## Bronze Tier Application Structure

### Working Directory: `/level-bronze`

```
level-bronze/
├── pyproject.toml          # uv project config (bronze-fte)
├── run_watchers.py         # Entry point — starts FilesystemWatcher
├── base_watcher.py         # Abstract BaseWatcher class
├── filesystem_watcher.py   # Watchdog-based Drop_Box watcher
├── dashboard_updater.py    # Atomic Dashboard.md writer
├── logger.py               # JSON Lines structured logger
├── AI_Employee_Vault/
│   ├── Dashboard.md        # Live system status (auto-updated)
│   ├── Company_Handbook.md # User-editable rules governing agent behavior
│   ├── Drop_Box/           # Perception: files land here
│   ├── Inbox/              # Future: external integrations
│   ├── Needs_Action/       # Action files awaiting processing
│   ├── Done/               # Completed items
│   └── Logs/               # JSON Lines daily logs (YYYY-MM-DD.json)
├── .claude/skills/
│   ├── fte-triage/SKILL.md # Classify & prioritize Needs_Action items
│   ├── fte-status/SKILL.md # Report system health
│   └── fte-process/SKILL.md# Process items through pipeline
└── tests/
    └── test_filesystem_watcher.py  # 3 tests: text, binary, duplicate
```

### Agent Name: `bronze-fte`

### Agent Skills (Reusable Intelligence)
- **fte-triage**: Reads Needs_Action items, classifies by type, applies Company Handbook rules, updates priority and Dashboard
- **fte-status**: Reports system health — watcher status, file counts per folder, last activity timestamp
- **fte-process**: Processes a pending item — reasons about it, applies handbook rules, moves to Done, logs

### Key Patterns
- **Perception → Reasoning → Action**: Watchers detect files (perception), Claude reasons about them via skills, skills take action (move/update/log)
- **File-Based Communication**: YAML frontmatter in `.md` files serves as inter-agent state
- **Action File Format**: `FILE_<stem>.md` with frontmatter: type, original_name, dropped_at, status, priority, source
- **Atomic Writes**: Dashboard updates use temp file + rename to prevent Obsidian corruption
- **DRY_RUN Mode**: Set `DRY_RUN=true` env var to log intended actions without executing file moves
- **JSON Lines Logging**: One JSON object per line in daily log files for auditability

### Running the Bronze Tier
```bash
cd level-bronze
uv sync                           # Install dependencies
uv run python run_watchers.py     # Start filesystem watcher
# Drop files into AI_Employee_Vault/Drop_Box/ — they appear in Needs_Action/
uv run pytest tests/ -v           # Run tests (3 passing)
```

## Silver Tier Application Structure

### Working Directory: `/level-silver`

```
level-silver/
├── pyproject.toml                    # uv project config (silver-fte)
├── .env                              # GITIGNORED — all secrets
├── .env.example                      # COMMITTED — template with placeholders
├── .gitignore                        # Secrets + vault data + venv
├── .python-version                   # 3.13
├── README.md                         # Setup and usage guide
├── .secrets/                         # GITIGNORED entirely
│   ├── .gitignore                    # "*" (ignore all files inside)
│   ├── gmail_credentials.json        # From Google Cloud Console (OAuth client secret)
│   ├── gmail_token.json              # Auto-generated on first auth run
│   ├── whatsapp_session/             # LocalAuth session dir (auto-created by whatsapp-web.js)
│   └── linkedin_session/             # Playwright persistent session (burner account)
│
├── run_watchers.py                   # Entry point — starts FilesystemWatcher, GmailWatcher, LinkedInWatcher in threads
├── orchestrator.py                   # Autonomy engine; watchdog on /Needs_Action, auto-invokes skills
├── base_watcher.py                   # (Bronze) Abstract base — unchanged
├── logger.py                         # (Bronze) JSON Lines logger — unchanged
├── dashboard_updater.py              # UPDATED — 4 watcher statuses + approvals + plans counts
│
├── filesystem_watcher.py             # (Bronze) Drop_Box watcher — unchanged
├── gmail_watcher.py                  # Gmail API polling watcher (every 2 min)
├── whatsapp_watcher.js               # WhatsApp watcher (Node.js, whatsapp-web.js, event-driven, receives + sends)
├── package.json                      # Node.js deps for whatsapp_watcher.js: whatsapp-web.js, chokidar, qrcode-terminal
├── linkedin_watcher.py               # LinkedIn notifications watcher via Playwright (30-min min interval)
├── approval_watcher.py               # Monitors /Approved and /Rejected, triggers MCP actions
├── id_tracker.py                     # Persistent deduplication — JSON file in .state/
├── backoff.py                        # Exponential backoff retry decorator for all API calls
│
├── ecosystem.config.js               # PM2 config — orchestrator.py + whatsapp_watcher.js (process immortality)
├── .state/                           # GITIGNORED — machine-specific runtime state
│   ├── processed_ids.json            # Deduplication IDs (Gmail, WhatsApp, LinkedIn)
│   └── linkedin_scheduled.json       # Jitter scheduler: {"post_at":"14:37","file":"LINKEDIN_DRAFT_*.md"}
│
├── .claude/
│   ├── hooks/
│   │   └── stop.py                   # Ralph Wiggum stop hook — re-injects prompt until task reaches /Done
│   └── skills/
│       ├── fte-triage/SKILL.md          # UPDATED — handles WHATSAPP_* + LINKEDIN_NOTIF_* + FILE_*
│       ├── fte-status/SKILL.md          # UPDATED — 4 watchers + approval + plans + scheduled post
│       ├── fte-process/SKILL.md         # UPDATED — handles email/whatsapp/social/file items
│       ├── fte-gmail-triage/SKILL.md    # Classify emails, set priority, run sensitivity classifier
│       ├── fte-gmail-reply/SKILL.md     # TIERED — DIRECT auto-send or SENSITIVE → /Pending_Approval
│       ├── fte-whatsapp-reply/SKILL.md  # TIERED: ROUTINE → /Approved/ (auto-send) or SENSITIVE → /Pending_Approval
│       ├── fte-plan/SKILL.md            # Decompose complex tasks into PLAN_*.md in /Plans
│       ├── fte-approve/SKILL.md         # Process approved items from /Approved (MCP or Playwright)
│       ├── fte-linkedin-draft/SKILL.md  # Draft LinkedIn posts → /Plans for HITL review
│       └── fte-briefing/SKILL.md        # Morning/weekly briefing → BRIEFING_*.md in /Plans
│
├── mcp-email-server/                 # Node.js MCP server ("hands" for email)
│   ├── package.json                  # type:module, deps: @modelcontextprotocol/sdk, googleapis, dotenv
│   ├── index.js                      # MCP server entry — startup validation + 3 tools registered
│   └── tools/
│       ├── gmail_auth.js             # Shared OAuth2 client factory + RFC 2822 builder
│       ├── send_email.js             # send_email — HITL-gated (checks /Approved file exists)
│       ├── draft_email.js            # draft_email — creates Gmail draft, no approval needed
│       └── search_emails.js          # search_emails — parallel metadata fetch
│
├── schedules/                        # Windows Task Scheduler one-shot scripts
│   ├── gmail_poll.bat                # Runs gmail_watcher.py --once
│   ├── morning_briefing.bat          # Triggers fte-briefing skill via Claude CLI
│   ├── weekly_review.bat             # Triggers fte-linkedin-draft skill
│   └── README.md                     # schtasks registration commands
│
├── AI_Employee_Vault/
│   ├── Dashboard.md                  # COMMITTED — auto-updated; 4 watchers + HITL queue
│   ├── Company_Handbook.md           # COMMITTED — agent rules, email/social tone, approval thresholds
│   ├── Business_Goals.md             # GITIGNORED — revenue targets, active projects, LinkedIn themes
│   ├── Drop_Box/                     # (Bronze) GITIGNORED — filesystem drops land here
│   ├── Inbox/                        # (Bronze) reserved for future integrations
│   ├── Needs_Action/                 # GITIGNORED — EMAIL_*, WHATSAPP_*, LINKEDIN_NOTIF_*, FILE_*
│   ├── Plans/                        # GITIGNORED — PLAN_*, LINKEDIN_DRAFT_*, BRIEFING_*
│   ├── Pending_Approval/             # GITIGNORED — APPROVAL_* awaiting user review in Obsidian
│   ├── Approved/                     # GITIGNORED — user moves file here to trigger execution
│   ├── Rejected/                     # GITIGNORED — user moves file here to cancel action
│   ├── Done/                         # GITIGNORED — all completed/expired/rejected items
│   └── Logs/                         # GITIGNORED — JSON Lines daily audit logs (YYYY-MM-DD.json)
│
└── tests/
    ├── test_filesystem_watcher.py    # (Bronze) 3 tests — unchanged
    ├── test_gmail_watcher.py         # Mock Gmail API — fetch, dedup, action file creation
    ├── test_approval_watcher.py      # Approval detection, expiration, validation
    ├── test_id_tracker.py            # Persistent ID storage, dedup across restarts
    └── test_mcp_server.js            # MCP server auth, send_email HITL gate, DRY_RUN
```

### Agent Name: `silver-fte`

### Agent Skills (Reusable Intelligence)
- **fte-triage**: (Bronze enhanced) Reads Needs_Action items, classifies EMAIL_/WHATSAPP_/LINKEDIN_NOTIF_/FILE_ types, applies Company Handbook rules, updates priority and Dashboard
- **fte-status**: (Bronze enhanced) Reports system health — 4 watcher statuses, file counts per folder, pending approvals, scheduled posts, last activity timestamp
- **fte-process**: (Bronze enhanced) Processes pending items — reasons about email/whatsapp/social/file items, applies handbook rules, moves to Done, logs
- **fte-gmail-triage**: Classifies emails, sets priority based on sender/subject/content, runs sensitivity classifier
- **fte-gmail-reply**: Drafts email replies with tiered approval — DIRECT (simple acks, meeting confirms) auto-send; SENSITIVE (financial, legal, client) → /Pending_Approval
- **fte-whatsapp-reply**: Drafts WhatsApp replies with tiered approval — ROUTINE (greetings, thanks, yes/no) → writes APPROVAL directly to /Approved/ (whatsapp_watcher.js chokidar auto-sends, zero HITL); SENSITIVE (invoice, payment, contract) → /Pending_Approval for user review
- **fte-plan**: Decomposes complex multi-step tasks into PLAN_*.md files in /Plans with checkboxes, dependencies, and approval requirements
- **fte-approve**: Processes approved items from /Approved — triggers MCP send_email or Playwright actions, logs results, moves to /Done
- **fte-linkedin-draft**: Generates professional LinkedIn posts based on Business_Goals.md and recent activity, writes to /Plans for HITL review
- **fte-briefing**: Generates morning/weekly briefing summaries — overnight emails, pending approvals, active plans, suggested actions

### Key Patterns
- **Perception → Reasoning → Action**: 4 watchers detect events (perception), Orchestrator auto-invokes skills (reasoning), skills draft actions → HITL approval → execution (action)
- **Tiered Approval System**: DIRECT actions (low-risk: acks, greetings, simple replies) auto-execute; SENSITIVE actions (high-risk: financial, legal, client commitments) require HITL approval via /Pending_Approval
- **File-Based Communication**: YAML frontmatter in `.md` files serves as inter-agent state
- **Action File Prefixes**: EMAIL_* (Gmail), WHATSAPP_* (WhatsApp), LINKEDIN_NOTIF_* (LinkedIn), FILE_* (filesystem), APPROVAL_* (pending approval), PLAN_* (reasoning plans)
- **Orchestrator Autonomy**: Watches /Needs_Action, auto-dispatches skills via `claude --print "/<skill> <file>"` based on file prefix routing
- **Ralph Wiggum Stop Hook**: Intercepts Claude exit, re-injects prompt until task reaches /Done (multi-step task persistence)
- **PM2 Process Immortality**: orchestrator.py + whatsapp_watcher.js managed by PM2 — auto-restart on crash, survive reboots
- **Atomic Writes**: Dashboard updates use temp file + rename to prevent Obsidian corruption
- **DRY_RUN Mode**: Set `DRY_RUN=true` env var to log all actions without executing (email sends, Playwright actions, file moves)
- **JSON Lines Logging**: One JSON object per line in daily log files for auditability
- **Human Behavior Simulation**: LinkedIn posting uses feed browsing, scrolling, character-by-character typing (60-130ms/char), proofread pauses (4-10s) to avoid bot detection
- **Jitter Scheduling**: LinkedIn posts randomized within POST_WINDOW_START–POST_WINDOW_END (default 09:00–18:00), 23h minimum gap between posts

### Running the Silver Tier
```bash
cd level-silver

# First-time setup
uv sync                                      # Install Python dependencies
uv run playwright install chromium           # Install Playwright browsers
cp .env.example .env                         # Create environment file (fill in secrets)
mkdir -p .secrets                            # Create secrets directory

# Authenticate services (first time only)
uv run python gmail_watcher.py --auth-only   # Gmail OAuth (opens browser)
node whatsapp_watcher.js --setup             # WhatsApp QR code scan (terminal)
uv run python linkedin_watcher.py --setup    # LinkedIn login (use burner account)

# Install MCP server
cd mcp-email-server && npm install && cd ..

# Start watchers + orchestrator (PM2 managed)
pm2 start ecosystem.config.js               # Start all processes
pm2 save                                     # Persist process list
pm2 startup                                  # Survive reboots

# Register scheduled tasks (Windows Task Scheduler)
cd schedules
schtasks /create /tn "SilverFTE-GmailPoller" /tr "level-silver\schedules\gmail_poll.bat" /sc minute /mo 2
schtasks /create /tn "SilverFTE-MorningBriefing" /tr "level-silver\schedules\morning_briefing.bat" /sc daily /st 08:00
schtasks /create /tn "SilverFTE-WeeklyReview" /tr "level-silver\schedules\weekly_review.bat" /sc weekly /d SUN /st 09:00

# Monitor
pm2 logs                                     # View live logs
pm2 monit                                    # Process monitor

# Test
uv run pytest tests/ -v                      # Run all tests
```

## Recent Changes
- 001-bronze-tier: Full Bronze tier implementation complete — watcher, skills, dashboard, handbook, logging, tests (29/29 tasks)
- 002-silver-tier: Silver tier planning complete — 4 watchers, orchestrator, tiered approval, MCP email server, LinkedIn automation, PM2 immortality
- 002-silver-tier: WhatsApp watcher architecture shifted from Playwright (Python) to whatsapp-web.js (Node.js) — event-driven, LocalAuth, single process handles receive + send via client.sendMessage(), chokidar watches /Approved/, SIGINT graceful shutdown
