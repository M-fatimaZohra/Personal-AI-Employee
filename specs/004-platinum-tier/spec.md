# Feature Specification: Platinum Tier — Always-On Cloud Agent

**Feature Branch**: `004-platinum-tier`
**Created**: 2026-03-10
**Status**: Draft
**Input**: Platinum Tier — Azure VM cloud agent with vault sync, draft-only cloud orchestrator, 24/7 Odoo, local execution gate

---

## Overview

Platinum Tier upgrades the Gold Tier Digital FTE from a single local agent into a **two-agent distributed system**. A Cloud Agent runs 24/7 on an Azure VM and handles monitoring and drafting. A Local Agent on the user's laptop handles approvals and all final execution. The two agents stay in sync via a private Git repository hosted on the Azure VM, communicated over an encrypted SSH tunnel — no data ever touches GitHub.

**Core rule**: Cloud = eyes + brain (read, draft, never execute). Local = hands + wallet (approve, send, post).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Always-On Email Triage While Laptop is Off (Priority: P1)

A client sends an urgent email at 3 AM. The user's laptop is closed. The Cloud Agent detects the email, triages it, drafts a reply, and places it in the approval queue. When the user wakes up and opens their laptop, the draft is already waiting in Obsidian. The user approves it; the Local Agent sends it.

**Why this priority**: This is the defining Platinum capability — the minimum demo gate required by the hackathon. Without this, Platinum is indistinguishable from Gold.

**Independent Test**: Send an email while the local machine is off. Confirm draft appears in Obsidian vault on laptop after reconnection. Approve it; confirm email is sent.

**Acceptance Scenarios**:

1. **Given** the local laptop is offline, **When** an email arrives in Gmail, **Then** the Cloud Agent creates `Needs_Action/EMAIL_*.md` within 3 minutes and pushes it to vault sync.
2. **Given** the draft exists in `Pending_Approval/`, **When** the laptop comes online and pulls vault sync, **Then** the approval file appears in Obsidian within 2 minutes.
3. **Given** the user moves the file to `Approved/`, **When** the Local Agent detects it, **Then** the email is sent via MCP and moved to `Done/` within 60 seconds.
4. **Given** the Cloud Agent drafts a reply, **When** the draft is created, **Then** it is never sent — only written to `Pending_Approval/` and awaits local approval.

---

### User Story 2 — Vault Sync: Cloud and Local Stay in Sync (Priority: P1)

Both the Cloud Agent and Local Agent write to their own copy of the Obsidian vault. Changes made by one agent are visible to the other within 2 minutes via encrypted Git sync over SSH — no data ever leaves the private SSH tunnel to any public service.

**Why this priority**: Vault sync is the backbone of all Platinum workflows. Every other story depends on it working reliably.

**Independent Test**: Write a file on the Cloud VM vault. Confirm it appears on the local vault within 2 minutes, and vice versa.

**Acceptance Scenarios**:

1. **Given** the Cloud Agent writes `Needs_Action/EMAIL_*.md`, **When** 2 minutes elapse, **Then** the file appears in the local vault.
2. **Given** the user moves a file to `Approved/` locally, **When** 2 minutes elapse, **Then** the file appears in the Cloud VM vault.
3. **Given** both agents write files simultaneously, **When** sync runs, **Then** no data is lost — both files are preserved.
4. **Given** the vault sync script runs, **When** inspected, **Then** no `.env`, no `.secrets/`, no session files are included in any commit.

---

### User Story 3 — Claim-by-Move: No Double Processing (Priority: P2)

When both Cloud and Local agents are online simultaneously, the same email or task must never be processed twice. The first agent to move a file from `Needs_Action/` to `In_Progress/<agent>/` owns it; the other agent ignores it.

**Why this priority**: Prevents duplicate replies, duplicate invoice creation, and conflicting actions. Critical for correctness.

**Independent Test**: Drop a task file in `Needs_Action/` while both agents are running. Confirm only one agent processes it.

**Acceptance Scenarios**:

1. **Given** a new file in `Needs_Action/`, **When** Cloud Agent moves it to `In_Progress/cloud/`, **Then** the Local Agent skips it entirely.
2. **Given** a new file in `Needs_Action/`, **When** Local Agent moves it first, **Then** Cloud Agent skips it.
3. **Given** an item in `In_Progress/cloud/`, **When** Cloud Agent completes processing, **Then** the file moves to `Pending_Approval/` or `Done/` and `In_Progress/cloud/` is cleared.

---

### User Story 4 — Odoo Runs 24/7 on Cloud (Priority: P2)

Odoo Community is deployed on the Azure VM via Docker with HTTPS enabled. The Cloud Agent can query financial data and create draft invoices at any time, even when the local machine is off. The user approves invoice posting from the local machine.

**Why this priority**: Makes Odoo a true always-on business tool rather than a local service that only works when the laptop is open.

**Independent Test**: Stop the local machine. Access Odoo from a browser using the Azure VM's public IP. Confirm it is accessible and serving data.

**Acceptance Scenarios**:

1. **Given** the Azure VM is running, **When** accessing Odoo via HTTPS at the VM's public IP, **Then** the Odoo login page loads within 5 seconds.
2. **Given** a new invoice request email arrives, **When** the Cloud Agent processes it, **Then** a draft invoice is created in Odoo and an approval file is written to `Pending_Approval/`.
3. **Given** the local machine is offline, **When** the user checks Odoo from a mobile browser, **Then** financial data is accessible without the local machine being on.

---

### User Story 5 — Dashboard Single-Writer Rule (Priority: P3)

Only the Local Agent writes to `Dashboard.md`. The Cloud Agent writes its status updates to `Updates/cloud_status.md`. When the local vault syncs, the Local Agent merges cloud updates into `Dashboard.md`. This prevents file conflicts.

**Why this priority**: Prevents sync conflicts on the most-written file in the vault. Important for stability but not blocking for core demo.

**Independent Test**: Run both agents simultaneously for 10 minutes. Open `Dashboard.md`. Confirm it reflects both agents' statuses with no merge conflicts.

**Acceptance Scenarios**:

1. **Given** both agents are running, **When** the Cloud Agent completes a task, **Then** it writes to `Updates/cloud_status.md` — never directly to `Dashboard.md`.
2. **Given** `Updates/cloud_status.md` exists, **When** the Local Agent syncs, **Then** it merges cloud updates into `Dashboard.md` and clears `Updates/`.
3. **Given** a vault sync conflict occurs on `Dashboard.md`, **When** the merge runs, **Then** the Local Agent's version takes priority.

---

### User Story 6 — Platinum Demo Gate (Priority: P1)

The hackathon minimum passing gate: email arrives while local is offline → Cloud drafts reply + writes approval file → local returns + user approves → local executes send → logs → moves to Done.

**Why this priority**: This is the explicit Platinum demo requirement from the hackathon specification.

**Independent Test**: Shut down local machine. Send test email. Start local machine 5 minutes later. Confirm draft waiting, approve, confirm email sent.

**Acceptance Scenarios**:

1. **Given** local is offline, **When** email arrives, **Then** Cloud drafts reply in `Pending_Approval/` within 3 minutes.
2. **Given** local comes back online, **When** vault syncs, **Then** approval file appears in Obsidian within 2 minutes of connection.
3. **Given** user approves, **When** Local Agent detects approval, **Then** email is sent, logged, and all related files moved to `Done/`.

---

### Edge Cases

- What happens when vault sync fails (SSH timeout)? → Retry every 30 seconds; log failure; both agents continue operating independently.
- What happens when both agents write the same filename simultaneously? → Git conflict: Local Agent wins for `Dashboard.md`; unique timestamps in filenames prevent `Needs_Action/` collisions.
- What happens if Cloud VM runs out of disk space? → Alert written to `Updates/cloud_status.md`; sync continues with existing files.
- What happens if Gmail token expires on Cloud VM? → Cloud Agent writes `Updates/auth_required.md`; Gmail watcher pauses; user refreshes token via `scp`.
- What happens if Azure VM goes down? → Local Agent continues as full Gold Tier; vault sync resumes when VM returns.
- What happens if vault sync conflicts are unresolvable? → Local Agent's version always wins (single-writer authority).

---

## Requirements *(mandatory)*

### Functional Requirements

**Cloud Agent (Azure VM)**
- **FR-001**: Cloud Agent MUST run continuously 24/7 on the Azure VM, surviving reboots via process manager startup.
- **FR-002**: Cloud Agent MUST monitor Gmail every 2 minutes and create `Needs_Action/EMAIL_*.md` files.
- **FR-003**: Cloud Agent MUST operate in draft-only mode — it MUST write to `Pending_Approval/` but MUST NOT send emails, post to social media, or execute any irreversible action.
- **FR-004**: Cloud Agent MUST implement claim-by-move — move files from `Needs_Action/` to `In_Progress/cloud/` before processing; skip files already in `In_Progress/local/`.
- **FR-005**: Cloud Agent MUST write status updates to `Updates/cloud_status.md` — never directly to `Dashboard.md`.
- **FR-006**: Cloud Agent MUST support graceful degradation — if Gmail is unavailable, log the failure and retry with exponential backoff without crashing.

**Vault Sync**
- **FR-007**: Vault sync MUST run every 2 minutes on both Cloud VM and local machine via scheduled task.
- **FR-008**: Vault sync MUST use Git over SSH directly to the Azure VM — it MUST NOT push to GitHub or any public service.
- **FR-009**: Vault sync MUST exclude all secrets: `.env`, `.secrets/`, `gmail_token.json`, `gmail_credentials.json`, `whatsapp_session/`, social session files.
- **FR-010**: Vault sync MUST sync: `Needs_Action/`, `Pending_Approval/`, `Approved/`, `Plans/`, `Done/`, `In_Progress/`, `Updates/`, `Dashboard.md`.
- **FR-011**: Credentials MUST be transferred to Azure VM via encrypted file copy over SSH only — never via Git.

**Local Agent (updated from Gold)**
- **FR-012**: Local Agent MUST implement claim-by-move — move files to `In_Progress/local/` before processing; skip files in `In_Progress/cloud/`.
- **FR-013**: Local Agent MUST be the sole writer of `Dashboard.md` — it MUST merge `Updates/cloud_status.md` into `Dashboard.md` on each sync cycle.
- **FR-014**: Local Agent MUST retain all Gold Tier execution capabilities: sending emails via MCP, posting to social media via Playwright, processing WhatsApp.
- **FR-015**: WhatsApp watcher MUST remain on the local machine only — it MUST NOT be deployed to Cloud VM.
- **FR-016**: All Playwright-based social media watchers and posters MUST remain on the local machine — they MUST NOT run on Azure VM.

**Odoo on Cloud**
- **FR-017**: Odoo Community MUST run on the Azure VM via Docker Compose, accessible 24/7.
- **FR-018**: Odoo MUST be accessible via HTTPS (self-signed certificate acceptable for demo).
- **FR-019**: Cloud Agent MUST use Odoo MCP server in draft-only mode — create draft invoices but MUST NOT post/confirm without local approval.
- **FR-020**: Odoo data MUST be persisted via Docker volume — surviving VM restarts.

**Security**
- **FR-021**: The vault-sync bare Git repository MUST reside on the Azure VM only — accessible only via SSH key authentication.
- **FR-022**: Azure VM MUST have firewall rules allowing only port 22 (SSH) and port 8069 (Odoo) inbound.
- **FR-023**: SSH password authentication MUST be disabled on the Azure VM — key-based auth only.

### Key Entities

- **Cloud Agent**: Orchestrator on Azure VM; monitors Gmail, drafts replies, claims tasks, writes to `Pending_Approval/` and `Updates/`; never executes irreversible actions.
- **Local Agent**: Orchestrator on local machine; processes approvals, executes sends/posts, merges Dashboard, runs WhatsApp + all Playwright social media.
- **Vault Sync**: Bare Git repo on Azure VM; both agents push/pull every 2 minutes over SSH; single source of shared markdown state.
- **In_Progress/**: Claim directory with `cloud/` and `local/` subdirs; prevents double-processing when both agents are online.
- **Updates/**: Cloud Agent's write-only status directory; Local Agent reads and merges into `Dashboard.md`.
- **Credential Transfer**: One-time `scp` over SSH from local to Azure VM; never uses Git or any public service.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Email arriving while local machine is offline is triaged and drafted by Cloud Agent within 3 minutes of receipt.
- **SC-002**: Vault sync delivers files from Cloud to Local (and vice versa) within 2 minutes under normal network conditions.
- **SC-003**: No task is processed by both agents simultaneously — claim-by-move prevents double processing in 100% of test cases.
- **SC-004**: Odoo is accessible via HTTPS from any browser 24/7, independent of local machine state.
- **SC-005**: Platinum demo gate completes end-to-end (email → draft → approval → send → Done) in under 10 minutes total.
- **SC-006**: Zero secrets (credentials, tokens, session files) appear in any vault-sync Git commit.
- **SC-007**: Cloud Agent survives Azure VM reboot and resumes operations within 60 seconds.
- **SC-008**: Local Agent retains full Gold Tier functionality when operating without Cloud Agent (graceful degradation).

---

## Assumptions

- Azure VM is provisioned: Ubuntu 22.04, B2s (2 vCPU, 4GB RAM), ports 22 and 8069 open.
- SSH `.pem` key for Azure VM is stored securely on local machine.
- Gmail credentials (`gmail_credentials.json`, `gmail_token.json`) exist from Gold Tier and will be copied to VM via `scp`.
- Social media Playwright sessions remain on local machine only — not transferred to VM (Azure datacenter IPs trigger bot detection).
- WhatsApp stays local only — device-bound session cannot be transferred.
- A2A (Agent-to-Agent direct messaging) is out of scope — file-based vault sync only.
- No domain name required — Odoo accessed via Azure VM public IP with self-signed HTTPS cert.
- Vault sync latency of 2 minutes is acceptable for this use case.
- `level-platinum/` is a new top-level directory with `cloud/` and `local/` subdirectories.
- $200 Azure credit (30-day trial) covers the full implementation and demo period (~$42 estimated cost).

---

## Out of Scope

- A2A (Agent-to-Agent) direct messaging — Phase 2, not implemented.
- Social media watchers/posters on Cloud VM — bot detection risk with Azure datacenter IPs.
- WhatsApp on Cloud VM — device-bound session cannot be transferred.
- Banking/payment integrations — not required by any hackathon tier.
- Custom domain or production SSL — self-signed cert acceptable for demo.
- Multi-user support — single operator system.

---

## Dependencies

- Gold Tier fully complete ✅ (all 12 requirements verified, pushed to GitHub main)
- Azure VM provisioned with public IP and SSH access (user action required)
- Port 22 (SSH) and 8069 (Odoo) open in Azure Network Security Group (user action required)
- `gmail_credentials.json` and `gmail_token.json` available from Gold Tier `.secrets/`
