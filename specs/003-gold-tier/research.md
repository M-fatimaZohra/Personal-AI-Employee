# Research: Gold Tier Implementation

**Feature**: 003-gold-tier
**Date**: 2026-03-03
**Researcher**: Claude Sonnet 4.6

---

## Research Questions

### R1: Odoo JSON-RPC 2.0 API
**Question**: How to authenticate and call Odoo 19 methods via JSON-RPC?

**Decision**: Use Odoo JSON-2 API with bearer token authentication (API key)

**Rationale**:
- Modern API (introduced in Odoo 19)
- Simpler than XML-RPC (no SOAP overhead)
- API key authentication (no password in requests)
- RESTful-style endpoints: `/json/2/{model}/{method}`
- Better error messages with traceback

**Implementation**:
```javascript
// Authentication: Use API key in Authorization header
const response = await fetch('http://localhost:8069/json/2/account.move/search_read', {
  method: 'POST',
  headers: {
    'Authorization': `bearer ${ODOO_API_KEY}`,
    'X-Odoo-Database': ODOO_DB,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    context: { lang: 'en_US' },
    domain: [['move_type', '=', 'out_invoice']],
    fields: ['name', 'partner_id', 'amount_total', 'invoice_date_due', 'payment_state']
  })
});
```

**Key Models**:
- `account.move`: Invoices (move_type='out_invoice'), bills (move_type='in_invoice')
- `res.partner`: Customers and vendors
- `account.payment`: Payment records

**Alternatives Considered**:
- XML-RPC: More verbose, older protocol
- Odoo Python library: Adds dependency, overkill for simple queries

---

### R2: Playwright Social Media Automation
**Question**: How to post to Facebook/Instagram/Twitter with Playwright without triggering bot detection?

**Decision**: Use persistent browser contexts + human behavior simulation (typing delays, mouse movements, feed browsing)

**Rationale**:
- Persistent contexts save login sessions (no re-auth every time)
- `storage_state()` includes cookies, localStorage, IndexedDB
- Human simulation patterns reduce bot detection risk
- Character-by-character typing with random delays (60-130ms)
- Mouse movements with curved paths and wobble
- Pre-post activities (browse feed, scroll, pause)

**Implementation**:
```python
# Save session after first login
await context.storage_state(path='.secrets/facebook_session/state.json', indexed_db=True)

# Reuse session later
context = await browser.new_context(storage_state='.secrets/facebook_session/state.json')

# Human typing simulation
await page.locator('#post-content').press_sequentially(
    'This is my post!',
    delay=random.randint(60, 130)  # Random delay per character
)

# Proofread pause before posting
await page.wait_for_timeout(random.randint(4000, 10000))
```

**Anti-Bot Checklist**:
1. Browse feed before posting (2-5 seconds)
2. Scroll randomly (1-3 times)
3. Type character-by-character with delays
4. Pause to "proofread" (4-10 seconds)
5. Move mouse naturally (curved path, not straight line)
6. Use burner accounts for testing first

**Alternatives Considered**:
- Official APIs: Twitter API v2 costs $100/mo, Meta Graph API requires Business account setup
- Selenium: Older, more detectable than Playwright
- Puppeteer: Similar to Playwright but less cross-browser support

---

### R3: Circuit Breaker Pattern in Python
**Question**: How to implement circuit breaker (closed/open/half_open) with exponential backoff?

**Decision**: Enhance existing `backoff.py` with state machine (closed → open → half_open → closed)

**Rationale**:
- Prevents cascading failures when Odoo/social media services are down
- 3 consecutive failures → open circuit (stop trying)
- 15-minute timeout → half_open (try once)
- Success in half_open → closed (resume normal operation)
- Failure in half_open → open again

**Implementation**:
```python
class CircuitBreaker:
    def __init__(self, failure_threshold=3, timeout_seconds=900):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.state = 'closed'  # closed, open, half_open
        self.last_failure_time = None

    def call(self, func, *args, **kwargs):
        if self.state == 'open':
            if time.time() - self.last_failure_time > self.timeout_seconds:
                self.state = 'half_open'
            else:
                raise ServiceDegradedError(f'Circuit breaker open')

        try:
            result = func(*args, **kwargs)
            if self.state == 'half_open':
                self.state = 'closed'
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = 'open'
            raise e
```

**Integration with Dashboard**:
- Dashboard shows: "Odoo: Degraded (circuit open, retry in 12 min)"
- Log entry: `{"action": "circuit_breaker_opened", "service": "odoo", "failure_count": 3}`

**Alternatives Considered**:
- Simple retry with backoff: No protection against repeated failures
- Manual service disable: Requires human intervention

---

### R4: Multiple MCP Server Registration
**Question**: How to register 3 MCP servers in Claude Code settings?

**Decision**: Add 3 entries to `mcpServers` object in `~/.claude/settings.json`, each with unique command and env vars

**Rationale**:
- Claude Code supports multiple MCP servers natively
- Each server runs as separate Node.js process
- Stdio transport (no port conflicts)
- Environment variables isolate secrets per server

**Implementation**:
```json
{
  "mcpServers": {
    "email": {
      "command": "node",
      "args": ["/absolute/path/to/level-gold/mcp-email-server/index.js"],
      "env": {
        "MCP_SERVER_SECRET": "secret1",
        "GMAIL_CREDENTIALS_PATH": ".secrets/gmail_credentials.json"
      }
    },
    "odoo": {
      "command": "node",
      "args": ["/absolute/path/to/level-gold/mcp-odoo-server/index.js"],
      "env": {
        "ODOO_URL": "http://localhost:8069",
        "ODOO_DB": "your_database",
        "ODOO_API_KEY": "your_api_key"
      }
    },
    "social": {
      "command": "node",
      "args": ["/absolute/path/to/level-gold/mcp-social-server/index.js"],
      "env": {
        "FB_SESSION_DIR": ".secrets/facebook_session",
        "IG_SESSION_DIR": ".secrets/instagram_session",
        "TWITTER_SESSION_DIR": ".secrets/twitter_session"
      }
    }
  }
}
```

**Testing**:
1. Start each server individually: `node mcp-odoo-server/index.js`
2. Verify startup logs show "Ready — listening on stdio"
3. Test tool call: `claude --print "Use mcp__odoo__get_financial_summary tool"`
4. Check all 3 servers start without conflicts

**Alternatives Considered**:
- Single MCP server with all tools: Harder to maintain, single point of failure
- Different transport (HTTP): Requires port management, more complex

---

## Key Findings Summary

| Research Area | Decision | Risk Level | Mitigation |
|---|---|---|---|
| Odoo API | JSON-2 with API key | Low | Test with curl before MCP implementation |
| Social Media | Playwright + human sim | Medium | Use burner accounts first, implement session health checks |
| Circuit Breaker | State machine in backoff.py | Low | Test with simulated failures (stop Docker) |
| Multiple MCPs | 3 separate servers in settings.json | Low | Test each server in isolation first |

---

## Dependencies Confirmed

**Python**:
- `playwright` (existing) — for social media automation
- `python-dotenv` (existing) — for .env loading
- No new Python dependencies needed

**Node.js**:
- `@modelcontextprotocol/sdk` (existing) — for MCP servers
- `zod` (existing) — for input validation
- No new Node.js dependencies needed

**Docker**:
- `odoo:19` — Odoo Community Edition
- `postgres:15` — Odoo database backend

---

## Next Steps

1. Create `docker-compose.yml` for Odoo + PostgreSQL
2. Test Odoo connection with curl (authenticate, search invoices)
3. Create `mcp-odoo-server/` with 4 tools
4. Create `mcp-social-server/` with 4 tools
5. Update `backoff.py` with circuit breaker
6. Create new skills: `fte-odoo-audit`, `fte-audit`, `fte-social-post`, `fte-social-summary`
7. Update existing skills: `fte-approve`, `fte-briefing`, `fte-triage`
