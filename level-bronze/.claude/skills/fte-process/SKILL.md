---
name: fte-process
description: Process a pending item from Needs_Action — reason about it, apply handbook rules, update its status, and move it to Done. Use when the user wants to process or complete a pending task.
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Write, Edit, Bash(mv *)
argument-hint: "[optional: filename to process]"
---

# Process Pending Item

You are the `bronze-fte` AI Employee. Process an item through the pipeline.

## Steps

1. **List items** in `AI_Employee_Vault/Needs_Action/` using Glob (`*.md`).

2. **Select the item to process**:
   - If `$ARGUMENTS` is provided, find the matching file
   - Otherwise, pick the oldest item (earliest `dropped_at` in frontmatter)
   - If no items exist, report "No pending items to process" and stop

3. **Read the item** fully — frontmatter and body content.

4. **Read `AI_Employee_Vault/Company_Handbook.md`** for applicable rules.

5. **Reason about the item**:
   - What type of content is this?
   - What action should be taken? (archive, forward, flag, summarize)
   - Do any handbook rules apply?
   - Is any handbook rule violated by processing? If yes, set `status: rejected` with a `rejection_reason` in frontmatter and do NOT move to Done.

6. **Update the item's frontmatter**:
   - Set `status: done` (or `rejected` if rules violated)
   - Set `processed_by: fte-process`
   - Add `processed_at: <ISO timestamp>`
   - Add any `handbook_rule` references

7. **Move the file** from `AI_Employee_Vault/Needs_Action/` to `AI_Employee_Vault/Done/` (skip if rejected).

8. **Update `AI_Employee_Vault/Dashboard.md`** — refresh pending tasks and recent activity.

9. **Log the action**: Append to `AI_Employee_Vault/Logs/YYYY-MM-DD.json`:
   ```json
   {"timestamp":"<ISO>","action":"skill_executed","actor":"fte-process","source":"Needs_Action/<file>","destination":"Done/<file>","result":"success","details":"Processed: <summary>"}
   ```

10. **Report to the user**: what item was processed, what action was taken, and the current pending count.
