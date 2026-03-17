"""Gmail Watcher — monitors unread/important emails and writes them to the vault."""

import logging
import os
import pickle
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.retry_handler import TransientError, with_retry
from .base_watcher import BaseWatcher

logger = logging.getLogger(__name__)

# Read-only Gmail scope (never sends, never deletes)
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class GmailWatcher(BaseWatcher):
    """Monitors Gmail for unread/important messages and creates action files.

    Setup:
        1. Enable Gmail API in Google Cloud Console
        2. Download credentials.json (OAuth2 desktop client)
        3. Set GMAIL_CREDENTIALS_PATH and GMAIL_TOKEN_PATH in .env
        4. Run once manually to complete OAuth flow (browser will open)

    Configuration (.env):
        GMAIL_CREDENTIALS_PATH: path to credentials.json
        GMAIL_TOKEN_PATH: path to token.json (created on first run)
        GMAIL_MAX_RESULTS: max emails per check cycle (default: 10)
        GMAIL_CHECK_INTERVAL: seconds between checks (default: 120)
    """

    def __init__(self, vault_path: str):
        check_interval = int(os.getenv("GMAIL_CHECK_INTERVAL", "120"))
        super().__init__(vault_path, check_interval)
        self.credentials_path = Path(os.getenv("GMAIL_CREDENTIALS_PATH", "credentials.json"))
        self.token_path = Path(os.getenv("GMAIL_TOKEN_PATH", "token.json"))
        self.max_results = int(os.getenv("GMAIL_MAX_RESULTS", "10"))
        self._processed_ids: set[str] = set()
        self._service = None

    def _get_service(self):
        """Authenticate and return Gmail API service (cached)."""
        if self._service:
            return self._service

        creds = None
        if self.token_path.exists():
            with open(self.token_path, "rb") as f:
                creds = pickle.load(f)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not self.credentials_path.exists():
                    raise FileNotFoundError(
                        f"Gmail credentials not found at: {self.credentials_path}\n"
                        "Download from Google Cloud Console → APIs & Services → Credentials."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_path), SCOPES
                )
                creds = flow.run_local_server(port=0)

            with open(self.token_path, "wb") as f:
                pickle.dump(creds, f)

        self._service = build("gmail", "v1", credentials=creds)
        logger.info("Gmail API authenticated successfully.")
        return self._service

    @with_retry(max_attempts=3)
    def _fetch_messages(self) -> list[dict]:
        """Fetch unread or important messages from Gmail."""
        try:
            service = self._get_service()
            result = service.users().messages().list(
                userId="me",
                q="is:unread is:important",
                maxResults=self.max_results,
            ).execute()
            return result.get("messages", [])
        except HttpError as e:
            if e.resp.status in (429, 500, 503):
                raise TransientError(f"Gmail API transient error {e.resp.status}: {e}")
            raise

    @with_retry(max_attempts=3)
    def _get_message_detail(self, message_id: str) -> dict:
        """Fetch full message detail by ID."""
        try:
            service = self._get_service()
            return service.users().messages().get(
                userId="me",
                id=message_id,
                format="full",
            ).execute()
        except HttpError as e:
            if e.resp.status in (429, 500, 503):
                raise TransientError(f"Gmail API transient error {e.resp.status}: {e}")
            raise

    def _extract_body(self, payload: dict) -> str:
        """Extract plain text body from message payload."""
        import base64

        def decode_part(data: str) -> str:
            try:
                return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
            except Exception:
                return ""

        mime_type = payload.get("mimeType", "")
        body_data = payload.get("body", {}).get("data", "")

        if mime_type == "text/plain" and body_data:
            return decode_part(body_data)

        if mime_type.startswith("multipart/"):
            for part in payload.get("parts", []):
                if part.get("mimeType") == "text/plain":
                    data = part.get("body", {}).get("data", "")
                    if data:
                        return decode_part(data)
            # Fall back to any part with data
            for part in payload.get("parts", []):
                text = self._extract_body(part)
                if text:
                    return text

        return ""

    def _parse_message(self, raw: dict) -> dict:
        """Convert raw Gmail API message into a normalized item dict."""
        headers = {h["name"].lower(): h["value"] for h in raw.get("payload", {}).get("headers", [])}
        subject = headers.get("subject", "(no subject)")
        sender = headers.get("from", "unknown")
        date = headers.get("date", "")
        body = self._extract_body(raw.get("payload", {}))
        snippet = raw.get("snippet", "")
        labels = raw.get("labelIds", [])

        body_preview = (body[:2000] + "...[truncated]") if len(body) > 2000 else body

        return {
            "id": raw["id"],
            "type": "EMAIL",
            "summary": f"Email from {sender}: {subject}",
            "body": (
                f"**From:** {sender}\n"
                f"**Date:** {date}\n"
                f"**Subject:** {subject}\n\n"
                f"---\n\n"
                f"{body_preview or snippet}\n\n"
                f"## Suggested Actions\n"
                f"- [ ] Reply to sender\n"
                f"- [ ] Forward to relevant party\n"
                f"- [ ] Archive after processing\n"
            ),
            "metadata": {
                "from": sender,
                "subject": subject,
                "received": date,
                "priority": "high",
                "labels": ",".join(labels),
                "gmail_id": raw["id"],
                "thread_id": raw.get("threadId", ""),
            },
        }

    def check_for_updates(self) -> list[dict]:
        """Fetch new unread/important emails not yet processed."""
        messages = self._fetch_messages()
        new_items = []

        for msg_ref in messages:
            msg_id = msg_ref["id"]
            if msg_id in self._processed_ids:
                continue

            raw = self._get_message_detail(msg_id)
            item = self._parse_message(raw)
            new_items.append(item)
            self._processed_ids.add(msg_id)

        return new_items


def main():
    import sys
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    vault = os.getenv("VAULT_PATH")
    if not vault:
        print("ERROR: Set VAULT_PATH in .env")
        sys.exit(1)

    GmailWatcher(vault).run()


if __name__ == "__main__":
    main()
