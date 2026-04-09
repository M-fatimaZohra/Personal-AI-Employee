# Research: Platinum Tier

**Branch**: `004-platinum-tier` | **Date**: 2026-03-10

---

## R-001: SSH Hardening on Ubuntu 22.04

**Decision**: Key-only authentication, fail2ban, no root login, keep port 22.

**Rationale**:
- `PasswordAuthentication no` in `/etc/ssh/sshd_config` eliminates brute-force password attacks
- `PermitRootLogin no` prevents direct root compromise
- `AllowUsers ubuntu` whitelists only the provisioned user
- `fail2ban` auto-bans IPs after 5 failed attempts (default jail)
- Keeping port 22 (not obscure port) because Azure NSG already restricts source IPs; obscure ports give false security

**Alternatives considered**:
- Change SSH port to non-standard (e.g., 2222): Rejected — security through obscurity, NSG is the real firewall
- Use Azure Bastion: Rejected — adds cost and complexity; SSH key is sufficient

---

## R-002: Git Bare Repo over SSH — Two Concurrent Writers Safety

**Decision**: `git pull --rebase` on both agents; unique filenames via timestamp prevent conflicts.

**Rationale**:
- Two agents write to **different files** (Cloud writes `Needs_Action/EMAIL_*.md`, Local writes `Approved/APPROVAL_*.md`) — no line-level conflicts
- `git pull --rebase` keeps history linear and avoids merge commits in the vault sync log
- Filenames include millisecond timestamps → collision probability ~0
- If a true conflict occurs (e.g., both modify `Dashboard.md`), the `--rebase` strategy applies Local Agent's changes on top → Local wins (correct per spec FR-013)

**Alternatives considered**:
- `git pull --merge`: Creates merge commits, pollutes vault sync history — rejected
- Syncthing (real-time sync): More moving parts, extra daemon, harder to debug — rejected for hackathon scope

---

## R-003: HTTPS for Odoo on Azure VM

**Decision**: nginx reverse proxy with self-signed certificate.

**Rationale**:
- nginx sits in front of Odoo (port 8069 → 443), terminates SSL, proxies to Odoo
- Self-signed cert is sufficient for hackathon demo (browser shows warning, user accepts)
- Odoo's built-in SSL requires editing `odoo.conf` and restarting Docker — more fragile
- nginx provides clean separation: swap to Let's Encrypt later with one `certbot` command
- Azure NSG opens port 443 (HTTPS) and closes 8069 (Odoo raw) — external users only see HTTPS

**Alternatives considered**:
- Let's Encrypt via Certbot: Requires a domain name, DNS propagation — rejected (no domain in scope)
- Odoo built-in SSL: Less flexible, config inside Docker container — rejected
- No HTTPS (HTTP only): Rejected — FR-018 requires HTTPS, credentials transmitted in clear text

---

## R-004: PM2 Startup on Ubuntu — Survives Azure VM Reboots

**Decision**: Three commands required — `pm2 startup systemd`, `pm2 save`, AND `sudo loginctl enable-linger ubuntu`.

**Rationale**:
- `pm2 startup systemd` detects systemd on Ubuntu 22.04 and generates the correct unit file
- `pm2 save` persists the process list to `~/.pm2/dump.pm2`
- **`sudo loginctl enable-linger ubuntu` is critical** — without it, systemd stops user services the moment the SSH session ends. PM2 and all watchers would die every time you disconnect.
- On reboot: systemd starts PM2, PM2 restores saved processes — fully automatic
- Running as non-root `ubuntu` user (correct practice) requires linger to keep user services alive

**Alternatives considered**:
- Custom systemd unit per script: More granular but more boilerplate — rejected for simplicity
- cron `@reboot`: Less reliable than systemd, no restart-on-crash — rejected

---

## R-005: Windows Task Scheduler — 2-Minute Interval

**Decision**: Windows Task Scheduler supports 1-minute minimum interval. 2-minute vault sync is achievable.

**Rationale**:
- Task Scheduler trigger: "Repeat task every 2 minutes" under daily trigger
- Minimum granularity is 1 minute — 2 minutes is within range
- The `.bat` script calls `vault_sync.sh` via Git Bash (`"C:\Program Files\Git\bin\bash.exe" vault_sync.sh`)

**Alternatives considered**:
- PM2 cron on Windows: PM2 on Windows is less stable than Linux — vault sync uses Task Scheduler instead
- Infinite loop Python script: Would hold a process slot — rejected; Task Scheduler is cleaner

---

## R-006: `os.rename()` Atomic Claim-by-Move on Linux

**Decision**: `os.rename()` on Linux is POSIX-guaranteed atomic when source and destination are on the same filesystem.

**Rationale**:
- POSIX standard: `rename(2)` syscall is atomic — if two processes call rename on the same source file, only one succeeds; the other gets `ENOENT` (file not found)
- Both `In_Progress/cloud/` and `Needs_Action/` are in the same vault directory → same filesystem → atomic
- On failure (ENOENT), agent catches the exception and skips the file — correct claim-by-move behavior

**Alternatives considered**:
- File locking (`fcntl.flock`): More complex, not needed — rename atomicity is sufficient
- Database-backed claim: Overkill for markdown files — rejected

---

## R-007: Git Rebase vs Merge for Vault Sync Pull

**Decision**: `git pull --merge` (default) for vault sync on both agents. NOT rebase.

**Rationale**:
- Vault sync is a **shared public branch** — rebase is forbidden on shared branches (golden rule: "never rebase on public branches")
- If Cloud and Local both pull simultaneously and one rebases, the rebased commits get a new SHA → the other agent's next pull sees orphaned commits → history diverges → sync breaks
- `--merge` is non-destructive: preserves all commit history, no SHA rewriting, safe for concurrent writers
- Merge commits in vault sync history are harmless — they show sync points, useful for debugging
- Obsidian does not read Git history — merge commits have zero UI impact

**Alternatives considered**:
- `git pull --rebase`: REJECTED — rewrites history on a shared repo, causes orphaned commits when two agents pull concurrently. Research confirmed this breaks the distributed model.
- Manual fetch + reset: Too aggressive, could discard uncommitted vault state

---

## R-008: Azure VM Firewall Strategy (NSG Rules)

**Decision**: Azure Network Security Group (NSG) allows only ports 22 (SSH) and 443 (HTTPS/Odoo). Block all others including 8069.

**Rationale**:
- Port 22: SSH access for operator and vault sync
- Port 443: HTTPS Odoo via nginx (not 8069 directly)
- Port 8069 (Odoo raw): Blocked externally — only accessible via nginx proxy on 443
- All other ports: Denied by default NSG rule
- This means Odoo is never exposed without HTTPS

**Security boundary**:
```
Internet → NSG (443 only) → nginx (SSL termination) → Odoo:8069 (localhost only)
Internet → NSG (22 only)  → SSH daemon → ubuntu user (key only)
```

---

## R-009: Secret Transfer Security (`scp` vs alternatives)

**Decision**: `scp` over SSH for one-time credential transfer. Never `rsync --daemon`, never email, never paste.

**Rationale**:
- `scp` uses the same SSH encryption as the vault sync connection — no additional infrastructure
- One-time operation: credentials rarely change (only on token expiry or rotation)
- The `.pem` key used for `scp` is the same key used for vault sync — single key pair to manage

**Transfer command template** (safe, auditable):
```bash
scp -i ~/.ssh/azure_vm.pem \
    level-gold/.secrets/gmail_credentials.json \
    level-gold/.secrets/gmail_token.json \
    level-gold/.env \
    ubuntu@<VM_IP>:~/level-platinum/cloud/.secrets/
```

**Alternatives considered**:
- Azure Key Vault: Adds cost and complexity — overkill for hackathon
- Environment variable injection via Azure portal: Acceptable but less portable — rejected for simplicity
- Git-crypt (encrypted git): Adds key management overhead — rejected

