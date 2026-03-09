# Data Model: Gold Tier Entities

**Feature**: 003-gold-tier
**Date**: 2026-03-03

---

## Entity: Financial Transaction

**Source**: Odoo `account.move` model

**Purpose**: Represents business transactions (invoices, payments, expenses) tracked in Odoo accounting system

**Fields**:
- `transaction_id` (int): Odoo record ID
- `type` (enum): Transaction type
  - Values: `invoice`, `payment`, `expense`
  - Odoo mapping: `move_type` ('out_invoice', 'in_invoice', 'out_payment', 'in_payment')
- `amount` (decimal): Transaction amount in base currency
- `currency` (string): Currency code (e.g., 'USD', 'EUR')
- `date` (ISO date): Transaction date
- `customer_vendor` (string): Partner name (customer for invoices, vendor for bills)
- `status` (enum): Transaction status
  - Values: `draft`, `sent`, `paid`, `overdue`
  - Odoo mapping: `state` + `payment_state`
- `due_date` (ISO date): Payment due date (invoices only)

**Relationships**:
- Many-to-one: Transaction → Customer/Vendor (res.partner)
- One-to-many: Invoice → Payment records

**State Transitions**:
```
draft → sent → paid
              ↓
           overdue (if past due_date and not paid)
```

**Validation Rules**:
- `amount` > 0
- `due_date` >= `date` (for invoices)
- `status` must be in allowed values
- `type` = 'invoice' requires `due_date`

**Usage in Gold Tier**:
- Morning briefing: Show outstanding invoices count and total
- CEO briefing: Calculate revenue (paid invoices), expenses (paid bills), overdue amounts
- Proactive suggestions: Flag invoices overdue > 30 days

---

## Entity: Social Media Post

**Source**: File-based (SOCIAL_FB_*.md, SOCIAL_IG_*.md, TWITTER_*.md)

**Purpose**: Represents a post to be published on social media platforms

**Fields**:
- `post_id` (string): Unique identifier (filename stem)
- `platform` (enum): Target platform
  - Values: `facebook`, `instagram`, `twitter`
- `content` (string): Post text content
- `scheduled_time` (ISO datetime): When to post (optional, for scheduled posts)
- `status` (enum): Post lifecycle status
  - Values: `draft`, `pending_approval`, `scheduled`, `posted`, `failed`
- `engagement_metrics` (object): Post performance data
  - `likes` (int): Number of likes/reactions
  - `comments` (int): Number of comments
  - `shares` (int): Number of shares/retweets

**Relationships**:
- None (standalone posts)

**State Transitions**:
```
draft → pending_approval → scheduled → posted
                                      ↓
                                   failed (retry or manual)
```

**Validation Rules**:
- `content` length per platform:
  - Twitter: max 280 characters
  - Instagram: max 2200 characters
  - Facebook: max 63206 characters
- `scheduled_time` must be in future (if provided)
- `platform` must be in allowed values
- `status` must be in allowed values

**Usage in Gold Tier**:
- fte-social-post skill: Draft posts based on Business_Goals.md
- Approval pipeline: Write to /Pending_Approval for HITL review
- mcp-social-server: Execute post after approval
- CEO briefing: Aggregate engagement metrics for weekly summary

---

## Entity: CEO Briefing

**Source**: Generated file (CEO_BRIEFING_YYYY-MM-DD.md in /Plans)

**Purpose**: Weekly executive summary combining financial, operational, and strategic insights

**Fields**:
- `briefing_date` (ISO date): Sunday date of the briefing
- `week_number` (int): ISO week number (1-53)
- `revenue_summary` (object): Financial performance
  - `total_revenue` (decimal): Sum of paid invoices this week
  - `outstanding_invoices` (int): Count of unpaid invoices
  - `outstanding_amount` (decimal): Total unpaid amount
  - `overdue_invoices` (int): Count of overdue invoices
  - `overdue_amount` (decimal): Total overdue amount
- `expense_summary` (object): Spending analysis
  - `total_expenses` (decimal): Sum of paid bills this week
  - `top_categories` (array): Top 3 expense categories with amounts
  - `budget_variance` (decimal): Difference from expected budget
- `task_completion_rate` (float): Percentage of tasks completed (Done folder / total tasks)
- `bottlenecks` (array): Delayed or stuck items
  - Each item: `{task, expected_days, actual_days, delay_days}`
- `proactive_suggestions` (array): AI-generated action items
  - Each item: `{category, suggestion, potential_savings, priority}`
- `social_media_metrics` (object): Engagement summary
  - `posts_published` (int): Posts this week
  - `total_likes` (int): Sum of likes across platforms
  - `total_comments` (int): Sum of comments
  - `total_shares` (int): Sum of shares

**Relationships**:
- References: Odoo transactions (via API queries)
- References: Log entries (via file reads)
- References: Done folder files (via file counts)
- References: Business_Goals.md (for target comparison)

**State Transitions**:
- None (generated once per week, status: `unread` → `read` by user)

**Validation Rules**:
- `briefing_date` must be a Sunday
- `week_number` must match ISO week of `briefing_date`
- `task_completion_rate` must be 0.0-1.0
- All monetary amounts must be >= 0

**Usage in Gold Tier**:
- fte-audit skill: Generate every Sunday at 9 AM
- Orchestrator: Trigger via Task Scheduler
- Dashboard: Show notification when new briefing is ready

---

## Entity: Service Health Status

**Source**: Runtime state (not persisted to disk, tracked in orchestrator memory)

**Purpose**: Tracks operational status of external services for graceful degradation

**Fields**:
- `service_name` (string): Service identifier
  - Values: `odoo`, `facebook`, `instagram`, `twitter`, `email_mcp`, `social_mcp`, `odoo_mcp`
- `status` (enum): Current operational status
  - Values: `online`, `degraded`, `offline`
- `last_success_time` (ISO datetime): Last successful operation
- `failure_count` (int): Consecutive failures since last success
- `circuit_breaker_state` (enum): Circuit breaker state
  - Values: `closed`, `open`, `half_open`
- `last_error` (string): Most recent error message (for debugging)

**Relationships**:
- None (runtime state only)

**State Transitions**:
```
Circuit Breaker States:
closed → open (after 3 failures)
open → half_open (after 15 min timeout)
half_open → closed (on success)
half_open → open (on failure)

Service Status:
online → degraded (circuit opens)
degraded → online (circuit closes)
degraded → offline (manual intervention required)
```

**Validation Rules**:
- `failure_count` >= 0
- `circuit_breaker_state` must be in allowed values
- `status` must be in allowed values
- `last_success_time` must be <= current time

**Usage in Gold Tier**:
- Orchestrator: Track health of all services
- Dashboard: Display degraded services with failure reason
- Circuit breaker: Prevent cascading failures
- Logging: Record state transitions for audit trail

---

## Entity Relationships Diagram

```
┌─────────────────────────┐
│  Financial Transaction  │
│  (Odoo account.move)    │
│  - transaction_id       │
│  - type                 │
│  - amount               │
│  - status               │
└───────────┬─────────────┘
            │
            │ referenced by
            ↓
┌─────────────────────────┐
│     CEO Briefing        │
│  - briefing_date        │
│  - revenue_summary      │◄─────┐
│  - expense_summary      │      │
│  - bottlenecks          │      │ referenced by
│  - proactive_suggestions│      │
└─────────────────────────┘      │
            ▲                     │
            │ referenced by       │
            │                     │
┌─────────────────────────┐      │
│   Social Media Post     │──────┘
│  - post_id              │
│  - platform             │
│  - content              │
│  - engagement_metrics   │
└─────────────────────────┘

┌─────────────────────────┐
│  Service Health Status  │
│  (runtime only)         │
│  - service_name         │
│  - status               │
│  - circuit_breaker_state│
└─────────────────────────┘
```

---

## Storage Strategy

| Entity | Storage | Persistence | Access Pattern |
|---|---|---|---|
| Financial Transaction | Odoo PostgreSQL | Permanent | Read via JSON-RPC API |
| Social Media Post | Markdown files | Permanent (audit trail) | File I/O, move between folders |
| CEO Briefing | Markdown file | Permanent (weekly archive) | File write (generate), file read (user) |
| Service Health Status | Python dict (memory) | Transient (lost on restart) | In-memory read/write |

---

## Data Flow

**Financial Data Flow**:
```
Odoo PostgreSQL → JSON-RPC API → mcp-odoo-server → fte-odoo-audit skill → Morning Briefing
                                                   → fte-audit skill → CEO Briefing
```

**Social Media Data Flow**:
```
User/fte-social-post → SOCIAL_*.md (/Pending_Approval) → User approval → /Approved
→ mcp-social-server → Playwright → Platform API → Posted
→ Engagement metrics → get_social_summary → CEO Briefing
```

**Service Health Data Flow**:
```
Orchestrator → Service call → Success/Failure → Update health status → Dashboard
                            → Circuit breaker state machine → Log state change
```
