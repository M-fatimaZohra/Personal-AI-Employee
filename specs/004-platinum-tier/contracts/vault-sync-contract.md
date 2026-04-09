# Contract: Vault Sync

**Version**: 1.0 | **Date**: 2026-03-10

---

## Purpose
Defines exactly what the vault-sync bare Git repo syncs, what it never syncs, and the operational rules for both agents.

---

## Remote Definition
```
Remote name : origin
Remote URL  : ubuntu@<AZURE_VM_IP>:~/vault-sync.git
Transport   : SSH (key-based, ED25519)
Branch      : main
```

---

## SYNC — Always Included

| Path | Direction | Owner |
|---|---|---|
| `Needs_Action/` | Both ↔ | Cloud creates, Local reads |
| `In_Progress/cloud/` | Both ↔ | Cloud owns |
| `In_Progress/local/` | Both ↔ | Local owns |
| `Pending_Approval/` | Both ↔ | Cloud writes, Local approves |
| `Approved/` | Both ↔ | Local writes, Cloud reads |
| `Plans/` | Both ↔ | Cloud writes, Local reads |
| `Done/` | Both ↔ | Both write |
| `Updates/cloud_status.md` | Cloud → Local | Cloud writes only |
| `Dashboard.md` | Local → Cloud | Local writes only |
| `Company_Handbook.md` | Both ↔ | Operator writes |

---

## NO-SYNC — Always Excluded (`.gitignore` in vault root)

```gitignore
# SECURITY — never sync credentials
.env
.env.*
.secrets/
*.pem
*.key
*.p12
gmail_credentials.json
gmail_token.json
whatsapp_session/
facebook_session/
instagram_session/
twitter_session/
linkedin_session/

# RUNTIME — not needed on other machine
.state/
Logs/
Archive/
__pycache__/
*.pyc
node_modules/

# LOCAL ONLY — filesystem drops
Drop_Box/
Inbox/
```

---

## Sync Schedule

| Machine | Trigger | Command |
|---|---|---|
| Azure VM | PM2 cron `*/2 * * * *` | `bash ~/vault_sync.sh` |
| Local (Windows) | Task Scheduler every 2 min | `vault_sync.bat` |

---

## Sync Script Specification

```
vault_sync.sh (both machines, identical logic):
1. cd to vault directory
2. git add -A (stage all changes)
3. git diff --cached --quiet → if nothing staged, skip commit
4. git commit -m "sync: <ISO timestamp>"
5. git pull origin main --merge (get remote changes — NOT rebase; shared branch rule)
6. git push origin main (send local changes)
7. On any failure: log to .state/vault_sync_state.json, retry in next cycle
8. Never exit with non-zero code that would crash PM2
```

---

## Conflict Resolution Rules

| File | Resolution Strategy |
|---|---|
| `Dashboard.md` | Local Agent wins (it is the sole writer; Cloud never commits changes to it) |
| `Needs_Action/*.md` | No conflict possible — filenames include microsecond timestamps |
| `Updates/cloud_status.md` | Cloud Agent wins (it is the sole writer) |
| All others | `git pull --rebase` → later commit wins |

