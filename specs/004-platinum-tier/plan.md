# Implementation Plan: Platinum Tier — Always-On Cloud Agent

**Branch**: `004-platinum-tier` | **Date**: 2026-03-10 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/004-platinum-tier/spec.md`

---

## Summary

Platinum Tier splits the Gold Tier single-machine agent into a **two-agent distributed system**. A Cloud Agent runs 24/7 on an Azure VM (Ubuntu 22.04, B2s) handling Gmail monitoring, email drafting, and Odoo operations in draft-only mode. A Local Agent on the user's Windows machine handles all approvals and execution (send email, post social media, WhatsApp). The two agents share state via a private Git bare repository hosted on the Azure VM, synced over SSH every 2 minutes — no data ever touches GitHub. Security is enforced at every layer: SSH key-only auth, Azure NSG firewall, secrets transferred via `scp` only, and a strict no-execute constraint on the Cloud Agent.

**Core invariant**: Cloud Agent MUST NEVER execute irreversible actions. Local Agent is the sole executor.

---

## Technical Context

**Language/Version**: Python 3.13+ (uv), Node.js v20+ (MCP servers)
**Primary Dependencies**: watchdog, google-api-python-client, PM2, Docker (Odoo), nginx, Git, fail2ban
**Storage**: Obsidian vault (markdown + YAML frontmatter), Git bare repo (vault sync), PostgreSQL via Docker (Odoo)
**Testing**: pytest (unit + integration), manual end-to-end demo gate test
**Target Platform**: Cloud — Ubuntu 22.04 LTS on Azure B2s VM; Local — Windows 11 with Git Bash
**Project Type**: Distributed two-agent system (cloud component + local component)
**Performance Goals**: Vault sync latency < 2 minutes; email triage within 3 minutes of receipt; demo gate end-to-end < 10 minutes
**Constraints**: $200 Azure credit / 30 days; B2s VM (2 vCPU, 4GB RAM); no domain name (self-signed HTTPS); no A2A messaging
**Scale/Scope**: Single operator, ~50 emails/day, ~5 social posts/week, ~10 invoices/month

---

## Constitution Check

| Principle | Status | Notes |
|---|---|---|
| I. Local-First & Privacy-Centric | ✅ PASS | Vault sync never touches GitHub. Credentials via `scp` only. Secrets excluded from all Git commits. |
| II. Perception → Reasoning → Action | ✅ PASS | Cloud Watchers → Cloud Orchestrator (draft) → Local Orchestrator (execute). No layer bypasses. |
| III. File-Based Communication | ✅ PASS | All Cloud↔Local communication via markdown files. New: `In_Progress/`, `Updates/` directories. |
| IV. Human-in-the-Loop (NON-NEGOTIABLE) | ✅ PASS | Cloud Agent writes to `Pending_Approval/` only. Local Agent executes only after user approval. |
| V. Agent Skills Architecture | ✅ PASS | Cloud uses same Gold Tier skills in draft mode. New `fte-cloud-status` skill for Updates/. |
| VI. Observability & Audit Logging | ✅ PASS | Both agents log to their local `Logs/`. `Updates/cloud_status.md` provides cross-agent visibility. |
| VII. Incremental Tier Progression | ✅ PASS | Gold Tier 100% complete before Platinum begins. |
| VIII. Resilience & Graceful Degradation | ✅ PASS | VM down → Local runs as Gold Tier. Sync failure → retry with backoff. Gmail down → Cloud queues locally. |

**GATE: PASSED — no violations. Proceeding to implementation.**

---

## Security Architecture

This is the security-first section. Every decision here is non-negotiable.

### Threat Model

| Threat | Mitigation |
|---|---|
| Brute-force SSH login | `PasswordAuthentication no` + fail2ban (5 attempts → 10min ban) |
| Root account compromise | `PermitRootLogin no` + `AllowUsers ubuntu` |
| Credentials leaked via Git | Vault-sync `.gitignore` blocks all `.env`, `.secrets/`, `*.pem`, tokens |
| Odoo exposed without HTTPS | Azure NSG blocks port 8069; only port 443 (nginx) exposed |
| Man-in-the-middle on vault sync | All sync over SSH (ED25519 key); no plaintext channels |
| Cloud Agent sending emails autonomously | Cloud MCP email server has `SEND_ALLOWED=false` env var; `send_email` tool returns error |
| Secrets transferred insecurely | Only `scp` over SSH; never Git, never email, never clipboard paste |
| VM reboot loses processes | PM2 startup systemd unit; `pm2 save` persists process list |
| Vault sync conflict corrupts Dashboard | Local Agent is sole `Dashboard.md` writer; Cloud writes only to `Updates/` |

### Security Invariants (enforced in code)

```
INVARIANT-1: Cloud orchestrator checks CLOUD_DRAFT_ONLY=true on startup.
             If missing → refuse to start with clear error.

INVARIANT-2: Cloud MCP email server: SEND_ALLOWED=false
             send_email() returns {"error": "Cloud agent cannot send. Draft only."}

INVARIANT-3: Cloud MCP odoo server: POST_ALLOWED=false
             create_invoice() creates draft only. confirm_invoice() disabled.

INVARIANT-4: vault_sync.sh verifies .gitignore exists before every push.
             If .gitignore missing → abort sync, log error, alert via Updates/.

INVARIANT-5: os.rename() for claim-by-move. Never os.copy() + os.remove().
             Rename is atomic (POSIX). Copy+remove is not.
```

---

## Project Structure

### Documentation (this feature)

```text
specs/004-platinum-tier/
├── plan.md              ← this file
├── spec.md              ← feature specification
├── research.md          ← 9 research decisions
├── data-model.md        ← entities, state machines, vault gitignore
├── quickstart.md        ← operator setup guide
├── contracts/
│   ├── vault-sync-contract.md     ← what syncs, what never syncs
│   ├── cloud-agent-contract.md    ← what Cloud can/cannot do
│   └── claim-by-move-contract.md  ← ownership protocol
└── tasks.md             ← generated by /sp.tasks (next step)
```

### Source Code (repository root)

```text
level-platinum/
├── cloud/                          ← deployed to Azure VM
│   ├── gmail_watcher.py            ← Gold copy, unchanged logic
│   ├── orchestrator.py             ← draft-only (CLOUD_DRAFT_ONLY=true)
│   ├── dashboard_updater.py        ← writes Updates/cloud_status.md only
│   ├── vault_sync.sh               ← git push/pull every 2 min (PM2 cron)
│   ├── setup_vm.sh                 ← one-time VM provisioning script
│   ├── docker-compose.yml          ← Odoo 19 + PostgreSQL 15 (cloud)
│   ├── nginx.conf                  ← HTTPS reverse proxy for Odoo
│   ├── ecosystem.config.cjs        ← PM2: gmail-watcher + orchestrator + vault-sync
│   ├── mcp-email-server/           ← SEND_ALLOWED=false
│   │   └── index.js                ← send_email() blocked, draft_email() allowed
│   ├── mcp-odoo-server/            ← POST_ALLOWED=false
│   │   └── index.js                ← create_invoice() draft only
│   ├── pyproject.toml
│   ├── .env.example                ← template, no secrets
│   └── .gitignore                  ← blocks .env, .secrets/, *.pem
│
├── local/                          ← runs on Windows laptop
│   ├── orchestrator.py             ← cloud-aware + claim-by-move + Dashboard merge
│   ├── dashboard_updater.py        ← merges Updates/cloud_status.md → Dashboard.md
│   ├── vault_sync.sh               ← git push/pull (called by Task Scheduler)
│   ├── vault_sync.bat              ← Windows Task Scheduler wrapper
│   ├── register_tasks.bat          ← schtasks registration for vault sync
│   └── .env.example
│
└── shared/                         ← vault files (not Python, not deployed)
    ├── vault-gitignore             ← .gitignore for vault-sync.git repo
    └── AI_Employee_Vault/
        ├── In_Progress/
        │   ├── cloud/              ← Cloud Agent claims here
        │   └── local/              ← Local Agent claims here
        └── Updates/
            └── cloud_status.md     ← Cloud writes, Local merges
```

**Structure Decision**: Two-component layout (`cloud/` + `local/`) under `level-platinum/`. Each component is independently deployable. `shared/` holds vault additions (new directories, gitignore). Cloud component is a stripped-down Gold Tier with execution blocked. Local component is Gold Tier enhanced with claim-by-move and Dashboard merge.

---

## Implementation Phases

### Phase 1 — VM Infrastructure (User Action Required)

**Prerequisite**: Must complete before any code is deployed.

| Step | Who | Action |
|---|---|---|
| 1.1 | **User** | Azure Portal → Create VM: Ubuntu 22.04, B2s, UAE North, SSH key auth |
| 1.2 | **User** | Download `.pem` key → save to `~/.ssh/azure_vm.pem`, `chmod 600` |
| 1.3 | **User** | Azure NSG: allow port 22 (SSH) + port 443 (HTTPS). Block all others. |
| 1.4 | **User** | SSH into VM: `ssh -i ~/.ssh/azure_vm.pem ubuntu@<VM_IP>` |
| 1.5 | **User** | Run `setup_vm.sh` on VM (installs Python, Node, PM2, Docker, nginx, fail2ban) |
| 1.6 | **User** | `scp` credentials to VM (gmail_credentials.json, gmail_token.json, .env) |

**setup_vm.sh installs:**
- Python 3.13 via deadsnakes PPA + uv
- Node.js v20 LTS via NodeSource
- PM2 globally
- Docker + Docker Compose
- nginx
- fail2ban (with SSH jail)
- Git (already present on Ubuntu)

**SSH hardening applied by setup_vm.sh:**
```
PasswordAuthentication no
PermitRootLogin no
AllowUsers ubuntu
MaxAuthTries 3
```

---

### Phase 2 — Vault Sync Foundation

**Goal**: Both machines share vault state via SSH Git. Zero secrets in any commit.

| Step | Component | What Gets Built |
|---|---|---|
| 2.1 | Azure VM | Initialize `~/vault-sync.git` as bare Git repo |
| 2.2 | Azure VM | Create working vault `~/vault/` with `In_Progress/`, `Updates/` dirs |
| 2.3 | Azure VM + Local | `vault_sync.sh` — git add/commit/pull --merge/push over SSH (NOT rebase — shared branch) |
| 2.4 | Both | `shared/vault-gitignore` installed as `~/vault/.gitignore` (blocks all secrets) |
| 2.5 | Azure VM | PM2 cron job: `vault_sync.sh` every 2 minutes |
| 2.6 | Local | `vault_sync.bat` + `register_tasks.bat` for Windows Task Scheduler |
| 2.7 | Both | **Security test**: confirm no `.env`, no `.secrets/`, no `*.pem` in any commit |

**Acceptance test for Phase 2:**
1. Write `test_cloud.md` on VM → wait 2 min → confirm appears locally
2. Write `test_local.md` locally → wait 2 min → confirm appears on VM
3. `git log --name-only` shows zero secret files ever committed

---

### Phase 3 — Cloud Agent (Draft-Only)

**Goal**: Cloud orchestrator triages Gmail and drafts replies. Never executes.

| Step | Component | What Gets Built |
|---|---|---|
| 3.1 | `cloud/gmail_watcher.py` | Copy from Gold Tier, same polling logic, same `Needs_Action/` output |
| 3.2 | `cloud/orchestrator.py` | Gold orchestrator with execution paths removed; `CLOUD_DRAFT_ONLY=true` guard |
| 3.3 | `cloud/orchestrator.py` | Claim-by-move: `os.rename(needs_action/file, in_progress/cloud/file)` |
| 3.4 | `cloud/orchestrator.py` | Skip files in `In_Progress/local/` — do not process |
| 3.5 | `cloud/dashboard_updater.py` | Writes only to `Updates/cloud_status.md`, never `Dashboard.md` |
| 3.6 | `cloud/mcp-email-server/` | `SEND_ALLOWED=false` env var; `send_email()` returns blocked error |
| 3.7 | `cloud/mcp-odoo-server/` | `POST_ALLOWED=false`; `create_invoice()` creates draft only |
| 3.8 | `cloud/ecosystem.config.cjs` | PM2: gmail-watcher + cloud-orchestrator + vault-sync-cron |
| 3.9 | Azure VM | `pm2 startup systemd` + `pm2 save` + `sudo loginctl enable-linger ubuntu` → survives reboots AND SSH disconnects |

**Security test for Phase 3:**
- Start Cloud Agent. Manually place `Approved/APPROVAL_test.md` in vault.
- Confirm Cloud Agent does NOT call `send_email`. Log shows "Cloud draft-only, skipping execution."
- Confirm `Updates/cloud_status.md` is written. Confirm `Dashboard.md` is NOT touched.

---

### Phase 4 — Odoo on Cloud (24/7)

**Goal**: Odoo accessible via HTTPS 24/7 from any browser.

| Step | Component | What Gets Built |
|---|---|---|
| 4.1 | `cloud/docker-compose.yml` | Odoo 19 + PostgreSQL 15 with named Docker volumes (data persists reboots) |
| 4.2 | `cloud/nginx.conf` | Reverse proxy: port 443 (HTTPS) → Odoo:8069 (localhost) |
| 4.3 | Azure VM | Self-signed SSL cert: `openssl req -x509 -newkey rsa:4096 ...` |
| 4.4 | Azure NSG | Add inbound rule: port 443 allowed. Keep 8069 blocked. |
| 4.5 | Azure VM | `docker compose up -d` → Odoo running |
| 4.6 | Azure VM | PM2 health check: if Odoo container stops → write alert to `Updates/` |

**Acceptance test for Phase 4:**
- Open `https://<VM_IP>` in browser → Odoo login page loads (accept cert warning)
- Stop local machine → refresh Odoo in browser → still accessible
- Reboot Azure VM → `docker compose up` via cron `@reboot` → Odoo back in < 90 seconds

---

### Phase 5 — Local Agent Updates

**Goal**: Local orchestrator is claim-by-move aware and merges cloud status into Dashboard.

| Step | Component | What Gets Built |
|---|---|---|
| 5.1 | `local/orchestrator.py` | Add `_claim_file()`: `os.rename(needs_action/file, in_progress/local/file)` |
| 5.2 | `local/orchestrator.py` | Add `_is_claimed_by_cloud()`: skip files in `In_Progress/cloud/` |
| 5.3 | `local/orchestrator.py` | Add `_merge_cloud_status()`: read `Updates/cloud_status.md` → update Dashboard section |
| 5.4 | `local/dashboard_updater.py` | New `## Cloud Agent` section in Dashboard.md template |
| 5.5 | `local/orchestrator.py` | After merge, delete `Updates/cloud_status.md` (consumed) |
| 5.6 | `local/vault_sync.bat` | Calls `"C:\Program Files\Git\bin\bash.exe" vault_sync.sh` |
| 5.7 | `local/register_tasks.bat` | `schtasks /create ... /sc minute /mo 2` for vault sync |

**Acceptance test for Phase 5:**
- Cloud writes `In_Progress/cloud/EMAIL_test.md`. Local orchestrator polls → skips it. ✓
- Local processes `In_Progress/local/EMAIL_test2.md`. Cloud orchestrator skips it. ✓
- Cloud writes `Updates/cloud_status.md`. After sync, Dashboard.md shows `## Cloud Agent` section. ✓

---

### Phase 6 — Platinum Demo Gate (Integration Test)

**Goal**: Execute the hackathon minimum passing requirement end-to-end.

**Test sequence:**
```
1. Stop local machine (or disconnect from internet)
2. Send test email to monitored Gmail account
3. Wait 3 minutes
4. SSH into VM: confirm Needs_Action/EMAIL_*.md created ✓
5. Wait 2 more minutes: confirm Pending_Approval/APPROVAL_*.md created ✓
6. Start local machine
7. Wait 2 minutes for vault sync: confirm approval file appears in Obsidian ✓
8. Move file to Approved/ in Obsidian
9. Wait 60 seconds: confirm email sent (check recipient inbox) ✓
10. Confirm file moved to Done/ ✓
11. Confirm log entry in Logs/YYYY-MM-DD.json ✓
12. Confirm Dashboard.md shows completed action ✓
```

**Total end-to-end time target: < 10 minutes**

---

## Key Architectural Decisions

### ADR-001: Cloud Agent is Stateless Executor-Blocked
Cloud Agent has no execution capability by design, not by trust. The MCP servers running on the cloud have environment variables (`SEND_ALLOWED=false`, `POST_ALLOWED=false`) that make execution physically impossible regardless of what the orchestrator requests. This is defence-in-depth: even if the orchestrator code has a bug, the MCP server refuses.

### ADR-002: Vault Sync via Git Bare Repo (not Syncthing)
Git over SSH was chosen over Syncthing because: (a) no additional daemon, (b) uses existing SSH infrastructure, (c) provides an audit log of every sync operation, (d) conflict resolution via `--merge` is safe for concurrent writers. Trade-off: 2-minute polling latency vs real-time Syncthing. Acceptable for this use case.

### ADR-003: Claim-by-Move using os.rename() (not file locking)
`os.rename()` is POSIX-atomic on the same filesystem. Two agents calling `rename()` on the same file — only one succeeds; the other gets `FileNotFoundError`, catches it, and skips. No lock files, no databases, no additional infrastructure.

### ADR-004: Local Agent is the Single Dashboard.md Writer
Prevents Git conflicts on the most-frequently-updated file. Cloud Agent writes to `Updates/cloud_status.md` (its own file, no conflicts). Local Agent merges this into Dashboard.md and deletes `Updates/cloud_status.md`. Only one file, one writer, zero conflicts.

### ADR-005: Playwright Social Media Stays Local
Azure datacenter IP ranges are known to Facebook, Instagram, and Twitter bot-detection systems. Running Playwright from an Azure VM IP would trigger account bans. All Playwright-based watchers and posters remain on the local machine where the user's residential IP is used.

---

## Complexity Tracking

| Decision | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Two separate orchestrators (cloud + local) | Cloud must be draft-only; Local must execute. One orchestrator cannot safely do both. | Single orchestrator with `if cloud:` flag — rejected because a single code mistake could enable cloud execution |
| nginx reverse proxy for Odoo HTTPS | Azure NSG must block port 8069; HTTPS required by FR-018 | Direct Odoo SSL — less flexible, harder to swap to Let's Encrypt later |
| `Updates/` directory (not direct Dashboard write) | Local Agent is sole Dashboard writer; Cloud must communicate status | Cloud writing Dashboard.md directly — rejected because creates Git conflicts |

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Azure credits expire mid-demo | Low (30 days) | High | Monitor usage; ~$42/month, $200 credit buffer |
| Gmail token expires on VM | Medium (60-day token) | Medium | `Updates/auth_required.md` alert; re-run `scp` with fresh token |
| Vault sync conflict on same file | Very Low | Low | `git pull --merge`; Local wins on `Dashboard.md` (sole writer); timestamps prevent `Needs_Action` conflicts |
| Azure VM reboots (maintenance) | Low | Medium | PM2 systemd startup + Docker `restart: always` — back online in < 90s |
| Social media session expires locally | Medium | Low | Stays local; user re-authenticates locally; Cloud unaffected |
| SSH key lost | Very Low | High | **Backup `.pem` to a secure password manager immediately after VM creation** |

---

## Definition of Done

- [ ] `setup_vm.sh` runs clean on fresh Ubuntu 22.04 VM
- [ ] Vault sync: file created on VM appears locally within 2 minutes (and vice versa)
- [ ] Zero secrets in any vault-sync Git commit (`git log --name-only` audit passes)
- [ ] Cloud Agent starts, triages test email, writes `Pending_Approval/*.md`
- [ ] Cloud Agent does NOT send email when `Approved/*.md` appears
- [ ] Odoo accessible via HTTPS from browser with VM running (local machine off)
- [ ] Local Agent skips files claimed by Cloud Agent
- [ ] Dashboard.md shows `## Cloud Agent` section after sync
- [ ] **Platinum demo gate** passes end-to-end in under 10 minutes
- [ ] All tests in `level-platinum/tests/` pass
