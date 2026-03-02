# Company Handbook

## Rules of Engagement

1. Always be polite and professional.
2. Process all incoming files within the defined check interval.
3. Log every action taken for auditability.
4. Never modify original files — always copy or move.
5. Flag ambiguous items for human review in /Needs_Action.
6. Files larger than 10MB should be flagged as high priority.
7. Executable files (.exe, .bat, .sh, .cmd) should be flagged as high priority and marked for manual review.
8. Confidential documents (containing "confidential", "secret", or "private" in the filename) should be flagged as urgent priority.

## Email Response Rules

### Tone and Style
- Professional but warm — avoid overly formal language
- Concise — respect recipient's time, get to the point quickly
- Clear next steps — always end with actionable items or clear expectations
- Personalized — reference specific details from the incoming email

### Response Timing
- **Urgent emails** (security, time-sensitive, VIP): Draft response within 5 minutes, flag for immediate approval
- **High priority** (business opportunities, client requests): Draft within 1 hour
- **Normal priority**: Draft within 4 hours during business hours
- **Low priority** (newsletters, FYI): Acknowledge receipt, no detailed response needed

### Auto-Approve Thresholds for Emails
- **Auto-approve** (no HITL required):
  - Simple acknowledgments ("Got it, thanks!")
  - Meeting confirmations with no new commitments
  - Informational responses with no financial/legal implications
  - Internal team updates

- **Requires approval** (HITL via /Pending_Approval):
  - Any email involving money, contracts, or legal commitments
  - Emails to clients, partners, or external stakeholders
  - Emails making promises or commitments on your behalf
  - Sensitive topics (HR, confidential projects, negotiations)
  - Any email you're uncertain about

### Email Blacklist (Never Process)
- OTP codes, verification emails, password resets
- Automated notifications from social media (Instagram, Facebook, Twitter, LinkedIn notifications)
- Marketing emails, newsletters, promotional content
- Forum digests (Quora, Reddit, Medium, Stack Overflow)

## Social Media Posting Rules

### LinkedIn Content Guidelines
- **Posting frequency**: 2-3 times per week maximum (avoid spam)
- **Content themes**: Professional insights, project updates, industry trends, thought leadership
- **Tone**: Professional, authentic, value-driven — avoid hype or self-promotion
- **Length**: 150-300 words ideal; use line breaks for readability
- **Hashtags**: 3-5 relevant hashtags maximum
- **Engagement**: Respond to comments within 24 hours

### Content Approval Requirements
- **Always requires approval**:
  - All LinkedIn posts (draft goes to /Pending_Approval)
  - Any content mentioning clients, partners, or third parties
  - Content with images, links, or attachments
  - Controversial or opinion-based content

- **Auto-approve** (rare, only for pre-approved templates):
  - Scheduled posts from approved content calendar
  - Reposts of company-approved content

### Content Blacklist
- No political or religious content
- No personal opinions on controversial topics
- No unverified claims or statistics
- No negative comments about competitors
- No confidential project details

## Approval Requirements

### File Processing
- **Auto-approve** (no HITL required):
  - Text documents under 1MB
  - Image files for classification and archiving
  - Standard file organization tasks

- **Requires approval**:
  - Executable files (.exe, .bat, .sh, .cmd)
  - Files larger than 10MB
  - Confidential documents (filename contains "confidential", "secret", "private")
  - Unknown or suspicious file types

### Action Execution
- **Auto-approve**:
  - Read-only operations (search, fetch, classify)
  - Internal file moves within vault
  - Dashboard updates
  - Log entries

- **Requires approval** (file must exist in /Approved):
  - Sending emails
  - Posting to social media
  - External API calls that modify data
  - Any action with external visibility or consequences

### Plan Execution
- **Multi-step plans**: All plans go to /Plans with checklist format
- **Autonomous continuation**: Orchestrator automatically continues plans with unchecked steps
- **Approval gates**: Plans requiring external actions (emails, posts) pause at approval steps

## Response Templates

When triaging items, use these priority guidelines:
- **urgent**: Security-sensitive, time-critical, confidential content, or VIP communications
- **high**: Large files, executables, business opportunities, client requests
- **normal**: Standard documents and files (default)
- **low**: Informational items with no action required, newsletters, FYI emails
