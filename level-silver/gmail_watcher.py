"""Gmail Watcher — polls Gmail API for important emails, creates action files."""

import base64
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Self

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from base_watcher import BaseWatcher
from dashboard_updater import update_dashboard
from logger import DRY_RUN, log_action

# ---------------------------------------------------------------------------
# OAuth scope — read-only is sufficient and safer than full access
# ---------------------------------------------------------------------------
# gmail.modify is a superset of gmail.readonly:
# it also allows send + archive (threads.modify) used by the MCP server.
# After changing this, delete .secrets/gmail_token.json and re-run:
#   uv run python gmail_watcher.py --auth-only
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

# ---------------------------------------------------------------------------
# Gmail search query — highly selective
#
# Logic:
#   is:unread              → only new emails
#   is:important           → Gmail's AI-flagged important emails
#   -category:social       → exclude Facebook, Twitter, etc.
#   -category:updates      → exclude automated notifications
#   -category:promotions   → exclude marketing / newsletters
#   -category:forums       → exclude mailing lists, Quora digests, etc.
#
# Additional client-side filtering is applied after fetch (see below).
# ---------------------------------------------------------------------------
GMAIL_QUERY = (
    "is:unread is:important "
    "-category:social "
    "-category:updates "
    "-category:promotions "
    "-category:forums"
)

# ---------------------------------------------------------------------------
# Security blacklist — subject + snippet keyword check
# Emails matching any of these are silently dropped and marked processed.
# This protects against OTP leakage via the vault.
# ---------------------------------------------------------------------------
SECURITY_BLACKLIST: list[str] = [
    "otp",
    "one-time password",
    "one time password",
    "verification code",
    "verify your",
    "login code",
    "sign-in code",
    "signin code",
    "auth code",
    "authentication code",
    "2-step verification",
    "two-step verification",
    "two factor",
    "2fa code",
    "passcode",
    "security code",
    "reset your password",
    "password reset",
    "confirm your account",
    "account verification",
]

# ---------------------------------------------------------------------------
# Digest sender blacklist — sender domain / address substring check
# Digest emails from these services are skipped regardless of labels.
# ---------------------------------------------------------------------------
DIGEST_BLACKLIST_DOMAINS: list[str] = [
    "instagram.com",
    "facebookmail.com",
    "facebook.com",
    "quora.com",
    "quoramail.com",
    "medium.com",
    "digest.medium.com",
    "noreply@medium.com",
]


class GmailWatcher(BaseWatcher):
    """Monitors Gmail for important, non-promotional emails.

    Authentication:
        OAuth 2.0 via credentials in .secrets/gmail_credentials.json.
        Token saved to .secrets/gmail_token.json after first browser login.

    Polling:
        Every POLL_INTERVAL seconds (default: 120 = 2 minutes).

    Filter pipeline (layered):
        1. Gmail query:  is:unread is:important, excludes social/promo/forum categories
        2. Security:     drop OTP / verification / login-code emails
        3. Digest:       drop Instagram, Facebook, Quora, Medium digests
        4. Dedup:        skip already-processed message IDs (persisted to .state/)

    Action files:
        EMAIL_<message_id>.md written to AI_Employee_Vault/Needs_Action/
    """

    POLL_INTERVAL = 120  # 2 minutes

    def __init__(
        self,
        vault_path: str | Path,
        credentials_path: str | Path = ".secrets/gmail_credentials.json",
        token_path: str | Path = ".secrets/gmail_token.json",
        query: str = GMAIL_QUERY,
        poll_interval: int = POLL_INTERVAL,
    ) -> None:
        super().__init__(vault_path, check_interval=poll_interval)

        # Paths are resolved relative to the script's directory so the watcher
        # can be started from any working directory.
        base_dir = Path(__file__).parent
        self.credentials_path = (base_dir / credentials_path).resolve()
        self.token_path = (base_dir / token_path).resolve()
        self.query = query

        # Gmail API service (set after authentication)
        self._service = None

        # Persistent state: processed message IDs survive restarts
        self._state_file = base_dir / ".state" / "gmail_processed_ids.json"
        self._state_file.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # OAuth authentication
    # ------------------------------------------------------------------

    def _authenticate(self):
        """Authenticate with Gmail API using OAuth 2.0.

        On first run: opens browser for user login, saves token.
        On subsequent runs: loads saved token, refreshes if expired.
        Raises FileNotFoundError if credentials file is missing.
        """
        creds: Credentials | None = None

        # Load existing token
        if self.token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)

        # Refresh expired token
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                log_action(
                    self.logs, "gmail_token_refresh", "GmailWatcher",
                    result="success", details="OAuth token refreshed automatically",
                )
            except Exception as e:
                log_action(
                    self.logs, "gmail_token_refresh_failed", "GmailWatcher",
                    result="error",
                    details=f"Refresh failed — re-authentication required: {e}",
                )
                creds = None  # Force re-auth below

        # Full re-authentication (opens browser)
        if not creds or not creds.valid:
            if not self.credentials_path.exists():
                raise FileNotFoundError(
                    f"Gmail credentials not found at {self.credentials_path}\n"
                    "Download gmail_credentials.json from Google Cloud Console:\n"
                    "  APIs & Services → Credentials → OAuth 2.0 Client IDs → Download"
                )

            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.credentials_path), SCOPES
            )
            creds = flow.run_local_server(port=0)
            log_action(
                self.logs, "gmail_auth_new", "GmailWatcher",
                result="success", details="New OAuth token obtained via browser",
            )

        # Persist token
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(creds.to_json(), encoding="utf-8")

        return build("gmail", "v1", credentials=creds)

    # ------------------------------------------------------------------
    # Persistent ID tracking (deduplication)
    # ------------------------------------------------------------------

    def _load_processed_ids(self) -> set[str]:
        """Load set of already-processed Gmail message IDs."""
        if not self._state_file.exists():
            return set()
        try:
            data = json.loads(self._state_file.read_text(encoding="utf-8"))
            return set(data.get("gmail_ids", []))
        except (json.JSONDecodeError, OSError):
            return set()

    def _save_processed_id(self, message_id: str) -> None:
        """Persist a message ID to prevent re-processing after restart."""
        ids = self._load_processed_ids()
        ids.add(message_id)
        # Cap at 10,000 to prevent unbounded file growth
        trimmed = sorted(ids)[-10_000:]
        self._state_file.write_text(
            json.dumps({"gmail_ids": trimmed}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Filter helpers
    # ------------------------------------------------------------------

    def _is_security_blacklisted(self, subject: str, snippet: str) -> bool:
        """Return True if this looks like an OTP / security-code email.

        Matches against a curated keyword list in subject + snippet (case-insensitive).
        """
        haystack = f"{subject} {snippet}".lower()
        return any(kw in haystack for kw in SECURITY_BLACKLIST)

    def _is_digest_blacklisted(self, sender: str) -> bool:
        """Return True if the sender belongs to a blacklisted digest service."""
        sender_lower = sender.lower()
        return any(domain in sender_lower for domain in DIGEST_BLACKLIST_DOMAINS)

    # ------------------------------------------------------------------
    # Email body extraction
    # ------------------------------------------------------------------

    def _extract_body(self, payload: dict) -> str:
        """Extract readable plain-text body from a Gmail message payload.

        Preference order: text/plain → text/html (tags stripped) → empty string.
        Handles simple, multipart, and nested-multipart MIME structures.
        """

        def _decode(part: dict) -> str | None:
            data = part.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
            return None

        def _strip_html(html: str) -> str:
            # Remove tags, collapse whitespace
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"[ \t]+", " ", text)
            return text.strip()

        def _walk(p: dict) -> str:
            mime = p.get("mimeType", "")

            if mime == "text/plain":
                return _decode(p) or ""

            if mime == "text/html":
                return _strip_html(_decode(p) or "")

            # Multipart: prefer text/plain part
            parts = p.get("parts", [])
            for part in parts:
                if part.get("mimeType") == "text/plain":
                    body = _decode(part)
                    if body:
                        return body

            # Fallback to HTML part
            for part in parts:
                if part.get("mimeType") == "text/html":
                    return _strip_html(_decode(part) or "")

            # Recurse into nested multipart
            for part in parts:
                result = _walk(part)
                if result:
                    return result

            return ""

        return _walk(payload)

    # ------------------------------------------------------------------
    # BaseWatcher interface
    # ------------------------------------------------------------------

    def check_for_updates(self) -> list[Any]:
        """Query Gmail API and return new unread important messages.

        Applies the Gmail search query and deduplication (processed IDs).
        Returns full message dicts — each is passed to create_action_file().
        """
        if self._service is None:
            return []

        processed_ids = self._load_processed_ids()
        new_messages: list[dict] = []

        try:
            result = (
                self._service.users()
                .messages()
                .list(userId="me", q=self.query, maxResults=50)
                .execute()
            )
        except HttpError as e:
            log_action(
                self.logs, "gmail_api_error", "GmailWatcher",
                result="error", details=f"messages.list() failed: {e}",
            )
            return []

        for msg in result.get("messages", []):
            msg_id = msg["id"]
            if msg_id in processed_ids:
                continue  # Already processed — skip

            try:
                full = (
                    self._service.users()
                    .messages()
                    .get(userId="me", id=msg_id, format="full")
                    .execute()
                )
                new_messages.append(full)
            except HttpError as e:
                log_action(
                    self.logs, "gmail_fetch_error", "GmailWatcher",
                    result="error",
                    details=f"messages.get({msg_id}) failed: {e}",
                )

        return new_messages

    def create_action_file(self, item: Any) -> Path:
        """Create an EMAIL_<id>.md action file from a Gmail message dict.

        Filter pipeline:
            1. Security blacklist check (OTP / verification codes) → drop silently
            2. Digest blacklist check (Instagram, Facebook, etc.) → drop silently
            3. Write EMAIL_<id>.md to Needs_Action with YAML frontmatter

        Returns the intended destination path in all cases.
        """
        msg_id: str = item["id"]
        thread_id: str = item.get("threadId", "")
        snippet: str = item.get("snippet", "")
        labels: list[str] = item.get("labelIds", [])
        payload: dict = item.get("payload", {})

        # Extract headers
        headers: dict[str, str] = {
            h["name"].lower(): h["value"]
            for h in payload.get("headers", [])
        }
        subject: str = headers.get("subject", "(no subject)")
        sender: str = headers.get("from", "unknown")
        to: str = headers.get("to", "")
        date_str: str = headers.get("date", "")

        dest = self.needs_action / f"EMAIL_{msg_id}.md"

        # ---------------------------------------------------------------
        # Filter 1: Security blacklist — OTP / verification codes
        # ---------------------------------------------------------------
        if self._is_security_blacklisted(subject, snippet):
            log_action(
                self.logs, "gmail_filtered_security", "GmailWatcher",
                source=sender,
                details=f"[SECURITY] Blocked OTP/auth email — Subject: {subject[:80]}",
            )
            self._save_processed_id(msg_id)
            return dest  # Return path without writing

        # ---------------------------------------------------------------
        # Filter 2: Digest blacklist — social media digests
        # ---------------------------------------------------------------
        if self._is_digest_blacklisted(sender):
            log_action(
                self.logs, "gmail_filtered_digest", "GmailWatcher",
                source=sender,
                details=f"[DIGEST] Blocked digest email — Subject: {subject[:80]}",
            )
            self._save_processed_id(msg_id)
            return dest  # Return path without writing

        # ---------------------------------------------------------------
        # Determine priority
        # ---------------------------------------------------------------
        urgent_keywords = ("urgent", "asap", "critical", "deadline", "emergency")
        if any(kw in subject.lower() for kw in urgent_keywords):
            priority = "urgent"
        elif "IMPORTANT" in labels:
            priority = "high"
        else:
            priority = "normal"

        # ---------------------------------------------------------------
        # Extract body (text/plain preferred)
        # ---------------------------------------------------------------
        body = self._extract_body(payload)
        if len(body) > 5000:
            body = body[:5000] + "\n\n[… truncated — open in Gmail for full email]"

        # ---------------------------------------------------------------
        # Check for attachments
        # ---------------------------------------------------------------
        has_attachments = any(
            part.get("filename") for part in payload.get("parts", [])
        )

        # ---------------------------------------------------------------
        # DRY_RUN — log intent, don't write
        # ---------------------------------------------------------------
        if DRY_RUN:
            log_action(
                self.logs, "gmail_email_processed", "GmailWatcher",
                source=sender,
                destination=dest.name,
                result="dry_run",
                details=f"Subject: {subject[:80]}",
            )
            self._save_processed_id(msg_id)
            return dest

        # ---------------------------------------------------------------
        # Write action file
        # ---------------------------------------------------------------
        now = datetime.now(timezone.utc).isoformat()

        frontmatter = (
            f"---\n"
            f"type: email\n"
            f"message_id: {msg_id}\n"
            f"thread_id: {thread_id}\n"
            f'from: "{sender}"\n'
            f'to: "{to}"\n'
            f'subject: "{subject}"\n'
            f'received_at: "{date_str}"\n'
            f"created_at: {now}\n"
            f"status: needs_action\n"
            f"priority: {priority}\n"
            f"labels: {json.dumps(labels)}\n"
            f"has_attachments: {str(has_attachments).lower()}\n"
            f"source: Gmail\n"
            f"processed_by: null\n"
            f"---\n\n"
        )

        body_section = (
            f"## Subject\n{subject}\n\n"
            f"## From\n{sender}\n\n"
            f"## Snippet\n{snippet}\n\n"
            f"## Body\n{body}\n"
        )

        dest.write_text(frontmatter + body_section, encoding="utf-8")
        self._save_processed_id(msg_id)

        log_action(
            self.logs, "gmail_email_processed", "GmailWatcher",
            source=sender,
            destination=dest.name,
            result="success",
            details=f"Subject: {subject[:80]} | Priority: {priority}",
        )
        update_dashboard(self.vault_path, {"GmailWatcher": "Online"})

        return dest

    # ------------------------------------------------------------------
    # Lifecycle — override start/stop to add auth + dashboard updates
    # ------------------------------------------------------------------

    def start(self) -> Self:
        """Authenticate with Gmail, then start the polling loop."""
        try:
            self._service = self._authenticate()
            log_action(
                self.logs, "gmail_auth_ok", "GmailWatcher",
                result="success",
                details=f"Authenticated | Query: {self.query}",
            )
        except FileNotFoundError as e:
            log_action(
                self.logs, "gmail_auth_failed", "GmailWatcher",
                result="error", details=str(e),
            )
            raise
        except Exception as e:
            log_action(
                self.logs, "gmail_auth_failed", "GmailWatcher",
                result="error", details=f"Unexpected auth error: {e}",
            )
            raise

        log_action(
            self.logs, "watcher_started", "GmailWatcher",
            details=f"Polling every {self.check_interval}s",
        )
        update_dashboard(self.vault_path, {"GmailWatcher": "Online"})

        # Start the inherited polling loop in a background thread
        return super().start()

    def stop(self) -> None:
        """Stop the polling loop and update dashboard."""
        super().stop()
        log_action(
            self.logs, "watcher_stopped", "GmailWatcher",
            details="Shutdown complete",
        )
        update_dashboard(self.vault_path, {"GmailWatcher": "Offline"})


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="GmailWatcher — OAuth setup and manual controls",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  uv run python gmail_watcher.py --auth-only   # First-time OAuth setup\n"
        ),
    )
    parser.add_argument(
        "--auth-only",
        action="store_true",
        help=(
            "Run the Gmail OAuth flow (opens browser), save token to "
            ".secrets/gmail_token.json, then exit. "
            "Required after changing SCOPES or rotating credentials."
        ),
    )
    args = parser.parse_args()

    vault = Path(__file__).parent / "AI_Employee_Vault"
    watcher = GmailWatcher(vault)

    if args.auth_only:
        print("[gmail_watcher] Running OAuth flow — browser will open...")
        watcher._authenticate()
        print(
            f"[gmail_watcher] Authentication complete. "
            f"Token saved to: {watcher.token_path}"
        )
        sys.exit(0)

    parser.print_help()
    sys.exit(0)
