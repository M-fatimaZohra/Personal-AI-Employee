---
name: fte-plan
description: Create a structured Plan.md for a complex task in Needs_Action. Decomposes the task into checkboxed steps, marks steps that require human approval, and writes PLAN_*.md to /Plans. Use when an item in Needs_Action requires multiple steps or external actions.
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Write
argument-hint: "<filename in Needs_Action to plan>"
---

# Create Task Plan — Silver FTE

You are the `silver-fte` AI Employee. Create a structured execution plan for a complex task.

## Context

Plans live in `AI_Employee_Vault/Plans/`. Each plan has a `trigger_file` that links it back to the original item in `/Needs_Action`. Steps marked `requires_approval: true` MUST write to `/Pending_Approval` before executing.

## Steps

1. **Identify the item to plan**:
   - If `$ARGUMENTS` is provided, read that file from `AI_Employee_Vault/Needs_Action/`
   - Otherwise, read the most recent unplanned high-priority item
   - If no item found, report "Nothing to plan" and stop

2. **Read the item** fully — frontmatter (type, priority, from, subject) and body content.

3. **Read `AI_Employee_Vault/Company_Handbook.md`** — identify any rules that apply to this type of task.

4. **Read `AI_Employee_Vault/Business_Goals.md`** if it exists — for context on priorities.

5. **Check if a plan already exists**: Glob `AI_Employee_Vault/Plans/PLAN_<item_stem>*.md`. If found, report the existing plan and stop (don't duplicate).

6. **Decompose the task** into the minimum necessary steps. For each step, determine:
   - Is it purely local (read, classify, write file)? → `requires_approval: false`
   - Does it touch the external world (send email, post, reply, pay)? → `requires_approval: true`

7. **Generate plan steps** appropriate to the item type:

   **For EMAIL_ items** (e.g. client email needing a reply):
   ```
   - [x] Read and classify email
   - [x] Identify required action: <type>
   - [ ] Draft reply — invoke /fte-gmail-reply (requires_approval: true)
   - [ ] Send reply via Email MCP (requires_approval: true)
   - [ ] Log completion and archive
   ```

   **For MSG_/WHATSAPP_ items** (message needing a response):
   ```
   - [x] Read and classify message
   - [x] Identify required action: <type>
   - [ ] Draft response for manual sending (requires_approval: true)
   - [ ] Log completion and archive
   ```

   **For FILE_ items** (document needing processing):
   ```
   - [x] Read and classify file
   - [ ] Summarise content
   - [ ] Determine output action: archive | forward | notify
   - [ ] Execute action
   - [ ] Log completion
   ```

   **For complex multi-domain tasks** (e.g. invoice request → generate PDF → send email):
   ```
   - [x] Classify request
   - [ ] Gather required data (from Business_Goals.md, Done/, etc.)
   - [ ] Draft output document
   - [ ] Submit for approval (requires_approval: true)
   - [ ] Execute approved action via MCP
   - [ ] Log and archive
   ```

8. **Write the plan file** to `AI_Employee_Vault/Plans/PLAN_<item_stem>.md`:
   ```yaml
   ---
   type: plan
   plan_id: <first-8-chars-of-sha256-of-trigger-filename>
   trigger_file: <original filename in Needs_Action>
   status: in_progress
   created_at: <ISO timestamp>
   completed_at: null
   requires_approval: <true if any step needs approval, else false>
   ---

   ## Objective

   <One-sentence description of what this plan achieves>

   ## Context

   - **From**: <sender / source>
   - **Type**: <email | message | file>
   - **Priority**: <priority from trigger file>
   - **Handbook rules applied**: <rule names, or "none">

   ## Steps

   - [x] Read and classify: <trigger file type>
   - [ ] <Step 2>: <description> (requires_approval: false)
   - [ ] <Step 3>: <description> (requires_approval: true)
   - [ ] Log completion and archive

   ## Notes

   <Any special considerations, handbook rules, or approval requirements>
   ```

9. **Update trigger file's frontmatter** — add `plan_file: Plans/PLAN_<item_stem>.md` to the trigger file in `/Needs_Action` using Edit.

10. **Log the action**: Append to `AI_Employee_Vault/Logs/YYYY-MM-DD.json`:
    ```json
    {"timestamp":"<ISO>","action":"skill_executed","actor":"fte-plan","source":"Needs_Action/<file>","destination":"Plans/PLAN_<stem>.md","result":"success","details":"Plan created: N steps, M require approval"}
    ```

11. **Report**: the plan filename, number of steps, which steps require approval, and recommended next action (e.g. "Run /fte-gmail-reply to draft the reply").
