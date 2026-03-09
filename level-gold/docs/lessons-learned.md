# Gold Tier — Lessons Learned

**Project**: Personal AI Employee (Digital FTE)
**Tier**: Gold — Autonomous Business AI Employee
**Date**: 2026-03-09
**Branch**: `003-gold-tier`

---

## 1. Architecture Lessons

### 1.1 Vault as State Bus: Simpler Than It Sounds

The decision to route all inter-component state through markdown files in the vault turned out to be one of the best architectural decisions of the project. Every component (watchers, orchestrator, Claude skills, MCP servers) communicates through the same lingua franca: YAML frontmatter + markdown body.

**What worked**: Human-readable state means debugging is trivial — open Obsidian, see exactly what's in the queue. No separate database to query.

**What surprised us**: YAML frontmatter parsing required careful handling of multi-line strings and quote escaping. The `python-frontmatter` library handled this cleanly; rolling our own parser would have been a mistake.

**Lesson**: File-based state is underrated for autonomous agents. It naturally provides audit trails, human visibility, and crash recovery (files persist across restarts).

---

### 1.2 The HITL Gate Is a Feature, Not a Constraint

Early instinct was to minimize HITL (Human-in-the-Loop) friction. Lived experience reversed this.

**What we learned**: The approval gate in Obsidian — moving a file from `Pending_Approval/` to `Approved/` — took 2-3 seconds per action. That's negligible for high-stakes operations (invoice creation, client emails, social posts). The gate provided:
- Confidence to let the system run autonomously for low-risk actions
- A natural audit trail (every approval is a timestamped file move)
- A "kill switch" pattern: stop PM2 or just don't approve anything

**Lesson**: Design HITL gates to be low-friction, not absent. Obsidian file drag-and-drop is the right UX for this.

---

### 1.3 PM2 Threads vs. Processes

All 7 watchers run as threads inside a single `gold-orchestrator` Python process, rather than as separate PM2 processes. This was deliberate.

**Why threads worked**: The circuit breaker state (CLOSED/OPEN/HALF_OPEN) for Odoo is shared memory across all threads. Separate processes would require IPC (sockets or files) to share this state. Thread-local state for a single-machine agent is the right tradeoff.

**What we'd do differently**: The orchestrator's 10-second heartbeat tick runs in the main thread while watcher threads poll independently. This created a subtle bug during early development — the heartbeat's `scan_needs_action()` was occasionally double-dispatching items that a watcher thread had just created. Fixed by adding dispatch flag files in `.state/`.

**Lesson**: Thread-based architecture reduces IPC complexity but requires careful flag-file deduplication for cross-thread state.

---

## 2. Integration Lessons

### 2.1 MCP Stdio Transport: Elegant But Finicky

The choice of stdio transport for MCP servers meant no port management and no network surface area. Claude Code spawns the server as a subprocess and communicates via stdin/stdout.

**What worked**: Zero configuration — no nginx, no firewall rules, no port conflicts. The MCP server starts fresh on each Claude Code session.

**What was painful**: Debugging MCP servers required running them standalone (`node mcp-email-server/index.js`) and sending JSON-RPC payloads via stdin. There's no GUI debugger for stdio transport. Adding `console.error()` logging (stderr, not stdout) was the only way to trace execution.

**Lesson**: For stdio MCP servers, log to stderr aggressively. stdout is sacred — a single stray `console.log()` corrupts the JSON-RPC framing and silently breaks all tool calls.

---

### 2.2 Odoo JSON-RPC: Simpler Than Expected

Initial concern was that Odoo's API would require complex authentication flows or unstable endpoints. Reality was straightforward.

**What worked**: Odoo's JSON-RPC API is stable and well-documented. Bearer token auth via API key (generated in Odoo UI) is simple. The `xmlrpc.client` Python library works too, but JSON-RPC from Node.js was cleaner for the MCP server pattern.

**What tripped us**: Odoo field names are snake_case internally but the API documentation shows camelCase examples for some endpoints. Always verify with a raw `read` call first.

**Lesson**: Test Odoo API calls with curl before writing code. The JSON-RPC spec is consistent; the field name conventions are not.

---

### 2.3 Playwright Social Sessions: Fragile by Design

Playwright browser sessions for social platforms (Facebook, Instagram, Twitter, LinkedIn) are inherently fragile — platforms actively try to detect and invalidate bot sessions.

**What worked**: Persistent session directories (`.secrets/platform_session/`) allow the browser to resume with existing cookies. Once authenticated, sessions typically lasted days without needing re-login.

**What was painful**:
- Sessions expired silently — the watcher would launch, navigate, and land on a login page without error
- Each platform has different login detection patterns
- Instagram's session was the most fragile; Facebook's was the most stable

**Lesson**: Always implement session health checks. Before any automated action, check `document.title` or look for login form presence. Log `session_expired` and stop immediately rather than proceeding — the alternative is typing into a login form, which triggers immediate account suspension.

---

### 2.4 Social Post Routing Bug (Critical Lesson)

The most impactful bug of the Gold tier: social post approvals were being routed to `fte-approve`, which dispatched a Claude Code subprocess. That subprocess timed out after 300 seconds because `fte-approve` had no logic for `action: social_post`.

**Root cause**: The approval routing in `orchestrator.py` was binary — either route to fte-approve or do nothing. Social posts needed a third path: route directly to the JitterScheduler.

**Fix**: Added `_handle_social_post_approval()` in the orchestrator's `check_approved()` method. This checks the frontmatter `action` field before dispatching any subprocess.

**Lesson**: Approval routing is a dispatch table, not a binary branch. New action types need explicit routing entries. The pattern to follow: `check_approved()` → read frontmatter → route by `action` type → fallback to fte-approve for unknown types.

---

### 2.5 Scheduler File Path Bug

After adding `_handle_social_post_approval()`, a subtle bug remained: `FacebookScheduler.schedule(filepath, content)` was called with the original `filepath` (still pointing to `Approved/`) before the file rename to `Done/`.

**Symptom**: `.state/facebook_scheduled.json` contained the `Approved/` path. When the heartbeat fired at post time, it passed a stale path to `post_to_facebook()`. The post still worked because `content` was embedded in the JSON (not re-read from the file), but the reference was wrong.

**Fix**: Always move to Done/ first, then pass `dest` (the Done/ path) to the scheduler.

**Lesson**: In workflows where a file is renamed/moved before being scheduled, always capture the final destination path before passing it to downstream components. Logging `dest` at schedule time confirmed the fix.

---

## 3. Development Workflow Lessons

### 3.1 DRY_RUN Is Mandatory

Every external action (email send, Odoo invoice, social post, file move to Done/) respects `DRY_RUN=true`. This was a Bronze-tier decision that paid dividends at Gold tier.

**What it enabled**: Testing the full pipeline — orchestrator heartbeat, skill dispatch, MCP tool calls, scheduler creation — without any live consequences. Caught 3 bugs in the first Gold-tier test run before anything went live.

**Lesson**: Implement DRY_RUN before implementing the actual action. It's an architectural concern, not an afterthought.

---

### 3.2 Circuit Breaker: Test the Full Lifecycle, Not Just the Open State

Most circuit breaker implementations are tested when they open. The recovery path (OPEN → HALF_OPEN → CLOSED) is often untested.

**What we tested**: Stopped Docker Odoo → verified `circuit_opened` logged after 3 failures → waited 15 minutes → verified `circuit_half_open` probe → started Odoo → verified `circuit_closed` and `odoo_health_ok` resumed.

**What we found**: The briefing skill correctly showed "⚠️ Odoo unavailable" during OPEN state and resumed normal operation after CLOSED. The Dashboard updated correctly across all state transitions.

**Lesson**: Test OPEN → HALF_OPEN → CLOSED as a single lifecycle test, not three separate tests. The transitions depend on each other.

---

### 3.3 The 300-Second Skill Timeout

The orchestrator dispatches skills via `subprocess.run(["claude", "--print", f"/{skill} {file}"])` with a 300-second timeout. This is generous for most skills (triage, reply drafting typically complete in 30-60 seconds).

**What we learned**: Skills that attempt external API calls (Odoo, social platforms) can approach this limit under network latency. The social post routing bug caused timeouts because fte-approve was waiting for Claude to figure out an unsupported action type.

**Lesson**: Skills should fail fast on unsupported inputs with a clear error message, not hang waiting for Claude to reason through an impossible scenario.

---

### 3.4 WhatsApp Baileys vs. whatsapp-web.js

Initial Silver-tier design used `whatsapp-web.js`. Gold tier continued with this. The Node.js process is event-driven and handles both receive and send in a single process.

**What worked**: LocalAuth session (``.secrets/whatsapp_session/``) persists across restarts. PM2 auto-restart preserves the session as long as SIGINT graceful shutdown is implemented.

**Critical**: Without `process.on('SIGINT', async () => { await client.destroy(); })`, PM2 force-kills the process and corrupts the session files. Recovery requires deleting `.secrets/whatsapp_session/` and scanning QR again.

**Lesson**: Any process managing a persistent browser session MUST handle SIGINT gracefully. Document this prominently in the README.

---

## 4. Operational Lessons

### 4.1 Dashboard.md as System Health Snapshot

The 10-second heartbeat update to Dashboard.md was more valuable than expected. Obsidian's live preview shows system state without opening any terminals.

**What the dashboard revealed in practice**:
- A watcher thread crashing (status goes Offline) before PM2 logs showed anything
- Pending approvals accumulating while user was offline (count rose to 8 during one session)
- Facebook scheduled post appearing 30 seconds after approval — confirmed routing was working

**Lesson**: A human-readable status page (even a markdown file) is worth the 10-second update cost. It's the first place to look when something seems wrong.

---

### 4.2 Logs as Debugging Infrastructure

The JSON Lines audit logs in `AI_Employee_Vault/Logs/YYYY-MM-DD.json` were used daily during development, not just for compliance.

**Patterns we searched for**:
- `jq 'select(.action == "circuit_opened")' Logs/2026-03-09.json` — confirm circuit breaker test
- `jq 'select(.result == "error")' Logs/2026-03-09.json` — surface all errors in one view
- `jq 'select(.source | startswith("EMAIL_"))' Logs/2026-03-09.json` — trace one email through the pipeline

**Lesson**: Design logs to be queryable from day one. JSON Lines + `jq` is sufficient for a single-machine agent. No need for ELK or similar.

---

### 4.3 23-Hour Post Gap: Right Call

The JitterScheduler enforces a 23-hour minimum gap between posts per platform. Initially this seemed overly conservative.

**Why it mattered**: Two social posts in quick succession (e.g., from a development test and a live approval) would look spammy and potentially trigger platform rate limiting. The 23-hour gap enforces human-pace posting even in automated workflows.

**Lesson**: Social automation rules should be conservative by default. Changing 23h to 12h is a one-line config change; recovering from an account suspension is not.

---

## 5. What We'd Do Differently

### 5.1 Spec Social Post Routing Before Building

The routing bug (`check_approved()` not handling `action: social_post`) would have been caught by a spec review. The spec said "route approvals to MCP or scheduler" but didn't specify the dispatch table explicitly.

**Fix for next time**: For each approval action type, explicitly define the routing in the spec: `email_action → mcp__email__send_email`, `odoo_invoice → mcp__odoo__create_invoice`, `social_post → JitterScheduler`.

### 5.2 Integration Tests for Scheduler

The scheduler unit tests (`T-SCHED-001` through `T-SCHED-003`) verified JSON creation but not the end-to-end fire time. An integration test that:
1. Creates a test approval
2. Sets the scheduled time to T+30 seconds
3. Verifies `post_to_{platform}()` is called at T+30s

...would have caught the file path bug immediately.

### 5.3 Consolidate WhatsApp Node.js Process Into Python

The mixed-language architecture (Python orchestrator + Node.js WhatsApp watcher) added coordination complexity. PM2 manages both, but the two processes don't share state except through the vault.

In a future version: consider a Python WhatsApp library (e.g., `py-baileys` or a REST bridge) to eliminate the Node.js process and simplify the architecture to pure Python.

### 5.4 Twitter Watcher: Build It Alongside Facebook

The Twitter watcher was architected alongside Facebook but deferred for implementation. This left a gap in the test matrix. The pattern (Playwright + persistent session + JitterScheduler) is identical to Facebook — building them in parallel would have cost minimal extra effort.

---

## 6. What Worked Better Than Expected

1. **Ralph Wiggum Loop**: Multi-step plans completing autonomously across Claude Code session boundaries was a major capability unlock. The stop.py hook was simple (< 50 lines) but powerful.

2. **YAML Frontmatter as Action Schema**: Using YAML frontmatter for action type, platform, approval ID, and status gave a structured schema without a database. Python's `python-frontmatter` library parsed it cleanly.

3. **Odoo via Docker**: Standing up a full accounting system locally in 3 commands (`docker compose up -d`, browser setup, API key generation) took 15 minutes. Running MCP tools against it felt like interacting with an enterprise system without enterprise complexity.

4. **MCP HITL Gate**: The check that the approval file must exist in `Approved/` before the MCP tool executes prevented a class of bugs where an approval file was approved, moved, then a replay or retry attempted to re-execute. The gate refused cleanly with an error.

5. **CircuitBreaker Implementation**: The 3-state machine (CLOSED → OPEN → HALF_OPEN → CLOSED) with a 900-second reset timer was straightforward to implement and test. Graceful degradation in briefings ("⚠️ Odoo unavailable") was exactly the behavior needed.

---

## 7. Gold Tier Completion Summary

| Category | Result |
|----------|--------|
| Requirements met | 12/12 ✅ |
| Skills built | 15 ✅ |
| MCP servers | 2 ✅ |
| Social platforms | 4 (FB, IG, TW, LI) ✅ |
| End-to-end tests | Email→Odoo→Email ✅, Facebook autonomous ✅, Circuit breaker lifecycle ✅ |
| Documentation | architecture.md, lessons-learned.md, QUICKSTART.md, SECURITY.md, README.md ✅ |
| Audit logging | JSON Lines, daily rotation, queryable ✅ |
| Known gaps | Twitter/Instagram autonomous scheduling not yet tested under PM2; T-SCHED-004 through T-SCHED-007 untested |
