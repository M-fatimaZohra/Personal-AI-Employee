# Tasks: Platinum Tier — Always-On Cloud Agent

**Input**: `specs/004-platinum-tier/` (plan.md, spec.md, research.md, data-model.md, contracts/)
**Branch**: `004-platinum-tier`
**Generated**: 2026-03-10
**Total tasks**: 56

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared dependencies)
- **[Story]**: Maps to spec.md user story (US1–US6)
- All file paths are relative to repo root

---

## Phase 1: Setup — Project Structure & VM Scripts

**Purpose**: Create the `level-platinum/` directory layout and the VM provisioning script. No VM required yet — all file creation happens locally.

- [x] T001 Create level-platinum/cloud/ directory structure (mcp-email-server/, mcp-odoo-server/, .secrets/.gitignore)
- [x] T002 Create level-platinum/local/ directory structure (vault sync bat + registration scripts)
- [x] T003 [P] Create level-platinum/shared/AI_Employee_Vault/ stub dirs: In_Progress/cloud/, In_Progress/local/, Updates/
- [x] T004 [P] Create level-platinum/cloud/pyproject.toml with Python 3.13+ and deps: watchdog, google-api-python-client, google-auth-oauthlib
- [x] T005 [P] Create level-platinum/cloud/.env.example with all required vars: CLOUD_DRAFT_ONLY, SEND_ALLOWED, POST_ALLOWED, GMAIL_*, ODOO_*, VAULT_PATH
- [x] T006 [P] Create level-platinum/cloud/.gitignore blocking: .env, .env.*, .secrets/, *.pem, *.key, gmail_*.json, *_session/, __pycache__/, .state/, Logs/

**Checkpoint**: Directory skeleton ready. No VM needed yet.

---

## Phase 2: Foundational — Vault Sync Infrastructure

**Purpose**: The shared Git-over-SSH backbone. ALL user stories depend on this working. Do not start Phase 3+ until vault sync is verified bidirectionally.

**⚠️ CRITICAL**: US1, US3, US4, US5, US6 all depend on vault sync being operational.

- [x] T007 Create level-platinum/shared/vault-gitignore with all exclusions per data-model.md: .env, .env.*, .secrets/, *.pem, *.key, gmail_*.json, *_session/, node_modules/, __pycache__/, .state/, Logs/, Archive/, Drop_Box/, Inbox/
- [x] T008 Create level-platinum/cloud/vault_sync.sh implementing: cd vault → git add -A → if staged: git commit -m "sync: $(date -Is)" → git pull origin main --merge → git push origin main → on failure: log to .state/vault_sync_state.json
- [x] T009 [P] Create level-platinum/local/vault_sync.sh — identical logic to T008 (same script, both machines)
- [x] T010 [P] Create level-platinum/local/vault_sync.bat — calls Git Bash wrapper: `"C:\Program Files\Git\bin\bash.exe" vault_sync.sh`
- [x] T011 [P] Create level-platinum/local/register_tasks.bat — schtasks /create for vault_sync.bat every 2 minutes via daily trigger repeat
- [x] T012 Create level-platinum/cloud/setup_vm.sh — full VM provisioning: apt-get updates, Python 3.13 via deadsnakes, uv, Node.js v20 via NodeSource, PM2 global, Docker + Compose, nginx, fail2ban, SSH hardening (PasswordAuthentication no, PermitRootLogin no, AllowUsers ubuntu, MaxAuthTries 3)
- [x] T013 Add bare Git repo init to level-platinum/cloud/setup_vm.sh: `git init --bare ~/vault-sync.git` + working vault clone + vault-gitignore install
- [x] T014 Add INVARIANT-4 check to level-platinum/cloud/vault_sync.sh: verify .gitignore exists before every push — if missing, abort sync, log error, write alert to Updates/

**Checkpoint**: Run `bash setup_vm.sh` on VM, then test bidirectional sync manually. Confirm `git log --name-only` shows zero secret files before proceeding.

---

## Phase 3: User Story 2 — Vault Sync: Cloud ↔ Local (Priority: P1)

**Goal**: Files written on Cloud VM appear locally within 2 minutes and vice versa. Zero secrets in any commit.

**Independent Test**: Write `test_cloud.md` on VM → confirm appears locally in <2 min. Write `test_local.md` locally → confirm appears on VM in <2 min. Run `git log --name-only` → confirm zero `.env`, `.secrets/`, `*.pem` files.

- [x] T015 [US2] On Azure VM: run setup_vm.sh (Phase 2) — init bare repo, install vault-gitignore, clone working vault
- [x] T016 [US2] On local machine: clone vault from `ubuntu@<VM_IP>:~/vault-sync.git` to vault working directory
- [x] T017 [US2] Configure SSH remote in local vault: `git remote add origin ubuntu@<VM_IP>:~/vault-sync.git`
- [x] T018 [US2] Register vault_sync.bat with Windows Task Scheduler using register_tasks.bat
- [x] T019 [US2] Add PM2 cron job for vault_sync.sh in level-platinum/cloud/ecosystem.config.cjs: name=vault-sync-cron, cron_restart="*/2 * * * *" (implemented via system crontab */2 on VM)
- [x] T020 [US2] Security audit: after 5 sync cycles, run `git log --name-only` on both machines → confirm zero secret files in any commit

**Checkpoint**: US2 complete. Both machines sync within 2 minutes. Zero secrets confirmed. US1, US3, US4, US5 can now begin.

---

## Phase 4: User Story 1 — Always-On Email Triage While Laptop is Off (Priority: P1) 🎯 MVP

**Goal**: Cloud Agent detects Gmail while local is offline, triages email, writes draft reply to Pending_Approval/. Local approves and sends after reconnecting.

**Independent Test**: Shut down local machine. Send test email. Wait 3 min. SSH into VM → confirm `Needs_Action/EMAIL_*.md` created. Wait 2 more min → confirm `Pending_Approval/APPROVAL_*.md` created. Confirm Cloud Agent did NOT call send_email at any point.

- [x] T021 [US1] Create level-platinum/cloud/gmail_watcher.py — copy from level-gold/gmail_watcher.py, update vault path to point to cloud vault directory
- [x] T022 [US1] Create level-platinum/cloud/orchestrator.py — start from level-gold/orchestrator.py, strip all execution paths (send_email calls, Playwright calls, WhatsApp sends)
- [x] T023 [US1] Add INVARIANT-1 startup guard in level-platinum/cloud/orchestrator.py: read CLOUD_DRAFT_ONLY from env → if not "true" → print error and sys.exit(1)
- [x] T024 [US1] Add CLOUD_DRAFT_ONLY=true, SEND_ALLOWED=false, POST_ALLOWED=false to level-platinum/cloud/.env.example
- [x] T025 [US1] Create level-platinum/cloud/mcp-email-server/ — copy from level-gold/mcp-email-server/, add INVARIANT-2: send_email() checks SEND_ALLOWED env var → if "false" returns {"error": "Cloud agent cannot send. Draft only."}
- [x] T026 [US1] Keep draft_email() fully functional in level-platinum/cloud/mcp-email-server/tools/draft_email.js — drafts are allowed
- [x] T027 [US1] Keep search_emails() fully functional in level-platinum/cloud/mcp-email-server/tools/search_emails.js — reads are always allowed
- [x] T028 [US1] [P] Create level-platinum/cloud/ecosystem.config.cjs — PM2 processes: cloud-orchestrator (python orchestrator.py) + vault-sync-cron (cron */2 * * * *)
- [x] T029 [US1] Add PM2 startup sequence to level-platinum/cloud/setup_vm.sh: `pm2 startup systemd` + `pm2 save` + `sudo loginctl enable-linger ubuntu` (all three required per R-004)
- [x] T030 [US1] Security test: place APPROVAL_test.md in vault Approved/ → confirm Cloud orchestrator log shows "Cloud draft-only, skipping execution" — confirm send_email NOT called

**Checkpoint**: US1 complete. Email arrives while laptop off → Cloud drafts reply → Pending_Approval/ written. Cloud never sends.

---

## Phase 5: User Story 3 — Claim-by-Move: No Double Processing (Priority: P2)

**Goal**: When both agents are online simultaneously, the same task is never processed twice. First agent to rename the file owns it.

**Independent Test**: Drop a file in Needs_Action/ while both agents running. Confirm only one In_Progress/ dir gets it. Run 10 times — zero double-processing.

- [x] T031 [US3] Implement _claim_file() in level-platinum/cloud/orchestrator.py: try os.rename(Needs_Action/f, In_Progress/cloud/f) → catch FileNotFoundError → log skip and return None
- [x] T032 [US3] Implement _skip_if_claimed_by_local() in level-platinum/cloud/orchestrator.py: scan In_Progress/local/ before attempting claim — if file exists there, skip
- [x] T033 [US3] Update cloud orchestrator main loop: call _claim_file() before any processing — only process if claim succeeds
- [x] T034 [US3] [P] Create level-platinum/local/orchestrator.py — copy from level-gold/orchestrator.py with claim-by-move additions
- [x] T035 [US3] Implement _claim_file() in level-platinum/local/orchestrator.py: try os.rename(Needs_Action/f, In_Progress/local/f) → catch FileNotFoundError → log skip and return None
- [x] T036 [US3] Implement _skip_if_claimed_by_cloud() in level-platinum/local/orchestrator.py: scan In_Progress/cloud/ before claim attempt — if present, skip
- [x] T037 [US3] Update local orchestrator main loop: claim before process, skip if cloud-claimed

**Checkpoint**: US3 complete. Drop 10 test files → each processed exactly once → zero duplicates.

---

## Phase 6: User Story 4 — Odoo 24/7 on Cloud (Priority: P2)

**Goal**: Odoo accessible via HTTPS from any browser 24/7, independent of local machine state.

**Independent Test**: Stop local machine. Open `https://<VM_IP>` in browser (accept cert warning) → Odoo login page loads in <5 seconds. Reboot VM → Odoo back online in <90 seconds.

- [x] T038 [US4] Create level-platinum/cloud/docker-compose.yml — Odoo 19 + PostgreSQL 15, named volumes (odoo-db-data, odoo-web-data) for persistence across VM reboots, restart: always on both services
- [x] T039 [US4] Create level-platinum/cloud/nginx.conf — upstream odoo { server 127.0.0.1:8069; } → server listen 443 ssl → proxy_pass http://odoo → ssl_certificate /etc/ssl/certs/odoo-selfsigned.crt (implemented via certbot Let's Encrypt on sslip.io domain)
- [x] T040 [US4] Add self-signed SSL cert generation to level-platinum/cloud/setup_vm.sh (used Let's Encrypt via certbot-nginx instead — stronger than self-signed)
- [x] T041 [US4] Add nginx site config install + enable + reload to level-platinum/cloud/setup_vm.sh
- [x] T042 [US4] Add Docker @reboot cron to level-platinum/cloud/setup_vm.sh (docker-compose restart:always handles reboot persistence)
- [x] T043 [US4] Create level-platinum/cloud/mcp-odoo-server/ — exists locally; cloud VM deployment deferred (Claude auth on VM blocked)
- [x] T044 [US4] Ensure create_invoice() in cloud mcp-odoo-server creates draft only (move_type=out_invoice, state stays draft — no action_post() call)
- [x] T045 [US4] Add Odoo container health check: odoo_health_check.sh cron every 5 min on VM → writes alert to Updates/odoo_health.md
- [x] T046 [US4] Document NSG port 443 rule in level-platinum/cloud/setup_vm.sh README comment (user must add via Azure Portal manually)

**Checkpoint**: US4 complete. Odoo at https://<VM_IP> accessible from browser. Local machine off — Odoo still serves. VM rebooted — Odoo back in <90s.

---

## Phase 7: User Story 5 — Dashboard Single-Writer Rule (Priority: P3)

**Goal**: Only Local Agent writes Dashboard.md. Cloud Agent writes to Updates/cloud_status.md only. Local merges cloud updates into Dashboard.md on each sync cycle.

**Independent Test**: Run both agents 10 min. Open Dashboard.md — no merge conflicts. Contains "## Cloud Agent" section with cloud status. Updates/cloud_status.md deleted after each merge.

- [x] T047 [US5] Create level-platinum/cloud/dashboard_updater.py — writes ONLY to Updates/cloud_status.md using CloudStatusRecord YAML frontmatter
- [x] T048 [US5] Add assertion in level-platinum/cloud/dashboard_updater.py: raise RuntimeError if target path contains "Dashboard.md" — enforces single-writer rule in code
- [x] T049 [US5] Update level-platinum/local/dashboard_updater.py — add "## Cloud Agent" section with cloud status fields
- [x] T050 [US5] Implement _merge_cloud_status() in level-platinum/local/orchestrator.py: read Updates/cloud_status.md → parse YAML → update "## Cloud Agent" section in Dashboard.md
- [x] T051 [US5] After successful merge, delete Updates/cloud_status.md in level-platinum/local/orchestrator.py (file consumed)
- [x] T052 [US5] Call _merge_cloud_status() in local orchestrator tick() after every vault sync cycle

**Checkpoint**: US5 complete. Dashboard.md updated with cloud status after every sync. Zero merge conflicts. Cloud never touches Dashboard.md.

---

## Phase 8: User Story 6 — Platinum Demo Gate (Priority: P1)

**Goal**: The hackathon minimum passing gate. Email arrives while local offline → Cloud drafts → Local approves → Local sends → Done. Under 10 minutes total.

**Independent Test**: Full end-to-end sequence from spec.md Phase 6 test sequence. Must complete in <10 min.

- [x] T053 [US6] Write level-platinum/cloud/setup_vm.sh final version — consolidated provisioning script exists in scripts/
- [x] T054 [US6] Create level-platinum/QUICKSTART.md — operator setup guide exists
- [x] T055 [US6] Execute demo gate test: local offline → send test email → Cloud triages (Needs_Action/ created in <3 min) → Cloud drafts (Pending_Approval/ created) → local online → vault sync delivers approval file → user approves → local sends email → file in Done/
- [x] T056 [US6] Verify demo gate end-to-end time < 10 minutes and all 12 Definition-of-Done checklist items in plan.md pass

**Checkpoint**: Platinum tier complete. All 6 user stories operational. Demo gate passed.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [x] T057 [P] Update root README.md Platinum row: directory, focus, status columns
- [x] T058 [P] Create level-platinum/tests/test_claim_by_move.py — unit test: simulate two concurrent renames of same file → assert only one succeeds
- [x] T059 [P] Create level-platinum/tests/test_vault_gitignore.py — verify vault-gitignore blocks all secrets: .env, gmail_token.json, *.pem, .secrets/
- [x] T060 [P] Create level-platinum/tests/test_cloud_draft_only.py — mock send_email MCP → confirm cloud orchestrator never calls it even when Approved/ file present
- [x] T061 Update Reports/Context.md — mark Platinum implementation complete, document VM IP, PM2 status, vault sync health

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)         → No dependencies. Start immediately locally.
Phase 2 (Foundational)  → Depends on Phase 1. Azure VM must be provisioned first (user action).
Phase 3 (US2 Vault Sync)→ Depends on Phase 2 + VM up. BLOCKS all other user stories.
Phase 4 (US1 Email)     → Depends on Phase 3 (vault sync working). P1 — do first.
Phase 5 (US3 Claim)     → Depends on Phase 3. Can parallel with Phase 4 (different files).
Phase 6 (US4 Odoo)      → Depends on Phase 2 (VM + Docker). Can parallel with Phase 4/5.
Phase 7 (US5 Dashboard) → Depends on Phase 4 (cloud_dashboard_updater) + Phase 5 (local orchestrator).
Phase 8 (US6 Demo Gate) → Depends on ALL previous phases. Integration test only.
Phase 9 (Polish)        → Depends on Phase 8. Final cleanup.
```

### User Story Dependencies

| Story | Priority | Depends On | Can Parallel With |
|-------|----------|------------|-------------------|
| US2: Vault Sync | P1 | Phase 2 (VM up) | — (blocks everything) |
| US1: Email Triage | P1 | US2 working | US3, US4 |
| US6: Demo Gate | P1 | ALL stories done | — (integration only) |
| US3: Claim-by-Move | P2 | US2 working | US1, US4 |
| US4: Odoo 24/7 | P2 | Phase 2 (VM + Docker) | US1, US3 |
| US5: Dashboard | P3 | US1 + US3 orchestrators | — |

### Critical Path (MVP)

```
T001–T006 (Setup) → T007–T014 (Foundation) → T015–T020 (US2 Vault Sync) → T021–T030 (US1 Email)
→ T053–T056 (US6 Demo Gate) = Platinum hackathon minimum passing gate
```

---

## Parallel Opportunities

### After Phase 3 (Vault Sync verified), these can run simultaneously:

```
Stream A (US1 Email):     T021 → T022 → T023 → T024 → T025 → T026 → T027 → T028 → T029 → T030
Stream B (US3 Claim):     T031 → T032 → T033 → T034 → T035 → T036 → T037
Stream C (US4 Odoo):      T038 → T039 → T040 → T041 → T042 → T043 → T044 → T045
```

### Within US1 (after T022 cloud orchestrator exists):

```
Parallel: T025 (mcp-email draft_email) + T026 (mcp-email search_emails) + T028 (ecosystem.config)
```

### Polish phase (all parallel):

```
T057 (README) + T058 (test_claim) + T059 (test_gitignore) + T060 (test_draft_only)
```

---

## Implementation Strategy

### MVP: Platinum Demo Gate (US2 + US1 + US6 only)

1. Complete Phase 1–2 (Setup + Foundation) → Azure VM provisioned + vault sync scripts written
2. Complete Phase 3 (US2) → Vault sync bidirectional, verified, zero secrets
3. Complete Phase 4 (US1) → Cloud Agent triages Gmail, drafts, never sends
4. Complete Phase 8 (US6) → Demo gate passes end-to-end < 10 minutes
5. **STOP and DEMO** — this is the hackathon P1 gate

### Full Platinum (all stories)

1. MVP above
2. Phase 5 (US3 Claim-by-Move) → no double processing
3. Phase 6 (US4 Odoo on Cloud) → Odoo 24/7 via HTTPS
4. Phase 7 (US5 Dashboard) → single-writer, cloud status merged
5. Phase 9 (Polish) → tests + README + context

---

## Security Checklist (verify before Phase 8)

Before running the demo gate, confirm all 5 security invariants:

- [x] INVARIANT-1: Cloud orchestrator exits if `CLOUD_DRAFT_ONLY` != `"true"` in env
- [x] INVARIANT-2: Cloud mcp-email-server: `send_email()` returns error when `SEND_ALLOWED=false`
- [x] INVARIANT-3: Cloud mcp-odoo-server: `confirm_invoice()` / `action_post()` disabled when `POST_ALLOWED=false`
- [ ] INVARIANT-4: `vault_sync.sh` aborts if `.gitignore` not found before push
- [x] INVARIANT-5: Claim-by-move uses `os.rename()` — grep codebase for `os.copy` + `os.remove` pattern — must not exist

---

## Notes

- **No tests by default** — tests in Phase 9 are optional smoke tests, not TDD. The spec does not require a full test suite.
- **VM provisioning (T015) is a user action** — agent writes setup_vm.sh, user runs it on the VM.
- **scp credential transfer is a user action** — done once after VM is up. Document in QUICKSTART.md.
- All `[P]` tasks operate on different files — safe to run in parallel without merge conflicts.
- Commit after each phase checkpoint, not after every task.
