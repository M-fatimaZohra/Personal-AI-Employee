# Odoo Setup Guide — Gold Tier

Odoo 19 Community runs locally via Docker. The Gold Tier uses it as the accounting backend, accessed exclusively through the `mcp-odoo-server` (JSON-RPC 2.0).

---

## 1. Start Odoo

```bash
cd level-gold
docker compose up -d
```

First-time startup takes ~60 seconds. Check status:

```bash
docker compose ps
# gold-fte-odoo and gold-fte-db should both show "Up"
```

---

## 2. Create the Database (first time only)

1. Open `http://localhost:8069` in browser
2. Click **Create Database**
3. Fill in:
   - **Database Name**: `fte_business` (must match `ODOO_DB` in `.env`)
   - **Email**: your admin email
   - **Password**: strong password
   - **Language**: English
4. Click **Create Database** — wait ~2 minutes for initialization

---

## 3. Install the Accounting Module

1. Log in to `http://localhost:8069`
2. Go to **Apps** (top menu)
3. Search for `Accounting`
4. Click **Install** — this installs invoicing, partners, chart of accounts

---

## 4. Generate an API Key

1. Go to **Settings → Users & Companies → Users**
2. Click **Administrator**
3. Scroll to **API Keys** section → click **Generate**
4. Name it: `gold-fte-mcp`
5. Copy the key — it's shown only once
6. Paste into `.env`:

```env
ODOO_API_KEY=<your-key-here>
ODOO_URL=http://localhost:8069
ODOO_DB=fte_business
```

---

## 5. Verify the Connection

```bash
cd level-gold/mcp-odoo-server
node index.js
# Should print: MCP Odoo server started on stdio
# Should print: Connected to Odoo at http://localhost:8069 (fte_business)
```

Or test directly with the MCP tool via Claude Code:

```
mcp__odoo__get_financial_summary
```

Expected response: revenue, expenses, outstanding invoices (all zero on fresh install).

---

## 6. Add Test Data (Optional)

For testing without real business data:

1. Go to **Accounting → Customers → Invoices → New**
2. Set Customer: any name, Amount: $1,000, Status: Posted
3. This makes `get_financial_summary` return real values

Or use the `create_partner` + `create_invoice` MCP tools (requires approval via vault workflow).

---

## 7. Stop / Restart Odoo

```bash
docker compose stop        # Graceful stop
docker compose start       # Restart (data preserved)
docker compose down        # Stop + remove containers (data preserved in volume)
docker compose down -v     # DESTRUCTIVE — removes all data
```

---

## 8. Troubleshooting

| Problem | Fix |
|---------|-----|
| `http://localhost:8069` not loading | Run `docker compose up -d`, wait 60s |
| `401 Unauthorized` from MCP | Regenerate API key in Odoo → update `.env` |
| `invalid_db` error | Check `ODOO_DB` matches exact database name (case-sensitive) |
| Circuit breaker opened | Odoo is down — run `docker compose start`, wait 15 min for half-open probe |
| Database corrupted | Run `docker compose down && docker compose up -d` — may need to recreate DB |

---

## 9. How the MCP Server Connects

The `mcp-odoo-server` uses Odoo's JSON-RPC 2.0 API (not REST):

```
POST http://localhost:8069/json/2/<model>/<method>
Authorization: Bearer <ODOO_API_KEY>
```

All 4 tools use this pattern:
- `get_financial_summary` — reads invoices and bills, calculates revenue/expenses
- `list_transactions` — filters invoices by date range
- `create_invoice` — writes a new invoice (HITL-gated: checks `/Approved/` before executing)
- `create_partner` — creates a new customer record (HITL-gated)
