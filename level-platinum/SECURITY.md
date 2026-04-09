# Security Notes — Platinum Tier

## What Is Gitignored and Why

### Secrets and Credentials (NEVER commit)

| Path | Reason |
|------|--------|
| `.env` / `.env.*` | Gmail, Odoo API key, session dirs — never commit |
| `.secrets/` | All OAuth tokens and Playwright session files |
| `.azure-secrets/` | SSH private key (.pem) and VM IP address |
| `.secrets/gmail_credentials.json` | OAuth2 client secret from Google Cloud Console |
| `.secrets/gmail_token.json` | Auto-generated OAuth access/refresh token |
| `.secrets/whatsapp_session/` | WhatsApp LocalAuth session |
| `.secrets/linkedin_session/` | Playwright persistent session for LinkedIn |
| `.secrets/facebook_session/` | Playwright persistent session for Facebook |
| `.secrets/instagram_session/` | Playwright persistent session for Instagram |
| `.secrets/twitter_session/` | Playwright persistent session for Twitter/X |
| `cloud/.env` | Cloud agent config (CLOUD_DRAFT_ONLY=true, test Gmail) |
| `local/.env` | Local agent config (business Gmail, all credentials) |

### Runtime State (machine-specific)

| Path | Reason |
|------|--------|
| `.state/` | Deduplication IDs, social scheduler state — machine-specific |
| `.state/processed_ids.json` | Gmail/WhatsApp/LinkedIn message IDs |
| `.state/facebook_scheduled.json` | Pending Facebook post schedule |
| `.state/instagram_scheduled.json` | Pending Instagram post schedule + media queue |
| `.state/twitter_scheduled.json` | Pending Twitter post schedule |
| `.state/linkedin_scheduled.json` | Pending LinkedIn post schedule |
| `logs/` | Vault sync logs — runtime data, not code |

### Vault Data (AI_Employee_Vault/)

The vault `.gitignore` (separate from root) excludes all runtime data:

| Path | Reason |
|------|--------|
| `Needs_Action/*.md` | Real message content from Gmail, WhatsApp, social platforms |
| `In_Progress/cloud/*.md` | Cloud agent claimed items |
| `In_Progress/local/*.md` | Local agent claimed items |
| `Pending_Approval/*.md` | Draft replies with client names, amounts, context |
| `Approved/`, `Rejected/` | Execution-ready or cancelled actions (local-only) |
| `Plans/*.md` | AI-generated plans, CEO briefings, LinkedIn drafts |
| `Done/*.md` | Completed items with full transaction details |
| `Logs/*.json` | Daily audit logs with message metadata, partner names |
| `Business_Goals.md` | Revenue targets, client pipeline — sensitive business data |
| `FAQ_Context.md` | Pricing, services, escalation contacts |
| `Dashboard.md` | Live system status (local-only, cloud writes to Updates/) |

**What IS committed from vault**:
- `Company_Handbook.md` — agent behavior rules (no sensitive data)
- Empty directory structure (for Git tracking)

### Build Artifacts

| Path | Reason |
|------|--------|
| `.venv/` | Recreated by `uv sync` |
| `cloud/.venv/`, `local/.venv/` | Tier-specific venvs |
| `node_modules/` | Recreated by `npm install` |
| `__pycache__/`, `*.pyc` | Python bytecode — not portable |

---

## Platinum-Specific Security Model

### Five Layers of Draft-Only Protection (Cloud Agent)

1. **Environment variable**: `CLOUD_DRAFT_ONLY=true` in `cloud/.env`
2. **Startup check**: `orchestrator.py` raises `RuntimeError` if not set
3. **MCP server flags**: `SEND_ALLOWED=false`, `POST_ALLOWED=false` in cloud MCP configs
4. **DRY_RUN mode**: `DRY_RUN=true` in `cloud/.env` (logs actions, never executes)
5. **No execution code**: Cloud orchestrator has no `approval_watcher`, no posters

### Credential Isolation

- **Cloud Agent**: Test Gmail account (dedicated AI agent account)
- **Local Agent**: Business Gmail account (your real credentials)
- **Social Media**: Local only (Azure IPs trigger bot detection)
- **WhatsApp**: Local only (device-bound session)
- **Odoo**: Cloud has read-only access; Local executes invoice posts

### Vault Sync Security

**What syncs** (Git over SSH, every 2 min):
- `Needs_Action/email/`, `Needs_Action/social/`, `Needs_Action/odoo/`
- `In_Progress/cloud/`, `In_Progress/local/`
- `Pending_Approval/`
- `Plans/`
- `Done/`
- `Updates/` (cloud status)
- `Company_Handbook.md`

**What NEVER syncs** (vault `.gitignore`):
- `.env`, `.secrets/`, `*.pem`, `*.key`
- `Approved/`, `Rejected/` (local-only execution triggers)
- `Dashboard.md` (local is single-writer)
- `Logs/` (too large, machine-specific)
- `Drop_Box/`, `Inbox/` (local filesystem only)
- `Needs_Action/whatsapp/`, `Needs_Action/filesystem/` (local-only domains)

### SSH Key Security

The `.pem` file grants root access to the VM. Protect it:

```bash
chmod 400 .azure-secrets/ai-employee-key.pem  # Read-only for owner
```

Never commit `.azure-secrets/` to Git (already in `.gitignore`).

---

## No Hardcoded Credentials

All code reads credentials exclusively from environment variables and `.secrets/` files. No tokens, passwords, or API keys appear in committed code.

**The one exception to watch**: `.env.example` must never contain real values — only placeholders. Verify before committing.

---

## Secrets Setup Checklist

### Cloud Agent (on VM)
- [ ] `cloud/.env` created with `CLOUD_DRAFT_ONLY=true`
- [ ] `.secrets/gmail_credentials.json` — test Gmail account
- [ ] `.secrets/gmail_token.json` — auto-created after auth
- [ ] `SEND_ALLOWED=false` in cloud MCP email server
- [ ] `POST_ALLOWED=false` in cloud MCP Odoo server

### Local Agent (on laptop)
- [ ] `local/.env` created from `.env.example` (all values filled)
- [ ] `.secrets/gmail_credentials.json` — business Gmail account
- [ ] `.secrets/gmail_token.json` — auto-created after `--auth-only` run
- [ ] `.secrets/whatsapp_session/` — created by first QR scan
- [ ] `.secrets/linkedin_session/` — created by `--setup` run
- [ ] `.secrets/facebook_session/` — created by `--setup` run
- [ ] `.secrets/instagram_session/` — created by `--setup` run
- [ ] `.secrets/twitter_session/` — created by `--setup` run
- [ ] `.azure-secrets/ai-employee-key.pem` — chmod 400
- [ ] `.azure-secrets/vm-ip.txt` — VM public IP
- [ ] `DRY_RUN=false` in `local/.env` when ready for live execution

---

## Pre-Deployment Security Audit

Before pushing to GitHub or deploying to VM:

- [ ] No email addresses in committed docs (use "dedicated AI agent account" placeholder)
- [ ] No VM IP addresses in committed files (use `<VM_IP>` placeholder)
- [ ] No API keys or tokens in any `.md` files
- [ ] `.gitignore` verified — all secrets excluded
- [ ] Vault `.gitignore` verified — runtime data excluded
- [ ] `.env.example` contains only placeholders
- [ ] SSH key has 400 permissions
- [ ] Test Gmail on cloud, business Gmail on local (never reversed)
