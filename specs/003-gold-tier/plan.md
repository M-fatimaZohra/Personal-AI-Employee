# Implementation Plan: Gold Tier — Autonomous Business Employee

**Branch**: `003-gold-tier` | **Date**: 2026-03-03 | **Spec**: [specs/003-gold-tier/spec.md](spec.md)
**Input**: Feature specification from `/specs/003-gold-tier/spec.md`
**Working Directory**: `/level-gold` (copy of `/level-silver` + Gold extensions)
**Agent Name**: `gold-fte`

## Summary

Gold Tier transforms the Silver autonomous assistant into a **business manager** by adding financial oversight (Odoo accounting), social media presence (Facebook, Instagram, Twitter), and executive intelligence (weekly CEO briefing). Two MCP servers (email, odoo) operate concurrently. Social media posting uses direct Python Playwright execution (NO MCP layer) following the proven LinkedIn poster pattern. A circuit breaker pattern ensures graceful degradation when services fail. The signature feature is the Sunday CEO briefing that combines Odoo financials, task completion metrics, and proactive suggestions (unused subscriptions, overdue invoices, high-engagement posts). All integrations use $0 cost approaches: Odoo Community in Docker, Playwright automation for social media (no API keys). Implementation prioritizes Odoo integration (P1) before social media (P2) to maximize business value before Claude Pro usage limits reset.

## Technical Context

**Language/Version**: Python 3.13+ via `uv` (watchers, orchestrator) + Node.js v24+ (MCP servers)
**Primary Dependencies**:
- Python: `google-auth`, `google-auth-oauthlib`, `google-api-python-client` (existing), `playwright` (existing), `watchdog` (existing), `python-dotenv` (existing)
- Node.js (MCP servers): `@modelcontextprotocol/sdk`, `googleapis` (existing), `dotenv` (existing), `zod` (existing)
- Docker: `odoo:19`, `postgres:15` (for Odoo backend)
**Storage**: Local filesystem (Obsidian vault) + Odoo PostgreSQL in Docker (localhost:8069)
**Testing**: `pytest` (Python watchers), manual integration tests via vault, curl tests for Odoo JSON-RPC
**Target Platform**: Windows 11, Python 3.13, Node.js v24+, Docker Desktop
**Project Type**: Single project (agent system with multiple watchers + MCP servers)
**Performance Goals**: Odoo queries <2s, social media posts <5s after approval, CEO briefing generation <30s, watcher response <30s
**Constraints**: $0 cost (no paid APIs), HITL approval for all writes, local-first (no cloud storage), Playwright sessions must survive 7+ days without re-auth, social media posting via direct Python Playwright (NO MCP layer)
**Scale/Scope**: 2 MCP servers (email, odoo), 3 social media watchers + 3 Python poster scripts, 4 new skills, 7 updated skills, ~2000 LOC new code

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Local-First & Privacy-Centric | ✅ PASS | Odoo runs in Docker locally (localhost:8069). All data in vault. Secrets in .env (ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_API_KEY, FB_SESSION_DIR, IG_SESSION_DIR, TWITTER_SESSION_DIR). Social media sessions stored in .secrets/ (gitignored). |
| II. Perception → Reasoning → Action | ✅ PASS | Social media watcher (perception) → fte-social-post skill (reasoning) → Python Playwright poster script (action). Odoo watcher polls financials → fte-audit skill → mcp-odoo-server. No layer bypassed. |
| III. File-Based Communication | ✅ PASS | New file prefixes: SOCIAL_FB_*.md, SOCIAL_IG_*.md, TWITTER_*.md in /Needs_Action. CEO_BRIEFING_*.md in /Plans. APPROVAL_odoo_*.md, APPROVAL_social_*.md in /Pending_Approval. Same folder contract as Silver. |
| IV. Human-in-the-Loop | ✅ PASS | All Odoo write operations (create_invoice, create_partner) require HITL approval. All social media posts require HITL approval. Read-only ops (get_financial_summary, list_transactions, get_social_summary) auto-allowed. |
| V. Agent Skills Architecture | ✅ PASS | All new functionality as skills: fte-audit (CEO briefing), fte-social-post (draft posts), fte-social-summary (metrics), fte-odoo-audit (financial queries). Updated skills: fte-approve, fte-briefing, fte-triage. |
| VI. Observability & Audit Logging | ✅ PASS | Enhanced log format adds approval_status, approved_by, parameters fields. 90-day retention policy enforced. DRY_RUN mode supported. Dashboard shows Odoo balance + social engagement. |
| VII. Incremental Tier Progression | ✅ PASS | Building on complete Silver tier (all watchers, orchestrator, email MCP, approval pipeline, Ralph Wiggum hook tested and stable). level-silver/ copied to level-gold/ before starting. |
| VIII. Resilience & Graceful Degradation | ✅ PASS | Circuit breaker pattern for Odoo, social media watchers, MCP servers (3 failures → degraded mode for 15 min). Exponential backoff (2s, 4s, 8s). System continues with available services. Dashboard shows degraded services. |

## Project Structure

### Documentation (this feature)

```text
specs/003-gold-tier/
├── spec.md              # Feature specification (complete)
├── plan.md              # This file (in progress)
├── research.md          # Phase 0 output (Odoo JSON-RPC, Playwright social media)
├── data-model.md        # Phase 1 output (Financial Transaction, Social Post, CEO Briefing entities)
├── quickstart.md        # Phase 1 output (Docker Compose setup, MCP registration)
├── contracts/           # Phase 1 output (Odoo JSON-RPC contracts, MCP tool schemas)
└── tasks.md             # Phase 2 output (/sp.tasks command)
```

### Source Code (repository root)

```text
level-gold/
├── pyproject.toml                    # gold-fte agent (uv)
├── .env.example                      # Template with ODOO_*, FB_*, IG_*, TWITTER_* vars
├── .gitignore                        # Adds .secrets/, AI_Employee_Vault/ (except Dashboard.md)
│
├── run_watchers.py                   # (Silver) Entry point — starts all watchers
├── orchestrator.py                   # UPDATED: + social media routing, Odoo audit tick
├── base_watcher.py                   # (Silver) Unchanged
├── logger.py                         # UPDATED: + approval_status, approved_by, parameters fields
├── dashboard_updater.py              # UPDATED: + Odoo balance row, social engagement row
├── backoff.py                        # UPDATED: + circuit breaker (closed/open/half_open states)
├── id_tracker.py                     # (Silver) Unchanged
│
├── filesystem_watcher.py             # (Silver) Unchanged
├── gmail_watcher.py                  # (Silver) Unchanged
├── whatsapp_watcher.js               # (Silver) Unchanged
├── linkedin_watcher.py               # (Silver) Unchanged
├── approval_watcher.py               # UPDATED: + odoo_action, social_post types
├── facebook_watcher.py               # NEW: Playwright watcher for Facebook notifications
├── instagram_watcher.py              # NEW: Playwright watcher for Instagram notifications
├── twitter_watcher.py                # NEW: Playwright watcher for Twitter mentions/DMs
├── facebook_poster.py                # NEW: Python Playwright poster (NO MCP) — WORKING ✅
├── instagram_poster.py               # NEW: Python Playwright poster (NO MCP)
├── twitter_poster.py                 # NEW: Python Playwright poster (NO MCP)
│
├── mcp-email-server/                 # (Silver) Unchanged
│   ├── package.json
│   ├── index.js
│   └── tools/
│       ├── gmail_auth.js
│       ├── send_email.js
│       ├── draft_email.js
│       └── search_emails.js
│
├── mcp-odoo-server/                  # NEW: Odoo accounting MCP
│   ├── package.json
│   ├── index.js
│   └── tools/
│       ├── odoo_auth.js              # JSON-RPC 2.0 session management
│       ├── get_financial_summary.js  # Read: revenue, expenses, invoices
│       ├── list_transactions.js      # Read: transaction search/filter
│       ├── create_invoice.js         # Write: HITL-gated invoice creation
│       └── create_partner.js         # Write: HITL-gated customer creation
│
├── .claude/
│   ├── hooks/
│   │   └── stop.py                   # (Silver) Ralph Wiggum hook — unchanged
│   └── skills/
│       ├── fte-triage/SKILL.md          # UPDATED: + SOCIAL_*, TWITTER_* routing
│       ├── fte-status/SKILL.md          # UPDATED: + Odoo, social media watcher status
│       ├── fte-process/SKILL.md         # (Silver) Unchanged
│       ├── fte-gmail-triage/SKILL.md    # (Silver) Unchanged
│       ├── fte-gmail-reply/SKILL.md     # (Silver) Unchanged
│       ├── fte-whatsapp-reply/SKILL.md  # (Silver) Unchanged
│       ├── fte-plan/SKILL.md            # (Silver) Unchanged
│       ├── fte-approve/SKILL.md         # UPDATED: + odoo_action, social_post (calls Python posters via Bash)
│       ├── fte-linkedin-draft/SKILL.md  # (Silver) Unchanged
│       ├── fte-briefing/SKILL.md        # UPDATED: + Odoo balance line
│       ├── fte-audit/SKILL.md           # NEW: Weekly CEO briefing generator
│       ├── fte-social-post/SKILL.md     # NEW: Draft FB/IG/Twitter posts
│       └── fte-odoo-audit/SKILL.md      # NEW: Odoo financial queries
│
├── AI_Employee_Vault/
│   ├── Dashboard.md                  # UPDATED: + Odoo balance, social engagement
│   ├── Company_Handbook.md           # (Silver) Unchanged
│   ├── Business_Goals.md             # User-maintained (revenue targets, social themes)
│   ├── Drop_Box/                     # (Bronze) Unchanged
│   ├── Inbox/                        # (Bronze) Reserved
│   ├── Needs_Action/                 # + SOCIAL_FB_*, SOCIAL_IG_*, TWITTER_* files
│   ├── Plans/                        # + CEO_BRIEFING_*.md files
│   ├── Pending_Approval/             # + APPROVAL_odoo_*, APPROVAL_social_* files
│   ├── Approved/                     # (Silver) Unchanged
│   ├── Rejected/                     # (Silver) Unchanged
│   ├── Done/                         # (Silver) Unchanged
│   └── Logs/                         # UPDATED: + approval_status, 90-day retention
│
├── schedules/
│   ├── gmail_poll.bat                # (Silver) Unchanged
│   ├── morning_briefing.bat          # (Silver) Unchanged
│   ├── weekly_review.bat             # (Silver) Unchanged
│   └── weekly_audit.bat              # NEW: Sunday 9 AM CEO briefing trigger
│
├── ecosystem.config.cjs              # UPDATED: + facebook_watcher.py, instagram_watcher.py, twitter_watcher.py processes
├── docker-compose.yml                # NEW: Odoo + PostgreSQL containers
│
└── tests/
    ├── test_filesystem_watcher.py    # (Bronze) Unchanged
    ├── test_gmail_watcher.py         # (Silver) Unchanged
    ├── test_approval_watcher.py      # (Silver) Unchanged
    ├── test_id_tracker.py            # (Silver) Unchanged
    ├── test_mcp_email_server.js      # (Silver) Unchanged
    ├── test_odoo_mcp_server.js       # NEW: Odoo JSON-RPC + MCP tool tests
    ├── test_facebook_poster.py       # NEW: Facebook Playwright poster tests
    ├── test_instagram_poster.py      # NEW: Instagram Playwright poster tests
    ├── test_twitter_poster.py        # NEW: Twitter Playwright poster tests
    ├── test_facebook_watcher.py      # NEW: Facebook watcher tests
    ├── test_instagram_watcher.py     # NEW: Instagram watcher tests
    └── test_twitter_watcher.py       # NEW: Twitter watcher tests
```

**Structure Decision**: Single project structure (agent system). All code in `level-gold/` directory (copy of `level-silver/` with Gold extensions). Three MCP servers as separate Node.js packages under `mcp-*-server/` subdirectories. Watchers and orchestrator in root. Skills in `.claude/skills/`. Tests mirror source structure.

## Complexity Tracking

No violations — Constitution Check passed. All principles satisfied.

## Phase 0: Research & Discovery

### Research Tasks

**R1: Odoo JSON-RPC 2.0 API**
- **Question**: How to authenticate and call Odoo 19 methods via JSON-RPC?
- **Approach**: Read Odoo official docs, test with curl against local Docker instance
- **Deliverable**: Working curl examples for: authenticate, search invoices, create invoice, get revenue summary
- **Success**: Can query Odoo from command line before writing MCP server

**R2: Playwright Social Media Automation**
- **Question**: How to post to Facebook/Instagram/Twitter with Python Playwright without triggering bot detection?
- **Approach**: Review existing LinkedIn poster implementation (linkedin_poster.py), adapt proven patterns
- **Deliverable**: Python Playwright scripts for: login + save session, post with typing simulation, read notifications
- **Success**: Can post to test accounts from command line using direct Python execution (NO MCP layer)

**R3: Circuit Breaker Pattern in Python**
- **Question**: How to implement circuit breaker (closed/open/half_open) with exponential backoff?
- **Approach**: Review existing `backoff.py`, research circuit breaker state machine
- **Deliverable**: Enhanced `backoff.py` with state tracking and 15-minute timeout
- **Success**: Can simulate service failures and verify degraded mode behavior

**R4: Multiple MCP Server Registration**
- **Question**: How to register 2 MCP servers in Claude Code settings?
- **Approach**: Review existing email MCP registration, check Claude Code docs for multi-server format
- **Deliverable**: Example `~/.claude/settings.json` with 2 mcpServers entries (email, odoo)
- **Success**: Both servers start without port conflicts, Claude can call tools from both servers

### Research Output

All findings documented in `specs/003-gold-tier/research.md` with:
- Decision made
- Rationale
- Alternatives considered
- Code examples
- Links to documentation

## Phase 1: Design & Contracts

### Data Model

**Entity: Financial Transaction** (Odoo)
- Fields: transaction_id (int), type (invoice|payment|expense), amount (decimal), currency (str), date (ISO), customer_vendor (str), status (draft|sent|paid|overdue), due_date (ISO)
- Relationships: Customer → many Transactions
- State transitions: draft → sent → paid (or overdue if past due_date)
- Validation: amount > 0, due_date >= date, status in allowed values

**Entity: Social Media Post**
- Fields: post_id (str), platform (facebook|instagram|twitter), content (str), scheduled_time (ISO), status (draft|pending_approval|scheduled|posted), engagement_metrics (dict: likes, comments, shares)
- Relationships: None (standalone posts)
- State transitions: draft → pending_approval → scheduled → posted
- Validation: content length per platform (Twitter 280, Instagram 2200, Facebook 63206), scheduled_time in future

**Entity: CEO Briefing**
- Fields: briefing_date (ISO), week_number (int), revenue_summary (dict), expense_summary (dict), task_completion_rate (float), bottlenecks (list), proactive_suggestions (list), social_media_metrics (dict)
- Relationships: References Odoo transactions, log entries, Done folder files
- State transitions: None (generated once per week)
- Validation: briefing_date is Sunday, week_number matches ISO week

**Entity: Service Health Status**
- Fields: service_name (str), status (online|degraded|offline), last_success_time (ISO), failure_count (int), circuit_breaker_state (closed|open|half_open)
- Relationships: None (runtime state only, not persisted)
- State transitions: closed → open (after 3 failures) → half_open (after 15 min) → closed (on success) or open (on failure)
- Validation: failure_count >= 0, circuit_breaker_state in allowed values

### API Contracts

**Odoo JSON-RPC 2.0 Contract** (`contracts/odoo-jsonrpc.json`)
```json
{
  "authenticate": {
    "method": "POST /jsonrpc",
    "params": {"db": "string", "login": "string", "password": "string"},
    "returns": {"uid": "int", "session_id": "string"}
  },
  "search_read": {
    "method": "POST /jsonrpc",
    "params": {"model": "string", "domain": "array", "fields": "array"},
    "returns": {"records": "array"}
  },
  "create": {
    "method": "POST /jsonrpc",
    "params": {"model": "string", "values": "object"},
    "returns": {"id": "int"}
  }
}
```

**MCP Odoo Server Contract** (`contracts/mcp-odoo-tools.json`)
```json
{
  "get_financial_summary": {
    "input": {"month": "string (YYYY-MM)"},
    "output": {"revenue": "number", "expenses": "number", "outstanding_invoices": "array", "overdue_invoices": "array"}
  },
  "list_transactions": {
    "input": {"start_date": "string (ISO)", "end_date": "string (ISO)", "type": "string (invoice|payment|expense)"},
    "output": {"transactions": "array"}
  },
  "create_invoice": {
    "input": {"customer_id": "int", "amount": "number", "due_date": "string (ISO)", "approval_file": "string"},
    "output": {"invoice_id": "int", "status": "string"}
  }
}
```

**Python Playwright Poster Contract** (`contracts/social-posters-cli.json`)
```json
{
  "facebook_poster.py": {
    "args": ["--approval-file", "<filename>", "--content", "<text>"],
    "env": {"FB_SESSION_DIR": ".secrets/facebook_session", "FB_HEADLESS": "true"},
    "returns": "exit_code (0=success, 1=error)"
  },
  "instagram_poster.py": {
    "args": ["--approval-file", "<filename>", "--content", "<text>", "--image-path", "<path>"],
    "env": {"IG_SESSION_DIR": ".secrets/instagram_session", "IG_HEADLESS": "true"},
    "returns": "exit_code (0=success, 1=error)"
  },
  "twitter_poster.py": {
    "args": ["--approval-file", "<filename>", "--content", "<text>"],
    "env": {"TWITTER_SESSION_DIR": ".secrets/twitter_session", "TWITTER_HEADLESS": "true"},
    "returns": "exit_code (0=success, 1=error)"
  }
}
```

### Quickstart Guide

**Prerequisites**:
- Docker Desktop installed and running
- Silver Tier complete and tested
- Python 3.13+ via uv
- Node.js v24+

**Setup Steps**:
1. Copy `level-silver/` to `level-gold/`
2. Start Odoo: `cd level-gold && docker compose up -d`
3. Access Odoo: http://localhost:8069 (create database, add sample invoice)
4. Install MCP server: `cd mcp-odoo-server && npm install`
5. Register MCP server in `~/.claude/settings.json` (2 entries: email, odoo)
6. Update `.env` with Odoo credentials and social media session paths
7. Test Odoo MCP: `node mcp-odoo-server/index.js` (verify startup)
8. Create social media sessions: `uv run python facebook_poster.py --setup` (repeat for IG/Twitter)
9. Start watchers: `pm2 start ecosystem.config.cjs`
10. Verify Dashboard shows all services online

## Phase 2+: Implementation (Phased Approach)

### Phase 2A: Odoo Integration (P1 — Most Valuable)

**Goal**: Financial oversight in morning briefings and CEO briefing

**Tasks**:
1. Create `docker-compose.yml` (Odoo 19 + PostgreSQL 15)
2. Create `mcp-odoo-server/` with 4 tools (get_financial_summary, list_transactions, create_invoice, create_partner)
3. Create `fte-odoo-audit` skill (query Odoo, format financial summary)
4. Update `fte-briefing` skill (add Odoo balance line to morning briefing)
5. Create `fte-audit` skill (weekly CEO briefing with Odoo data)
6. Update `orchestrator.py` (add Odoo health check to tick)
7. Update `dashboard_updater.py` (add Odoo balance row)
8. Test: Morning briefing shows Odoo balance, CEO briefing shows revenue/expenses

**Acceptance**: User can see current month revenue and outstanding invoices in morning briefing without opening Odoo

### Phase 2B: Social Media Integration (P2 — Important but Secondary)

**Goal**: Manage Facebook, Instagram, Twitter presence

**Tasks**:
1. Create separate watchers: `facebook_watcher.py`, `instagram_watcher.py`, `twitter_watcher.py`
2. Create Python Playwright posters: `facebook_poster.py`, `instagram_poster.py`, `twitter_poster.py` (NO MCP layer)
3. Create `fte-social-post` skill (draft platform-appropriate posts)
4. Update `fte-triage` skill (route SOCIAL_FB_*, SOCIAL_IG_*, TWITTER_* files)
5. Update `fte-approve` skill (handle social_post type, call Python posters via Bash)
6. Update `orchestrator.py` (add social media routing)
7. Update `ecosystem.config.cjs` (add 3 watcher processes)
8. Test: Draft post → approve → post appears on platform

**Acceptance**: User can draft and publish social media posts to Facebook, Instagram, and Twitter with a single approval action

### Phase 2C: Error Recovery & Polish (P3 — Production Readiness)

**Goal**: Graceful degradation and comprehensive audit logging

**Tasks**:
1. Update `backoff.py` (add circuit breaker pattern with state tracking)
2. Update `logger.py` (add approval_status, approved_by, parameters fields)
3. Implement 90-day log retention policy (archive old logs to /Logs/Archive/)
4. Update `dashboard_updater.py` (show degraded services with failure reason)
5. Test: Stop Odoo container, verify system continues with degraded mode indicator
6. Test: Simulate MCP server failure, verify circuit breaker opens after 3 attempts
7. Create `test_odoo_mcp_server.js` (JSON-RPC + MCP tool tests)
8. Create `test_social_mcp_server.js` (Playwright + MCP tool tests)
9. Create `test_social_media_watcher.py` (FB/IG/Twitter watcher tests)

**Acceptance**: System continues processing emails and social media when Odoo is unavailable, with clear degraded-mode indicators in Dashboard

### Phase 2D: Documentation (P3 — Hackathon Requirement)

**Goal**: Architecture docs and lessons learned for submission

**Tasks**:
1. Create `/docs/architecture.md` (system overview, component diagram, data flow)
2. Create `/docs/lessons-learned.md` (what worked, what didn't, key decisions)
3. Create `/docs/odoo-setup.md` (Docker Compose guide, test data population)
4. Create `/docs/social-media-setup.md` (Playwright session creation, platform auth)
5. Update README.md (Gold Tier features, setup instructions)

**Acceptance**: Documentation is complete and ready for hackathon submission

## Implementation Order (Dependency-Driven)

```
1. Phase 2A: Odoo Integration (P1)
   └─ Delivers core business value before Claude Pro limits

2. Phase 2B: Social Media Integration (P2)
   └─ Can be done with Qwen if Claude Pro expires

3. Phase 2C: Error Recovery (P3)
   └─ Polish after core features work

4. Phase 2D: Documentation (P3)
   └─ Final step before submission
```

**Critical Path**: Odoo MCP → fte-odoo-audit → fte-audit (CEO briefing) = minimum viable Gold Tier

**Optional Path**: Social media watcher → mcp-social-server → fte-social-post = nice to have if time permits

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/sp.plan command output)
├── research.md          # Phase 0 output (/sp.plan command)
├── data-model.md        # Phase 1 output (/sp.plan command)
├── quickstart.md        # Phase 1 output (/sp.plan command)
├── contracts/           # Phase 1 output (/sp.plan command)
└── tasks.md             # Phase 2 output (/sp.tasks command - NOT created by /sp.plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
# [REMOVE IF UNUSED] Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# [REMOVE IF UNUSED] Option 2: Web application (when "frontend" + "backend" detected)
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# [REMOVE IF UNUSED] Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure: feature modules, UI flows, platform tests]
```

**Structure Decision**: [Document the selected structure and reference the real
directories captured above]

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
