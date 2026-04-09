# Data Model: Platinum Tier

**Branch**: `004-platinum-tier` | **Date**: 2026-03-10

---

## Entities

### 1. VaultFile (extends Gold Tier)
All existing Gold Tier vault files remain unchanged. Platinum adds new subdirectories.

**New directories added to vault:**
```
In_Progress/
  cloud/        ← Cloud Agent claims files here
  local/        ← Local Agent claims files here
Updates/
  cloud_status.md   ← Cloud Agent status (never Dashboard.md directly)
```

**State transitions (extended):**
```
Needs_Action/ → In_Progress/cloud/ → Pending_Approval/ → Approved/ → Done/
Needs_Action/ → In_Progress/local/ → Done/
```

---

### 2. ClaimRecord
Represents a file claimed by an agent via atomic move.

| Field | Type | Description |
|---|---|---|
| `filename` | string | Original filename from Needs_Action/ |
| `claimed_by` | enum: `cloud` / `local` | Agent that owns this file |
| `claimed_at` | ISO 8601 | Timestamp of claim |
| `status` | enum: `processing` / `done` / `failed` | Current state |

**File path pattern**: `In_Progress/<agent>/<original_filename>`
**Atomic guarantee**: Uses `os.rename()` (POSIX atomic on same filesystem)

---

### 3. CloudStatusRecord
Written by Cloud Agent to `Updates/cloud_status.md`. Merged into `Dashboard.md` by Local Agent.

**YAML frontmatter:**
```yaml
---
agent: cloud
last_updated: 2026-03-10T14:32:00Z
gmail_status: online          # online | offline | auth_required
odoo_status: online           # online | offline | degraded
emails_triaged_today: 3
drafts_pending: 1
last_email_triaged: 2026-03-10T14:30:00Z
error: null                   # error message if any
---
```

**Merge rule**: Local Agent reads this file after every vault sync and updates the `## Cloud Agent` section in Dashboard.md, then deletes Updates/cloud_status.md.

---

### 4. VaultSyncState
Tracks last successful sync on each machine. Stored in `.state/vault_sync_state.json` (gitignored).

| Field | Type | Description |
|---|---|---|
| `last_push` | ISO 8601 | Last successful git push |
| `last_pull` | ISO 8601 | Last successful git pull |
| `last_conflict` | ISO 8601 or null | Last conflict timestamp |
| `consecutive_failures` | int | Resets on success |
| `status` | enum: `ok` / `degraded` / `failed` | Current sync health |

---

### 5. VaultSyncGitignore
The `.gitignore` for the `vault-sync.git` bare repo. This is a separate file from the code repo's `.gitignore`.

**Always excluded (security-critical):**
```
.env
.env.*
.secrets/
*.pem
*.key
gmail_credentials.json
gmail_token.json
whatsapp_session/
facebook_session/
instagram_session/
twitter_session/
linkedin_session/
node_modules/
__pycache__/
*.pyc
.state/
Logs/
Archive/
Drop_Box/
```

**Always included (sync-required):**
```
Needs_Action/
In_Progress/
Pending_Approval/
Approved/
Plans/
Done/
Updates/
Dashboard.md
Company_Handbook.md
```

---

### 6. CredentialManifest
Documents which credentials live on each machine. Not a file in the system — an operational record for the operator.

| Credential | Local Machine | Azure VM | Transfer Method |
|---|---|---|---|
| `gmail_credentials.json` | ✅ source | ✅ copy | `scp` over SSH (one-time) |
| `gmail_token.json` | ✅ source | ✅ copy | `scp` over SSH (one-time) |
| `.env` (Gmail vars) | ✅ local .env | ✅ cloud .env | `scp` over SSH (one-time) |
| `.pem` SSH key | ✅ only here | ❌ never | stays local only |
| `whatsapp_session/` | ✅ only here | ❌ never | device-bound |
| `*_session/` (social) | ✅ only here | ❌ never | Playwright bot risk |
| Odoo admin password | local .env | cloud .env | `scp` over SSH |

---

## State Machine: Claim-by-Move

```
File created in Needs_Action/
         │
         ▼
   Both agents see it on next sync
         │
    ┌────┴────┐
    │         │
Cloud       Local
polls first  polls first
    │         │
os.rename()  os.rename()
to In_Progress/cloud/  to In_Progress/local/
    │         │
Only one succeeds (atomic)
Other agent sees file gone → skips
    │
Processing begins
    │
    ▼
Pending_Approval/ or Done/
In_Progress/<agent>/ cleared
```

---

## Vault Sync Data Flow

```
LOCAL MACHINE                    AZURE VM
──────────────                   ─────────────────
vault/                           vault-sync.git (bare)
  Approved/APPROVAL_xyz.md           │
         │                           │
  git add -A                         │
  git commit "sync: <timestamp>"     │
  git push origin main ──SSH────────►│
                                     │
                         git pull origin main
                         ──SSH─────►working vault/
                                     Approved/APPROVAL_xyz.md
                                     Cloud Agent sees it → sends ❌
                                     (Cloud is draft-only)
                                     Cloud Agent logs: "Local approved, execution local"
```

