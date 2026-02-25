# Bronze-tier Gmail Watcher for Digital FTE
# Polls for unread/important emails → creates .md in data/Needs_Action/

import os
import base64
import logging
import time
import pickle
import argparse
from pathlib import Path
from datetime import datetime
from random import uniform
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# ── CONFIG ────────────────────────────────────────────────────────────────
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
VAULT_DIR = Path(__file__).parent.parent.resolve()
CREDENTIALS_FILE = VAULT_DIR / 'credentials.json'
TOKEN_FILE = VAULT_DIR / 'token.json'
NEEDS_ACTION_DIR = VAULT_DIR / 'data' / 'Needs_Action'
LOG_DIR = VAULT_DIR / 'data' / 'Logs'
LOG_FILE = LOG_DIR / 'gmail_watcher.log'
PROCESSED_IDS_FILE = VAULT_DIR / 'data' / 'gmail_processed_ids.pkl'

CHECK_INTERVAL_SECONDS = 120
QUERY = 'is:unread is:important'  # customize: 'is:unread label:urgent', etc.

# ── LOGGING ───────────────────────────────────────────────────────────────
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)
logger = logging.getLogger('GmailWatcher')

# ── AUTH ──────────────────────────────────────────────────────────────────
def get_gmail_service():
    """Authenticate with Gmail API. Opens browser for OAuth on first run."""
    creds = None

    # Load existing token if available
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    # If no valid creds, refresh or run OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired token...")
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                logger.error(f"credentials.json not found at {CREDENTIALS_FILE}")
                logger.error("Download it from Google Cloud Console → APIs & Services → Credentials")
                raise FileNotFoundError(f"credentials.json not found at {CREDENTIALS_FILE}")

            logger.info("No valid token found. Starting OAuth flow (browser will open)...")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)
            logger.info("OAuth flow completed successfully!")

        # Save token for future runs
        TOKEN_FILE.write_text(creds.to_json())
        logger.info(f"Token saved to {TOKEN_FILE}")

    return build('gmail', 'v1', credentials=creds)

# ── RETRY LOGIC ──────────────────────────────────────────────────────────
def with_backoff(max_attempts=5, base_delay=1):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    delay = base_delay * (2 ** attempt) + uniform(0, 0.1)
                    logger.warning(f"Attempt {attempt+1} failed: {e}. Retrying in {delay:.1f}s...")
                    time.sleep(delay)
        return wrapper
    return decorator

# ── MAIN WATCHER LOGIC ────────────────────────────────────────────────────
class GmailWatcher:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.service = get_gmail_service()
        self.load_processed_ids()
        NEEDS_ACTION_DIR.mkdir(parents=True, exist_ok=True)

    def load_processed_ids(self):
        if PROCESSED_IDS_FILE.exists():
            with open(PROCESSED_IDS_FILE, 'rb') as f:
                self.processed_ids = pickle.load(f)
        else:
            self.processed_ids = set()

    def save_processed_ids(self):
        with open(PROCESSED_IDS_FILE, 'wb') as f:
            pickle.dump(self.processed_ids, f)

    def run(self):
        logger.info("Gmail Watcher started. Polling every %d seconds...", CHECK_INTERVAL_SECONDS)
        while True:
            try:
                self.check_for_new_emails()
            except Exception as e:
                logger.exception("Error during poll: %s", e)
            time.sleep(CHECK_INTERVAL_SECONDS)

    @with_backoff()
    def check_for_new_emails(self):
        results = self.service.users().messages().list(
            userId='me',
            q=QUERY,
            maxResults=10  # limit per poll
        ).execute()

        messages = results.get('messages', [])
        if not messages:
            logger.debug("No new matching emails.")
            return

        for msg in messages:
            msg_id = msg['id']
            if msg_id in self.processed_ids:
                continue

            self.process_email(msg_id)
            self.service.users().messages().modify(
                userId='me',
                id=msg_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
            logger.info(f"Marked email {msg_id} as read")
            self.processed_ids.add(msg_id)
            self.save_processed_ids()

    def process_email(self, msg_id):
        msg = self.service.users().messages().get(
            userId='me', id=msg_id, format='full'
        ).execute()

        # Extract headers
        headers = {}
        for header in msg['payload']['headers']:
            headers[header['name']] = header['value']

        from_ = headers.get('From', 'Unknown')
        subject = headers.get('Subject', 'No Subject')
        date_str = headers.get('Date', datetime.now().isoformat())

        # Get snippet (preview text)
        snippet = msg.get('snippet', '')

        # Optional: get full plain text body (basic)
        body = ""
        if 'parts' in msg['payload']:
            for part in msg['payload']['parts']:
                if part.get('mimeType') == 'text/plain':
                    data = part['body'].get('data')
                    if data:
                        body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                    break

        # Build markdown content (matches hackathon spec style)
        content = f"""---
type: email
from: {from_}
subject: {subject}
received: {date_str}
message_id: {msg_id}
priority: high
status: pending
---

## Email Content (snippet)
{snippet}

## Full Body (plain text excerpt)
{body[:800]}... (truncated)

## Suggested Actions
- [ ] Reply
- [ ] Forward
- [ ] Archive after processing
- [ ] Flag for human review
"""

        # Save to Needs_Action
        filename = f"EMAIL_{msg_id}.md"

        if self.dry_run:
            logger.info(f"[DRY RUN] Would create {filename}")
            return

        filepath = NEEDS_ACTION_DIR / filename
        filepath.write_text(content, encoding='utf-8')

        logger.info("Created task file: %s | From: %s | Subject: %s", filename, from_, subject)

# ── ENTRY POINT ───────────────────────────────────────────────────────────
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Gmail Watcher - polls for unread/important emails")
    parser.add_argument('--dry-run', action='store_true', help="Log actions but don't write files")
    args = parser.parse_args()
    watcher = GmailWatcher(dry_run=args.dry_run)
    watcher.run()