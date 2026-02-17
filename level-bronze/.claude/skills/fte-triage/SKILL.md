---
name: fte-triage
description: Triage all items in the AI Employee vault's Needs_Action folder. Classify items by type, apply Company Handbook rules, update priorities, and refresh the Dashboard. Use when the user wants to classify or prioritize pending items.
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Write, Edit
argument-hint: "[optional: filter by type]"
---

# Triage Pending Items

You are the `bronze-fte` AI Employee. Triage all items in the vault.

## Steps

1. **Read the handbook** at `AI_Employee_Vault/Company_Handbook.md` — note all rules.

2. **List all files** in `AI_Employee_Vault/Needs_Action/` using Glob (`*.md`).

3. **For each file**, read it and parse the YAML frontmatter (between `---` markers). Extract: `type`, `original_name`, `dropped_at`, `status`, `priority`.

4. **Classify each item**:
   - If `type` is `file_drop`: check file extension and content for category (document, image, code, data, other)
   - Apply handbook rules: for each rule, if it matches the item, update priority accordingly and add `handbook_rule: <rule number>` to the frontmatter

5. **Update each file's frontmatter** with any priority changes or handbook rule references. Use the Edit tool to modify only the frontmatter section.

6. **Rewrite `AI_Employee_Vault/Dashboard.md`** with:
   - System Status: show current state
   - Pending Tasks: table of all items in `/Needs_Action` grouped by type, sorted by priority (urgent > high > normal > low)
   - Recent Activity: read last 10 entries from the most recent file in `AI_Employee_Vault/Logs/`

7. **Log the action**: Append a JSON line to `AI_Employee_Vault/Logs/YYYY-MM-DD.json`:
   ```json
   {"timestamp":"<ISO>","action":"skill_executed","actor":"fte-triage","source":"Needs_Action","destination":"Dashboard.md","result":"success","details":"Triaged N items"}
   ```

8. **Report** to the user: list each item with its type, priority, and any handbook rules applied.

If `$ARGUMENTS` is provided, only triage items matching that type filter.
