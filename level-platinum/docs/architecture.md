# Gold Tier — Architecture Document

**Project**: Personal AI Employee (Digital FTE)
**Tier**: Gold — Autonomous Business AI Employee
**Date**: 2026-03-09
**Branch**: `003-gold-tier`

---

## 1. System Overview

The Gold Tier is a **local-first autonomous AI employee** that monitors 7 data sources (Gmail, WhatsApp, LinkedIn, Facebook, Instagram, Twitter, filesystem), reasons about incoming items using Claude Code Agent Skills, and executes approved actions through 2 MCP servers and Playwright browser automation — all running on a Windows 11 machine without any cloud infrastructure.

### Core Design Philosophy

- **Local-first**: All data stays on the machine. No external cloud storage, no SaaS dependencies beyond API calls.
- **File-based communication**: Agents communicate through markdown files with YAML frontmatter in an Obsidian vault. The vault is the state bus.
- **Human-in-the-Loop**: Every sensitive action requires explicit human approval. The system can suggest, draft, and schedule — but never act unilaterally on high-risk operations.
- **Perception → Reasoning → Action**: Watchers perceive events, Claude reasons via skills, skills produce approved action files that execution engines process.

---

## 2. Component Architecture

### 2.1 Process Topology

```
Windows Machine
│
├── PM2 Process Manager
│   ├── gold-orchestrator (Python)          ← Main autonomy engine
│   │   ├── Thread: FilesystemWatcher       ← watchdog on Drop_Box/
│   │   ├── Thread: ApprovalWatcher         ← watchdog on Approved/ + Rejected/
│   │   ├── Thread: GmailWatcher            ← Gmail API polling every 2 min
│   │   ├── Thread: LinkedInWatcher         ← Playwright, 30-min interval
│   │   ├── Thread: FacebookWatcher         ← Playwright, 30-min interval
│   │   ├── Thread: InstagramWatcher        ← Playwright, 30-min interval
│   │   ├── Thread: TwitterWatcher          ← Playwright, 30-min interval
│   │   └── Heartbeat Loop (10s tick)
│   │       ├── scan_needs_action()         ← dispatch skills for new files
│   │       ├── check_approved()            ← route approvals to MCP or scheduler
│   │       ├── check_plans()               ← Ralph Wiggum: re-inject PLAN_*.md steps
│   │       ├── check_facebook_schedule()   ← fire Playwright post at jitter time
│   │       ├── check_instagram_schedule()  ← fire Playwright post at jitter time
│   │       ├── check_twitter_schedule()    ← fire Playwright post at jitter time
│   │       ├── check_linkedin_schedule()   ← fire Playwright post at jitter time
│   │       ├── odoo_health_check()         ← probe Odoo JSON-RPC every N ticks
│   │       └── update_dashboard()          ← write Dashboard.md atomically
│   │
│   └── whatsapp-watcher (Node.js)          ← Baileys WebSocket process
│       ├── client.on('message')            ← receive → WHATSAPP_*.md
│       └── chokidar on Approved/           ← APPROVAL_WA_*.md → sendMessage()
│
├── Windows Task Scheduler
│   ├── GoldFTE-GmailPoller    (every 2 min)   ← fallback if PM2 down
│   ├── GoldFTE-MorningBriefing (daily 08:00)  ← /fte-briefing
│   ├── GoldFTE-DailySocial    (daily 12:00)   ← /fte-social-post
│   ├── GoldFTE-WeeklyReview   (Sun 09:00)     ← /fte-linkedin-draft
│   └── GoldFTE-WeeklyAudit    (Sun 18:00)     ← /fte-audit (CEO briefing)
│
├── Docker
│   ├── gold-fte-odoo (Odoo 19 Community)
│   └── gold-fte-postgres (PostgreSQL 15)
│
└── Claude Code (claude CLI)
    ├── mcp-email-server (Node.js, stdio)    ← send/draft/search Gmail
    └── mcp-odoo-server (Node.js, stdio)     ← invoice/partner/finance
```

### 2.2 Vault as State Bus

The `AI_Employee_Vault/` directory is the single source of truth for all inter-component state:

```
AI_Employee_Vault/
├── Drop_Box/           ← INPUT: file drops trigger FilesystemWatcher
├── Needs_Action/       ← QUEUE: all incoming items waiting for skill dispatch
│   ├── EMAIL_*.md          (from GmailWatcher)
│   ├── WHATSAPP_*.md       (from whatsapp_watcher.js)
│   ├── LINKEDIN_NOTIF_*.md (from LinkedInWatcher)
│   ├── SOCIAL_FB_*.md      (from FacebookWatcher)
│   ├── SOCIAL_IG_*.md      (from InstagramWatcher)
│   ├── TWITTER_*.md        (from TwitterWatcher)
│   ├── FILE_*.md           (from FilesystemWatcher)
│   ├── ATTACHMENT_*.md     (from attachment_extractor.py)
│   └── PLAN_*.md / FOLLOWUP_*.md (from fte-plan skill)
├── Plans/              ← REASONING: AI-generated plans, drafts, briefings
│   ├── PLAN_*.md           (multi-step task plans with checkboxes)
│   ├── CEO_BRIEFING_*.md   (weekly CEO briefing)
│   ├── BRIEFING_*.md       (daily morning briefing)
│   └── LINKEDIN_DRAFT_*.md (social post drafts)
├── Pending_Approval/   ← HITL GATE: sensitive items awaiting human review
│   └── APPROVAL_*.md
├── Approved/           ← EXECUTION: human-approved items
│   └── APPROVAL_*.md       (orchestrator routes to MCP or scheduler)
├── Rejected/           ← CANCELLED: human-rejected items
├── Done/               ← COMPLETE: all processed items (purged after 24h)
├── Archive/            ← LONG-TERM: archived done items (kept indefinitely)
└── Logs/               ← AUDIT: JSON Lines daily logs
    └── YYYY-MM-DD.json
```

### 2.3 Action File Schema

Every item in the vault uses YAML frontmatter for structured communication:

```yaml
---
type: email_action | whatsapp_action | social_post | odoo_invoice | approval | plan
source: gmail | whatsapp | linkedin | facebook | instagram | twitter | filesystem
status: pending | approved | rejected | executed | expired
priority: urgent | high | medium | low
created_at: 2026-03-09T12:00:00Z
expires_at: 2026-03-16T12:00:00Z   # 7-day approval window
action: send_email | send_whatsapp | social_post | create_invoice | create_partner
platform: facebook | instagram | twitter   # for social_post type
approval_id: <uuid8>                # links approval to plan
---
```

---

## 3. Data Flow

### 3.1 Email → Odoo → Email (Cross-Domain Workflow)

```
1. Gmail inbox  →  GmailWatcher polls every 2 min
2.              →  EMAIL_<id>.md created in Needs_Action/
3. Orchestrator →  detects new file, dispatches /fte-gmail-triage
4. fte-gmail-triage → classifies as ROUTINE or SENSITIVE
5.              →  dispatches /fte-gmail-reply (reads FAQ_Context.md)
6. fte-gmail-reply  → detects client request (e.g. portfolio website)
7.              →  creates PLAN_*.md with multi-step workflow
8.              →  APPROVAL_email_holding.md in Pending_Approval/ (holding reply)
9. User approves → moves to Approved/
10. fte-approve  → mcp__email__send_email (holding reply sent)
11. fte-plan     → detects plan, creates Odoo partner via mcp__odoo__create_partner
12.              → creates APPROVAL_odoo_invoice.md in Pending_Approval/
13. User approves → moves to Approved/
14. fte-approve  → mcp__odoo__create_invoice (INV/2026/XXXXX created)
15.              → mcp__email__send_email (quote email with invoice details)
16. Done/        → all approval files archived
```

### 3.2 Social Post Autonomous Workflow

```
1. Task Scheduler → daily_social.bat → /fte-social-post facebook
2. fte-social-post → reads Business_Goals.md for context
3.               → drafts post content
4.               → writes APPROVAL_social_facebook_*.md to Pending_Approval/
5. User reviews  → moves to Approved/ in Obsidian
6. ApprovalWatcher → validates frontmatter (action: social_post, platform: facebook)
7. Orchestrator  → _handle_social_post_approval()
8.               → moves file to Done/ first (correct path reference)
9.               → FacebookScheduler.schedule(done_path, content)
10.              → jitter time selected within POST_WINDOW (09:00-18:00)
11.              → .state/facebook_scheduled.json written
12. Heartbeat    → check_facebook_schedule() fires when post_at time reached
13.              → post_to_facebook(content) called
14. Playwright   → opens Facebook session, browses feed, types char-by-char, submits
15.              → FacebookScheduler.record_post() + clear()
16. Logs         → facebook_post_success logged
```

### 3.3 Error Recovery Flow (Circuit Breaker)

```
Normal: orchestrator calls Odoo health check every N ticks
        → odoo_health_ok logged

Failure 1-2: odoo_health_error logged, failure_count incremented
Failure 3:   circuit_opened logged — state = OPEN
             → orchestrator skips all Odoo calls, logs odoo_health_degraded
             → briefing skill shows "⚠️ Odoo unavailable" gracefully

After 900s (15 min): circuit transitions to HALF_OPEN
             → one probe attempt allowed
             → circuit_half_open logged

Probe success: circuit_closed logged — state = CLOSED
             → odoo_health_ok resumes
             → Dashboard updated to show Odoo ✅
```

---

## 4. MCP Server Architecture

### Why MCP Over Direct API Calls

MCP (Model Context Protocol) gives Claude Code native tool-calling capability with:
- **HITL gates built-in**: Tools can check for approval file existence before executing writes
- **Stdio transport**: No network port needed — Claude spawns the server as a subprocess
- **Structured schemas**: Zod validation ensures correct parameters before any API call
- **DRY_RUN support**: All write tools respect `DRY_RUN=true` env var

### mcp-email-server

```
Claude Code  →  stdio  →  mcp-email-server/index.js
                               │
                    ┌──────────┼──────────┐
                    ▼          ▼          ▼
              send_email   draft_email  search_emails
                    │
              gmail_auth.js (shared OAuth2 client)
                    │
              Gmail API (googleapis)
```

**HITL gate in send_email**: Before calling Gmail API, checks that the approval file exists in `Approved/`. If missing (e.g. file was moved or expired), refuses to send.

### mcp-odoo-server

```
Claude Code  →  stdio  →  mcp-odoo-server/index.js
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼                ▼
  get_financial_summary  list_transactions  create_invoice  create_partner
              │
        odoo_auth.js (JSON-RPC bearer token)
              │
        Odoo 19 Community (Docker, http://localhost:8069)
              │
        PostgreSQL 15 (Docker)
```

**HITL gate in create_invoice/create_partner**: Checks approval file exists in `Approved/` before creating Odoo record.

---

## 5. Social Media Architecture

### Scheduler Pattern (All 4 Platforms)

All social platforms use the same JitterScheduler pattern:

```
State file: .state/{platform}_scheduled.json
Schema:
{
  "post_at": "14:37",        ← randomized within POST_WINDOW
  "post_date": "2026-03-09", ← today or next day if gap < 23h
  "file": "Done/APPROVAL_social_{platform}_*.md",  ← source reference
  "content": "...",          ← embedded at scheduling time (file path not re-read)
  "scheduled_at": "..."      ← when schedule was created
}
```

**23-hour gap enforcement**: `_random_post_time()` checks `last_posted.json` — if last post was less than 23h ago, schedules for tomorrow.

**Instagram media tracking**: `InstagramScheduler` additionally manages:
- `ig_used_media.json` — list of already-posted image filenames
- `get_next_media()` — picks next unused image from `media/` directory
- Auto-pause when all media exhausted

### Human Behavior Simulation

All Playwright posters implement:

| Behavior | Implementation |
|----------|---------------|
| Feed browsing | Random scroll 3–7 times before composing |
| Mouse overshoot | Click target ±5-15px with correction |
| Character typing | 60–130ms per character (randomized) |
| Proofread pause | 4–10 second pause before submitting |
| Session health check | URL check + login form detection before any action |

---

## 6. Ralph Wiggum Loop

Named after the Simpsons character who keeps repeating himself, this mechanism ensures multi-step plans complete even when Claude's session would normally end after one response.

**Implementation**:
1. `stop.py` hook intercepts Claude Code's exit event
2. Checks for active PLAN_*.md files with unchecked steps in `/Plans`
3. If found — re-injects the plan continuation prompt
4. Bypassed when `FTE_AUTOMATED_DISPATCH=1` env var is set (orchestrator-spawned subprocesses)
5. Bypassed for `/sp.phr` skill (prevents infinite PHR creation loop)

**Plan file format**:
```markdown
---
type: plan
status: in_progress  ← changes to complete when all steps checked
---
- [x] Step 1 — completed
- [ ] Step 2 — pending  ← Ralph re-injects when this is found
- [ ] Step 3 — pending
```

---

## 7. Security Architecture

### HITL Gate Pattern

Write operations (email send, Odoo invoice, social post) all go through the same approval gate:

```
Skill writes APPROVAL_*.md → Pending_Approval/
User reviews in Obsidian
User moves to Approved/ or Rejected/
Orchestrator dispatches fte-approve
fte-approve calls MCP tool → MCP checks Approved/ file exists → executes
File moves to Done/
```

If the approval file is missing when the MCP tool is called, the tool refuses with a clear error. This prevents replay attacks and ensures the human always has the last word.

### Secrets Management

- All secrets in `.env` (gitignored)
- Playwright sessions in `.secrets/` (gitignored)
- OAuth tokens in `.secrets/` (gitignored)
- No credentials in committed code — verified via grep in CI
- `DRY_RUN=true` for all testing — prevents accidental live sends

---

## 8. Observability

### Audit Log Schema

Every action logged as a JSON Line:

```json
{
  "timestamp": "2026-03-09T12:00:00+05:00",
  "action": "skill_dispatched",
  "actor": "Orchestrator",
  "source": "EMAIL_abc123.md",
  "destination": "",
  "result": "success",
  "details": "exit=0 | prompt='/fte-gmail-triage EMAIL_abc123.md'"
}
```

**Key action types**: `skill_dispatched`, `skill_timeout`, `approval_validated`, `approved_archived`, `facebook_post_success`, `circuit_opened`, `circuit_closed`, `odoo_health_ok`, `odoo_health_error`, `gmail_email_processed`

### Dashboard

`AI_Employee_Vault/Dashboard.md` updated atomically every 10 seconds showing:
- Status of all 7 watchers (Online/Offline)
- Odoo service health (✅ reachable / ⚠️ degraded)
- Count of pending approvals
- Scheduled social posts per platform
- Last activity timestamp

---

## 9. Technology Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Orchestration | orchestrator.py (Python, single process) | Simpler than multiple PM2 processes; threads share memory for circuit breaker state |
| WhatsApp | Baileys (Node.js WebSocket) | No browser CDP overhead; event-driven; stable LocalAuth session |
| Social media | Playwright (Python) | Native Python integration; persistent sessions; human simulation feasible |
| Accounting | Odoo 19 Community (Docker) | Self-hosted; JSON-RPC API; full accounting suite; free tier |
| MCP transport | stdio | No port management; Claude Code native; subprocess lifecycle managed by Claude |
| State format | Markdown + YAML frontmatter | Human-readable in Obsidian; parseable by Python; no database needed |
| Scheduling | JitterScheduler (custom) | Platform-agnostic; 23h gap enforcement; randomized to avoid bot detection patterns |
| Error recovery | CircuitBreaker (custom) | Prevents cascade failures; half-open recovery; fully logged |
| Process manager | PM2 | Auto-restart; log aggregation; Windows startup support; ecosystem config |
