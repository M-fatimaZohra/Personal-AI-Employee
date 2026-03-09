# Feature Specification: Gold Tier — Autonomous Business Employee

**Feature Branch**: `003-gold-tier`
**Created**: 2026-03-03
**Status**: Draft
**Input**: User description: "Gold Tier: Autonomous Employee with Odoo accounting, social media integration (Facebook, Instagram, Twitter), multiple MCP servers, weekly CEO briefing, error recovery, and comprehensive audit logging"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Business Financial Oversight (Priority: P1)

As a business owner, I need the AI Employee to track my business finances in real-time so I can make informed decisions without manually checking accounting software.

**Why this priority**: Financial visibility is the core differentiator between Silver (personal assistant) and Gold (business manager). Without accounting integration, the agent cannot provide business value.

**Independent Test**: Can be fully tested by setting up Odoo with sample invoices and expenses, then verifying the agent can read financial data and include it in briefings. Delivers immediate value by showing current revenue, outstanding invoices, and expense trends.

**Acceptance Scenarios**:

1. **Given** Odoo is running with 3 unpaid invoices totaling $8,200, **When** the morning briefing is generated, **Then** the briefing shows "Outstanding invoices: 3 clients, $8,200 total" with client names and due dates
2. **Given** a client payment of $2,500 was recorded in Odoo yesterday, **When** the morning briefing is generated, **Then** the briefing shows "Revenue received: $2,500 from Client X"
3. **Given** monthly expenses exceed the budget by 15%, **When** the weekly CEO briefing is generated, **Then** the briefing flags "Expenses over budget: $1,200 above target" with category breakdown
4. **Given** an invoice is 45 days overdue, **When** the agent triages daily tasks, **Then** the agent creates a draft follow-up email and marks it high priority

---

### User Story 2 - Social Media Presence Management (Priority: P2)

As a business owner, I need the AI Employee to monitor and manage my social media presence across Facebook, Instagram, and Twitter so I can maintain consistent engagement without manual posting.

**Why this priority**: Social media is important for business visibility but less critical than financial oversight. Can be implemented after accounting integration is stable.

**Independent Test**: Can be tested by connecting to test social media accounts, having the agent draft posts based on Business_Goals.md, and verifying posts appear on the platforms after approval. Delivers value by maintaining social presence with minimal manual effort.

**Acceptance Scenarios**:

1. **Given** a new comment appears on a Facebook business page post, **When** the social media watcher runs, **Then** a SOCIAL_FB_*.md file is created in /Needs_Action with the comment text and commenter name
2. **Given** Business_Goals.md specifies "promote new product launch", **When** the user runs /fte-social-post, **Then** the agent drafts platform-appropriate posts for Facebook, Instagram, and Twitter and writes them to /Pending_Approval
3. **Given** an approved social media post in /Approved, **When** the approval watcher processes it, **Then** the post appears on the target platform within 5 minutes and the approval file moves to /Done with status "posted"
4. **Given** the agent posted to Facebook, Instagram, and Twitter this week, **When** the weekly CEO briefing is generated, **Then** the briefing shows "Social media activity: 3 posts published, 47 engagements (likes/comments/shares)"

---

### User Story 3 - Weekly Business Performance Review (Priority: P1)

As a business owner, I need a comprehensive weekly briefing that combines financial performance, task completion, and proactive suggestions so I can plan the upcoming week strategically.

**Why this priority**: The CEO briefing is the signature feature of Gold Tier — it transforms the agent from reactive (handles incoming items) to proactive (analyzes patterns and suggests actions). Critical for demonstrating business value.

**Independent Test**: Can be tested by running the system for one week with sample data (emails, invoices, social posts, tasks), then triggering the weekly briefing and verifying it contains all required sections with accurate data. Delivers value by providing executive-level insights without manual report compilation.

**Acceptance Scenarios**:

1. **Given** the system has been running for 7 days, **When** the weekly CEO briefing is triggered on Sunday at 9 AM, **Then** a CEO_BRIEFING_*.md file is created in /Plans with sections for revenue, expenses, task completion, social media metrics, and proactive suggestions
2. **Given** 3 vendor emails have been unanswered for 2+ days, **When** the weekly briefing is generated, **Then** the briefing includes "Bottleneck: 3 vendor emails pending response for 2+ days" with a suggested action to prioritize them
3. **Given** a subscription service (e.g., Notion) has had no activity for 45 days and costs $15/month, **When** the weekly briefing is generated, **Then** the briefing includes "Cost optimization: Notion subscription unused for 45 days — consider canceling to save $180/year"
4. **Given** revenue increased 15% this week compared to last week, **When** the weekly briefing is generated, **Then** the briefing highlights "Win: Revenue up 15% week-over-week" and suggests a LinkedIn post to share the milestone

---

### User Story 4 - Multi-Domain Action Coordination (Priority: P2)

As a business owner, I need the AI Employee to coordinate actions across personal and business domains (email, accounting, social media) so complex workflows complete without manual intervention.

**Why this priority**: Demonstrates the "autonomous employee" capability — the agent can handle multi-step tasks that span multiple systems. Important for Gold Tier but can be implemented after core integrations are stable.

**Independent Test**: Can be tested by creating a scenario like "Client requests invoice → agent drafts invoice in Odoo → sends email with invoice attached → follows up if unpaid after 30 days" and verifying each step completes automatically with only one HITL approval. Delivers value by reducing manual coordination overhead.

**Acceptance Scenarios**:

1. **Given** a client emails requesting an invoice, **When** the agent triages the email, **Then** the agent creates a PLAN_*.md file with steps: [1] Draft invoice in Odoo, [2] Send invoice email, [3] Schedule 30-day follow-up
2. **Given** an invoice is created in Odoo, **When** the agent sends the invoice email, **Then** the email includes a link to the Odoo invoice PDF and the invoice is marked "sent" in Odoo
3. **Given** a client payment is recorded in Odoo, **When** the agent checks for pending follow-ups, **Then** the agent cancels any scheduled payment reminder emails for that client
4. **Given** a social media post receives 10+ comments, **When** the agent generates the weekly briefing, **Then** the briefing suggests "High engagement on [post topic] — consider creating a follow-up post or blog article"

---

### User Story 5 - System Resilience and Degraded Mode (Priority: P3)

As a business owner, I need the AI Employee to continue operating when external services are unavailable so critical workflows don't stop due to temporary outages.

**Why this priority**: Important for production reliability but lower priority than core features. Can be implemented after all integrations are working in the happy path.

**Independent Test**: Can be tested by simulating Odoo downtime (stop Docker container) and verifying the agent continues processing emails and social media while logging Odoo errors and marking the Dashboard as "Odoo: Degraded". Delivers value by ensuring the agent remains useful even when one integration fails.

**Acceptance Scenarios**:

1. **Given** Odoo is unreachable (Docker container stopped), **When** the morning briefing is generated, **Then** the briefing includes all sections except financial data and shows "⚠️ Odoo unavailable — financial data not included"
2. **Given** Facebook API returns 429 (rate limit), **When** the social media watcher runs, **Then** the watcher logs the error, waits 15 minutes (exponential backoff), and retries without crashing
3. **Given** the email MCP server fails 3 times in a row, **When** the orchestrator tries to send an approved email, **Then** the orchestrator marks the email as "manual_required" and writes a note to the Dashboard: "Email MCP unavailable — send manually"
4. **Given** the system has been in degraded mode for 2 hours, **When** the user checks the Dashboard, **Then** the Dashboard shows which services are degraded, when the issue started, and the last successful operation for each service

---

### Edge Cases

- What happens when Odoo is running but the database is empty (no invoices, no customers)? Agent should handle gracefully and report "No financial data available yet — add your first invoice in Odoo"
- How does the system handle social media posts that violate platform policies (e.g., too long, prohibited content)? Agent should detect common issues (character limits, prohibited words) before posting and flag for user review
- What happens when multiple MCP servers are down simultaneously? Agent should continue with available services and consolidate all degraded-mode warnings into a single Dashboard alert
- How does the agent handle conflicting priorities (urgent email arrives while processing a CEO briefing)? Orchestrator should interrupt low-priority tasks for urgent items and resume them later
- What happens when the user approves an action but the target system is unavailable at execution time? Approval watcher should retry with exponential backoff (3 attempts) then mark as "manual_required" if all attempts fail
- How does the system handle Odoo authentication failures (wrong credentials, expired session)? Agent should detect auth errors, log them clearly, and write a Dashboard alert: "Odoo authentication failed — check credentials in .env"

## Requirements *(mandatory)*

### Functional Requirements

**Odoo Accounting Integration**

- **FR-001**: System MUST integrate with Odoo Community Edition 19+ running locally via Docker on port 8069
- **FR-002**: System MUST authenticate with Odoo using JSON-RPC 2.0 protocol with database name, username, and API key from .env file
- **FR-003**: System MUST provide an MCP server (mcp-odoo-server) with tools: get_financial_summary, list_transactions, create_invoice, create_partner
- **FR-004**: System MUST enforce HITL approval for all Odoo write operations (create_invoice, create_partner) — read operations (get_financial_summary, list_transactions) are auto-allowed
- **FR-005**: System MUST handle Odoo connection failures gracefully by logging errors, marking Dashboard as "Odoo: Degraded", and continuing with other operations
- **FR-006**: System MUST include Odoo financial data in morning briefings: current month revenue, outstanding invoices (count and total), overdue invoices (count and total), top 3 expense categories
- **FR-007**: System MUST detect overdue invoices (30+ days past due date) and proactively suggest follow-up actions in the daily briefing

**Social Media Integration**

- **FR-008**: System MUST monitor Facebook business pages for new comments, mentions, and direct messages using Playwright browser automation
- **FR-009**: System MUST monitor Instagram business accounts for new comments and direct messages using Playwright browser automation
- **FR-010**: System MUST monitor Twitter/X accounts for mentions, direct messages, and keyword matches using Playwright browser automation
- **FR-011**: System MUST create action files (SOCIAL_FB_*.md, SOCIAL_IG_*.md, TWITTER_*.md) in /Needs_Action when new social media activity is detected
- **FR-012**: System MUST provide Python Playwright poster scripts (facebook_poster.py, instagram_poster.py, twitter_poster.py) for direct browser automation — NO MCP layer for posting
- **FR-013**: System MUST enforce HITL approval for all social media posts — no auto-posting without user review
- **FR-014**: System MUST draft platform-appropriate posts (character limits: Twitter 280, Instagram 2200, Facebook 63206) based on Business_Goals.md content
- **FR-015**: System MUST simulate human behavior when posting to social media using Python Playwright (random delays, character-by-character typing via _human_type(), mouse movements via _click_with_overshoot(), feed browsing) to avoid bot detection
- **FR-016**: System MUST track social media engagement metrics (posts published, likes, comments, shares) and include them in weekly CEO briefings

**Multiple MCP Servers**

- **FR-017**: System MUST support 2 concurrent MCP servers: mcp-email-server (existing), mcp-odoo-server (new) — social media uses direct Python Playwright execution
- **FR-018**: System MUST register all MCP servers in Claude Code settings with appropriate permissions and environment variables
- **FR-019**: System MUST isolate MCP server failures — if one server crashes, other servers continue operating
- **FR-020**: System MUST validate MCP server availability on orchestrator startup and log warnings for any unreachable servers

**Weekly CEO Briefing**

- **FR-021**: System MUST generate a comprehensive CEO briefing every Sunday at 9 AM via Task Scheduler
- **FR-022**: CEO briefing MUST include sections: Week at a Glance (metrics summary), Goal Progress (from Business_Goals.md), Wins This Week (completed tasks), Bottlenecks (delayed items), Proactive Suggestions (cost optimization, follow-ups, opportunities)
- **FR-023**: CEO briefing MUST pull data from: Odoo (revenue, expenses, invoices), Logs (actions executed, errors), Done folder (completed tasks), Business_Goals.md (targets vs actuals), social media metrics (posts, engagement)
- **FR-024**: CEO briefing MUST detect patterns and suggest actions: unused subscriptions (no activity 30+ days), unanswered emails (2+ days old), overdue invoices (30+ days), high-engagement social posts (suggest follow-up content)
- **FR-025**: CEO briefing MUST be written to /Plans/CEO_BRIEFING_YYYY-MM-DD.md with status "unread" and trigger a Dashboard notification

**Error Recovery and Graceful Degradation**

- **FR-026**: System MUST implement circuit breaker pattern for all external service calls (Odoo, social media, MCP servers) — after 3 consecutive failures, mark service as degraded and skip for 15 minutes
- **FR-027**: System MUST retry failed operations with exponential backoff: 2s, 4s, 8s delays with max 3 attempts before marking as failed
- **FR-028**: System MUST continue operating when one or more services are degraded — only skip operations that depend on the unavailable service
- **FR-029**: System MUST report degraded services in Dashboard with: service name, failure reason, time of first failure, last retry attempt
- **FR-030**: System MUST automatically recover from degraded mode when the service becomes available again (circuit breaker resets after successful call)

**Comprehensive Audit Logging**

- **FR-031**: System MUST log all actions to daily JSON Lines files (YYYY-MM-DD.json) with fields: timestamp, action, actor, source, destination, result, details, approval_status, approved_by, parameters
- **FR-032**: System MUST enforce 90-day log retention policy — logs older than 90 days are automatically archived to /Logs/Archive/
- **FR-033**: System MUST log MCP tool calls with full parameters (sanitized — no passwords or API keys in logs)
- **FR-034**: System MUST log all approval decisions: file name, decision (approved/rejected), decision timestamp, user who moved the file
- **FR-035**: System MUST provide a log query tool (fte-logs skill) that can search logs by date range, action type, actor, or result

**Ralph Wiggum Loop (Multi-Step Task Completion)**

- **FR-036**: System MUST use the existing Ralph Wiggum stop hook (.claude/hooks/stop.py) to automatically continue multi-step tasks until completion
- **FR-037**: System MUST detect active Plan files with unchecked steps and re-inject continuation prompts when Claude attempts to exit
- **FR-038**: System MUST limit Ralph Wiggum re-injections to 5 per plan to prevent infinite loops
- **FR-039**: System MUST bypass Ralph Wiggum re-injection for automated orchestrator dispatches (FTE_AUTOMATED_DISPATCH=1 env var) to prevent timeout loops

**Agent Skills Architecture**

- **FR-040**: System MUST implement all new Gold Tier functionality as Agent Skills in .claude/skills/ directory
- **FR-041**: System MUST create new skills: fte-audit (CEO briefing), fte-social-post (draft social posts), fte-social-summary (engagement metrics), fte-odoo-audit (financial queries)
- **FR-042**: System MUST update existing skills: fte-approve (handle odoo_action and social_post types), fte-briefing (include Odoo balance), fte-triage (route SOCIAL_* and TWITTER_* files)
- **FR-043**: System MUST document each skill with: name, description, argument-hint, allowed-tools, disable-model-invocation flag, user-invocable flag

**Documentation**

- **FR-044**: System MUST provide architecture documentation in /docs/architecture.md covering: system overview, component diagram, data flow, MCP server architecture, skill routing table, approval pipeline
- **FR-045**: System MUST provide lessons learned documentation in /docs/lessons-learned.md covering: what worked well, what didn't work, key decisions, trade-offs, recommendations for future tiers
- **FR-046**: System MUST provide Odoo setup guide in /docs/odoo-setup.md with: Docker Compose installation, initial configuration, test data population, MCP server connection testing
- **FR-047**: System MUST provide social media setup guide in /docs/social-media-setup.md with: Playwright session creation, platform-specific authentication, test account recommendations, rate limit handling

### Key Entities

- **Financial Transaction**: Represents a business transaction in Odoo (invoice, payment, expense). Attributes: transaction_id, type (invoice/payment/expense), amount, currency, date, customer/vendor, status (draft/sent/paid/overdue), due_date
- **Social Media Post**: Represents a post to be published on social platforms. Attributes: post_id, platform (facebook/instagram/twitter), content, scheduled_time, status (draft/pending_approval/scheduled/posted), engagement_metrics (likes, comments, shares)
- **CEO Briefing**: Represents a weekly executive summary. Attributes: briefing_date, week_number, revenue_summary, expense_summary, task_completion_rate, bottlenecks, proactive_suggestions, social_media_metrics
- **Service Health Status**: Represents the operational status of an external service. Attributes: service_name (odoo/facebook/instagram/twitter/email_mcp), status (online/degraded/offline), last_success_time, failure_count, circuit_breaker_state (closed/open/half_open)
- **Approval Record**: Represents a user decision on a pending action. Attributes: approval_file, action_type, decision (approved/rejected), decision_time, approved_by, execution_result, execution_time

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: User can view current month revenue and outstanding invoices in the morning briefing without opening Odoo
- **SC-002**: User receives a comprehensive weekly CEO briefing every Sunday at 9 AM with financial performance, task completion, and proactive suggestions
- **SC-003**: User can draft and publish social media posts to Facebook, Instagram, and Twitter with a single approval action
- **SC-004**: System continues processing emails and social media when Odoo is unavailable, with clear degraded-mode indicators in Dashboard
- **SC-005**: System automatically retries failed operations up to 3 times before requiring manual intervention
- **SC-006**: User can search 90 days of audit logs to find any action, approval decision, or error by date, actor, or action type
- **SC-007**: Multi-step tasks (e.g., "draft invoice → send email → schedule follow-up") complete automatically with only one user approval
- **SC-008**: System detects and flags unused subscriptions, overdue invoices, and unanswered emails in weekly briefings without manual review
- **SC-009**: All 2 MCP servers (email, odoo) operate concurrently without conflicts; social media posting uses direct Python Playwright execution
- **SC-010**: Social media posts simulate human behavior (typing delays, mouse movements) to avoid platform bot detection
