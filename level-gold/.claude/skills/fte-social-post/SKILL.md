---
name: fte-social-post
description: Draft social media posts for Facebook, Instagram, and Twitter/X based on Business_Goals.md themes and recent activity. Creates platform-appropriate content (respects 280-char limit for Twitter, image requirements for Instagram) and writes APPROVAL_social_*.md files to /Pending_Approval/ for HITL review. Triggered manually or by orchestrator.
disable-model-invocation: true
allowed-tools: Read, Glob, Grep, Write
argument-hint: "[optional: facebook | instagram | twitter | all] [optional: topic]"
---

# Draft Social Media Posts — Gold FTE

You are the `gold-fte` AI Employee. Draft platform-appropriate social media posts for HITL review.

## Context

- `$ARGUMENTS[0]`: Platform filter — "facebook", "instagram", "twitter", or "all" (default: all)
- `$ARGUMENTS[1]`: Optional topic hint (e.g. "AI chatbot launch", "case study")
- Posts must align with `AI_Employee_Vault/Business_Goals.md` LinkedIn Content Themes
- Each platform gets its own approval file — they are INDEPENDENT of each other

---

## Steps

### 1. Read Business Context

Read `AI_Employee_Vault/Business_Goals.md`:
- Extract Content Themes (AI & Automation, Build in Public, Full-Stack Engineering)
- Note current week's theme from Content Calendar (Mon=AI, Wed=Build in Public, Fri=Engineering)
- Note Active Projects and Priority Opportunities for post hooks
- Note Topics to Avoid

Read `AI_Employee_Vault/Company_Handbook.md` for tone guidelines.

### 2. Determine Platforms to Post

- `$ARGUMENTS` contains "facebook" → draft Facebook post only
- `$ARGUMENTS` contains "instagram" → draft Instagram post only
- `$ARGUMENTS` contains "twitter" → draft Twitter post only
- `$ARGUMENTS` is empty or "all" → draft for ALL three platforms

### 3. Check Existing Pending Posts

Glob `AI_Employee_Vault/Pending_Approval/APPROVAL_social_*.md` — if posts for a platform
already exist, note them but still draft new ones (user decides which to use).

### 4. Draft Platform-Appropriate Content

**Theme selection** (use today's day of week or topic hint from $ARGUMENTS):
- Monday → AI & Automation theme
- Wednesday → Build in Public theme
- Friday → Full-Stack Engineering theme
- Other days → rotate based on last post theme in Done/

**Facebook post** (if applicable):
- Length: 150–400 words — more narrative, can include context
- Format: Hook sentence → 2-3 value paragraphs → call to action → 3-5 hashtags
- Tone: Professional but conversational
- NO 280-char limit

**Instagram post** (if applicable):
- Length: 125–200 words caption
- Format: Strong opening line → value bullet points → emoji usage OK → 5-10 hashtags
- Note: Requires an image — add `image_required: true` in frontmatter
- Tone: Engaging, visual storytelling

**Twitter/X post** (if applicable):
- Length: MAX 240 chars (leave buffer below 280-char limit)
- Format: Punchy insight or question → value → 1-2 hashtags
- Count characters EXACTLY — reject if over 240 chars
- Tone: Direct, thought-provoking

### 5. Write Approval Files

For each platform, write to `AI_Employee_Vault/Pending_Approval/APPROVAL_social_<platform>_<YYYY-MM-DD>.md`:

```yaml
---
type: social_post
platform: <facebook|instagram|twitter>
created_at: <ISO timestamp>
expires_at: <ISO timestamp + 48 hours>
status: pending
requires_image: <true|false>  # Instagram only
char_count: <N>               # Twitter only
theme: <AI & Automation | Build in Public | Full-Stack Engineering>
---

## Post Content

<drafted post content here>

## Hashtags
<hashtags here>

## To Approve
Move this file to AI_Employee_Vault/Approved/

## To Reject
Move this file to AI_Employee_Vault/Rejected/
```

### 6. Log and Report

Append to `AI_Employee_Vault/Logs/<YYYY-MM-DD>.json`:
```json
{"timestamp":"<ISO>","action":"skill_executed","actor":"fte-social-post","source":"Business_Goals.md","destination":"Pending_Approval/","result":"success","details":"Drafted N posts: <platforms>"}
```

Report:
```
✅ Social post drafts ready for review:
  Facebook:  Pending_Approval/APPROVAL_social_facebook_<date>.md
  Instagram: Pending_Approval/APPROVAL_social_instagram_<date>.md (⚠️ requires image)
  Twitter:   Pending_Approval/APPROVAL_social_twitter_<date>.md (N chars)

Open in Obsidian → move to Approved/ to publish.
```
