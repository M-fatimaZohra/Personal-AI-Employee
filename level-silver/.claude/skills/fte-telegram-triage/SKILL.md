---
name: fte-telegram-triage
description: DEPRECATED — Telegram was replaced by WhatsApp in the Silver tier implementation. This skill is no longer active. Use fte-whatsapp-reply for WhatsApp message triage and auto-reply.
disable-model-invocation: true
allowed-tools: Read
argument-hint: ""
---

# ⚠️ DEPRECATED — Telegram Triage

**This skill has been deprecated.** Telegram was removed from the Silver tier in favour of WhatsApp (plan Decision 2 — see `specs/002-silver-tier/plan.md`).

## Replacement

Use **`fte-whatsapp-reply`** for all incoming message triage and auto-reply:

- Skill path: `level-silver/.claude/skills/fte-whatsapp-reply/SKILL.md`
- Invoked automatically by the orchestrator for `WHATSAPP_*.md` files
- Categorizer-Responder: ROUTINE (FAQ auto-draft → /Approved) vs SENSITIVE (HITL → /Pending_Approval)

## Why Telegram was removed

WhatsApp was chosen over Telegram because:
1. WhatsApp has significantly higher adoption in the target business context
2. The hackathon requirement specifies WhatsApp as the second channel
3. A Playwright-based persistent session approach was already in place for LinkedIn

## If you need Telegram support

1. Restore `telegram_watcher.py` (tasks T028–T032 in `specs/002-silver-tier/tasks.md`)
2. Create a new `fte-telegram-triage` skill mirroring `fte-whatsapp-reply`'s Categorizer-Responder pattern
3. Add `MSG_` prefix routing in `orchestrator.py` SKILL_ROUTING
