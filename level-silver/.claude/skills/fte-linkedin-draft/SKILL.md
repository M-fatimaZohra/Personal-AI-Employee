---
name: fte-linkedin-draft
description: Draft a professional LinkedIn post based on Business_Goals.md and recent activity from /Done and /Logs. Writes LINKEDIN_DRAFT_<date>.md to /Plans for HITL review. After the user approves by moving the file to /Approved, the orchestrator auto-posts via Playwright at a randomised jitter time.
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Write
argument-hint: "[optional: topic or theme override]"
---

# Draft LinkedIn Post — Silver FTE

You are the `silver-fte` AI Employee. Draft a compelling LinkedIn post for business promotion.

## Approval Flow (HITL then Auto-Post)

**This skill drafts the post. The user reviews in Obsidian. Once the user moves the file
to `/Approved`, the orchestrator schedules the post at a randomised time within the
configured posting window (default 09:00–18:00) and auto-posts via Playwright with
human behavior simulation. The user's only action is moving the file in Obsidian.**

## Steps

1. **Check for today's existing draft**: Glob `AI_Employee_Vault/Plans/LINKEDIN_DRAFT_<today-date>*.md`.
   - If found and status is `draft`: report the existing draft path and stop (don't duplicate)
   - If found and status is `approved` or `posted`: create a new draft for a different topic

2. **Read business context** — gather intelligence for the post:

   a) **Business Goals** (`AI_Employee_Vault/Business_Goals.md` if it exists):
      - Revenue targets and current progress
      - Active projects and client wins
      - Key metrics and achievements
      - LinkedIn content themes specified

   b) **Recent wins** — read last 5 files in `AI_Employee_Vault/Done/` (sorted by date):
      - Extract titles and summaries of completed tasks
      - Identify "wins" worth sharing (completed projects, milestones, achievements)

   c) **Recent logs** — read last 20 lines from most recent `AI_Employee_Vault/Logs/` file:
      - Identify high-value actions executed recently

3. **Determine the post topic**:
   - If `$ARGUMENTS` is provided: use that as the topic/theme
   - If Business_Goals.md has `linkedin_themes` or `post_topics`: use the next unused theme
   - Otherwise: choose from recent wins or a general professional insight

4. **Draft the LinkedIn post** (150–300 words):

   **Post structure**:
   - **Hook** (1-2 sentences): Open with a specific observation, question, or bold statement. NOT "Excited to share..." or "I'm thrilled..."
   - **Body** (3-5 short paragraphs of 1-3 sentences each): The insight, story, or value
   - **Takeaway** (1 sentence): The key lesson or call to reflection
   - **Question** (1 sentence): Engage readers by asking for their experience/opinion
   - **Hashtags** (3-5 relevant hashtags on the last line)

   **Tone**: Professional but human. Specific, not generic. Draws on real activity where possible.

   **Topics to consider** (pick the most relevant):
   - AI automation saving time on a specific task
   - Lesson learned from a client interaction
   - Progress toward a business goal
   - Tool or workflow improvement
   - Industry insight related to your work

5. **Write the draft file** to `AI_Employee_Vault/Plans/LINKEDIN_DRAFT_<YYYY-MM-DD>.md`:
   ```yaml
   ---
   type: linkedin_post
   status: draft
   created_at: <ISO timestamp>
   topic: <one-line topic description>
   word_count: <approximate count>
   hashtags: [<hashtag1>, <hashtag2>, <hashtag3>]
   based_on: <source of inspiration — e.g. "client win from Done/EMAIL_abc.md">
   review_required: true
   ---

   ## Draft Post

   > Review and edit this post. Then move this file to `/Approved` when ready.
   > After approval, the orchestrator will auto-post via Playwright at a
   > randomised time within your configured posting window (default 09:00–18:00).
   > A 23-hour gap between posts is enforced automatically.

   <Full post content here — plain text, ready to post>

   ## Alternative Version (shorter)

   <A shorter 80-100 word version of the same post>

   ## Suggested Hashtags

   <hashtag1> <hashtag2> <hashtag3> <hashtag4> <hashtag5>

   ## Why This Topic

   <One paragraph explaining why this topic was chosen and what data it's based on>

   ## To Approve

   1. Review and edit the Draft Post section above
   2. Move this file to `AI_Employee_Vault/Approved/`
   3. The orchestrator will schedule the post and show the time on Dashboard
   4. The file moves to `/Done` automatically after posting
   ```

6. **Log**: Append to `AI_Employee_Vault/Logs/YYYY-MM-DD.json`:
   ```json
   {"timestamp":"<ISO>","action":"skill_executed","actor":"fte-linkedin-draft","source":"Business_Goals.md + Done/","destination":"Plans/LINKEDIN_DRAFT_<date>.md","result":"success","details":"Draft created: topic=<topic>, words=<count>"}
   ```

7. **Report**:
   - "Draft saved to `Plans/LINKEDIN_DRAFT_<date>.md`"
   - Show the post hook (first 2 sentences) as a preview
   - "Review in Obsidian → edit if needed → move to /Approved → copy-paste to LinkedIn"
