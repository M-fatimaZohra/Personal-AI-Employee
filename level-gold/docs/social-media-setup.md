# Social Media Setup Guide — Gold Tier

All social media automation uses **Python Playwright with persistent browser sessions**. Sessions are saved to `.secrets/` and reused automatically. No API keys required — the agent logs in once as a human would.

> **Use burner accounts for testing.** Graduate to primary accounts only after verifying the system works correctly in DRY_RUN mode.

---

## Prerequisites

```bash
cd level-gold
uv run playwright install chromium    # Install Playwright browser (once)
mkdir -p .secrets                     # Session directory (gitignored)
```

---

## Facebook

### First-time setup

```bash
FB_HEADLESS=false uv run python facebook_watcher.py --setup
```

- A real browser window opens
- Log in manually with your Facebook credentials
- Once your feed is visible, close the browser
- Session saved to `.secrets/facebook_session/`

### Verify

```bash
uv run python facebook_poster.py --content "Test post" --dry-run
# Should print: [DRY_RUN] Would post to Facebook
```

### Session health check

The poster checks for the login form on every run. If the session expires:

```bash
FB_HEADLESS=false uv run python facebook_watcher.py --setup   # Re-authenticate
```

---

## Instagram

### First-time setup

```bash
IG_HEADLESS=false uv run python instagram_watcher.py --setup
```

- Log in manually
- Complete any 2FA prompts
- Session saved to `.secrets/instagram_session/`

### Image requirement

Instagram posts require an image. Place images in `level-gold/media/`:

```
level-gold/media/
├── sky.png          # Used in initial testing
├── post_001.jpg
└── ...
```

The `InstagramScheduler` picks the next unused image automatically. Images are marked used in `.state/ig_media_state.json`.

### Verify

```bash
uv run python instagram_poster.py --image-path media/sky.png --content "Test" --dry-run
```

---

## Twitter / X

### First-time setup

```bash
LI_HEADLESS=false uv run python twitter_watcher.py --setup
```

- Log in manually at twitter.com / x.com
- Complete any verification prompts
- Session saved to `.secrets/twitter_session/`

### 280 character limit

`twitter_poster.py` validates content length before posting. Content exceeding 280 chars is truncated with `...` rather than failing.

### Verify

```bash
uv run python twitter_poster.py --content "Test tweet" --dry-run
```

---

## LinkedIn

### First-time setup (burner account strongly recommended)

```bash
LI_HEADLESS=false uv run python linkedin_watcher.py --setup
```

- Log in manually
- Session saved to `.secrets/linkedin_session/`

### LinkedIn has stricter bot detection

The poster uses human behavior simulation:
- Character-by-character typing (60–130 ms/char)
- Mouse movement with overshoot
- Feed browsing before posting
- Random pauses (4–10 s) for "proofreading"
- Jitter-scheduled posting (random time in 09:00–18:00 window)
- 23-hour minimum gap between posts

---

## Autonomous Posting Workflow

Once sessions are set up, posts flow through the vault without manual intervention:

```
1. Create APPROVAL_social_<platform>_*.md in AI_Employee_Vault/Approved/
   - frontmatter: action: social_post, platform: facebook|instagram|twitter
   - body: ## Post Content section with the post text

2. ApprovalWatcher detects it (within 10 seconds)
   → Moves file to Done/
   → Creates .state/<platform>_scheduled.json with jitter post time

3. Orchestrator heartbeat fires at scheduled time
   → Calls post_to_<platform>() with Playwright
   → Logs result to Logs/YYYY-MM-DD.json
   → Clears schedule file
```

---

## Session Management

| Platform | Session dir | Expiry | Re-auth trigger |
|----------|-------------|--------|-----------------|
| Facebook | `.secrets/facebook_session/` | ~30–90 days | Login page detected |
| Instagram | `.secrets/instagram_session/` | ~30–90 days | Login page detected |
| Twitter | `.secrets/twitter_session/` | ~30–90 days | Login page detected |
| LinkedIn | `.secrets/linkedin_session/` | ~14–30 days | Login page detected |

All posters run a **session health check** on startup — if the login form is detected, the script writes an alert to `Dashboard.md` and exits without posting.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `SessionExpiredError` or login page detected | Re-run `--setup` with `LI_HEADLESS=false` |
| 2FA blocks setup | Complete 2FA manually during `--setup`, then close browser |
| Post appears but then disappears | Platform spam filter — wait 24h, try with different content |
| Playwright browser not found | Run `uv run playwright install chromium` |
| Session dir missing | Run `mkdir -p .secrets` then re-authenticate |
| Post fires at wrong time | Check `.state/<platform>_scheduled.json` — edit `post_at` directly |
| Instagram `no image` error | Check `level-gold/media/` has `.jpg/.png` files; check `.state/ig_media_state.json` |
