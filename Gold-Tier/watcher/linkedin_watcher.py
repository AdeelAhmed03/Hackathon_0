#!/usr/bin/env python3
"""
LinkedIn Watcher (Silver Tier)

Polls the LinkedIn API for new mentions, comments, and interactions on the
authenticated user's posts.  When a new interaction is found it creates a
structured .md task file in data/Needs_Action/.

Also triggers a daily LinkedIn draft generation via skill-linkedin-draft
by creating a SCHEDULED_linkedin_draft task file once per day.

Requires:
    pip install linkedin-api python-dotenv

Environment:
    LINKEDIN_TOKEN          – OAuth access token (in .env, gitignored)
    LINKEDIN_PERSON_URN     – urn:li:person:<id>
    LINKEDIN_CHECK_INTERVAL – poll interval in seconds (default 3600)
    LINKEDIN_DRAFT_HOUR     – hour (0-23) to trigger daily draft (default 9)
    LINKEDIN_DRY_RUN        – "true" to log without writing files
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from random import uniform

# ── Env loading ───────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # env vars may be set externally

# ── CONFIG ────────────────────────────────────────────────────────────────
VAULT_DIR = Path(__file__).parent.parent.resolve()
LOGS_DIR = VAULT_DIR / "data" / "Logs"
LOG_FILE = LOGS_DIR / "linkedin_watcher.log"
NEEDS_ACTION_DIR = VAULT_DIR / "data" / "Needs_Action"
STATE_FILE = LOGS_DIR / "linkedin_watcher_state.json"

LINKEDIN_TOKEN = os.environ.get("LINKEDIN_TOKEN", "")
LINKEDIN_PERSON_URN = os.environ.get("LINKEDIN_PERSON_URN", "")
CHECK_INTERVAL = int(os.environ.get("LINKEDIN_CHECK_INTERVAL", "3600"))
DRAFT_HOUR = int(os.environ.get("LINKEDIN_DRAFT_HOUR", "9"))
DRY_RUN_ENV = os.environ.get("LINKEDIN_DRY_RUN", "false").lower() == "true"


# ── LOGGING SETUP ─────────────────────────────────────────────────────────
def setup_logging() -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger("LinkedInWatcher")


logger = setup_logging()


# ── RETRY HELPER (matches gmail_watcher pattern) ─────────────────────────
def with_backoff(max_attempts: int = 3, base_delay: float = 2):
    """Decorator: retry with exponential backoff + jitter."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as exc:
                    if attempt == max_attempts - 1:
                        raise
                    delay = base_delay * (2 ** attempt) + uniform(0, 0.5)
                    logger.warning(
                        "Attempt %d/%d failed: %s. Retrying in %.1fs ...",
                        attempt + 1, max_attempts, exc, delay,
                    )
                    time.sleep(delay)
        return wrapper
    return decorator


# ══════════════════════════════════════════════════════════════════════════
#  STATE MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════
def load_state() -> dict:
    """Load watcher state (processed IDs + last draft date)."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("State file corrupt, starting fresh: %s", exc)
    return {"processed_ids": [], "last_draft_date": None, "last_check": None}


def save_state(state: dict) -> None:
    """Persist watcher state to JSON."""
    state["last_check"] = datetime.now(timezone.utc).isoformat()
    try:
        STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.error("Failed to save state: %s", exc)


# ══════════════════════════════════════════════════════════════════════════
#  LINKEDIN API CLIENT
# ══════════════════════════════════════════════════════════════════════════
COOKIES_FILE = LOGS_DIR / "linkedin_cookies.json"


class LinkedInClient:
    """Thin wrapper for reading LinkedIn interactions via REST API.

    Authentication methods (tried in order):
      1. Cookie-based auth from linkedin_cookies.json (created by linkedin_auth.py)
      2. Bearer token from LINKEDIN_TOKEN env var
      3. Falls back to DEMO mode with mock data
    """

    def __init__(self, token: str, person_urn: str) -> None:
        self.token = token
        self.person_urn = person_urn
        self._session = None
        self._api_base = "https://api.linkedin.com/v2"
        self._demo_mode = False

        # Try cookie auth first, then Bearer token, then demo mode
        if self._load_cookies():
            logger.info("LinkedIn API client initialised (cookie auth)")
        elif token and not token.startswith("your_"):
            self._init_bearer(token)
            logger.info("LinkedIn API client initialised (Bearer token)")
        else:
            logger.warning(
                "No LinkedIn credentials found. "
                "Run: python watcher/linkedin_auth.py  — "
                "Running in DEMO mode with mock data."
            )
            self._demo_mode = True

    def _load_cookies(self) -> bool:
        """Load session cookies from linkedin_cookies.json."""
        if not COOKIES_FILE.exists():
            return False
        try:
            import requests
            cookies = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))
            li_at = next((c for c in cookies if c["name"] == "li_at"), None)
            jsessionid = next((c for c in cookies if c["name"] == "JSESSIONID"), None)
            if not li_at:
                logger.warning("Cookie file exists but li_at cookie missing")
                return False

            self._session = requests.Session()
            for c in cookies:
                self._session.cookies.set(c["name"], c["value"], domain=c.get("domain", ""))

            csrf = jsessionid["value"].strip('"') if jsessionid else ""
            self._session.headers.update({
                "csrf-token": csrf,
                "X-Restli-Protocol-Version": "2.0.0",
                "Content-Type": "application/json",
            })
            return True
        except Exception as exc:
            logger.warning("Failed to load LinkedIn cookies: %s", exc)
            return False

    def _init_bearer(self, token: str) -> None:
        """Set up a requests Session with Bearer token auth."""
        import requests
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        })

    # ── API calls (with backoff) ──────────────────────────────────────
    @with_backoff(max_attempts=3, base_delay=5)
    def get_notifications(self) -> list[dict]:
        """Fetch recent notifications (mentions, comments, reactions).

        Returns a normalised list of dicts with keys:
            id, type, from_name, text, post_urn, timestamp
        """
        if self._demo_mode:
            return self._mock_notifications()

        try:
            # --- Fetch notification feed ---
            resp = self._session.get(
                f"{self._api_base}/socialActions?q=entity&entity={self.person_urn}"
                "&count=20&start=0",
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            notifications: list[dict] = []
            for element in data.get("elements", []):
                notifications.append(self._normalise(element))
            return notifications

        except Exception:
            logger.exception("Error fetching LinkedIn notifications, trying comments endpoint")
            return self._fetch_comments_fallback()

    @with_backoff(max_attempts=2, base_delay=3)
    def _fetch_comments_fallback(self) -> list[dict]:
        """Fallback: try the comments endpoint directly."""
        if self._demo_mode:
            return self._mock_notifications()

        try:
            resp = self._session.get(
                f"{self._api_base}/socialMetadata?q=entity&entity={self.person_urn}",
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            notifications: list[dict] = []
            for element in data.get("elements", []):
                notifications.append(self._normalise(element))
            return notifications
        except Exception:
            logger.exception("Comments fallback also failed")
            return []

    def _normalise(self, raw: dict) -> dict:
        """Normalise a LinkedIn API element into our standard shape."""
        actor = raw.get("actor", raw.get("commenter", ""))
        actor_name = actor if isinstance(actor, str) else str(actor)

        text = raw.get("commentary", raw.get("message", {}).get("text", ""))
        if isinstance(text, dict):
            text = text.get("text", str(text))

        return {
            "id": raw.get("$URN", raw.get("id", hashlib.sha256(
                json.dumps(raw, sort_keys=True, default=str).encode()
            ).hexdigest()[:16])),
            "type": raw.get("$type", "comment"),
            "from_name": actor_name,
            "text": str(text)[:500],
            "post_urn": raw.get("object", ""),
            "timestamp": raw.get("created", {}).get("time",
                         datetime.now(timezone.utc).isoformat()),
        }

    # ── Mock data for demo / dry-run ──────────────────────────────────
    @staticmethod
    def _mock_notifications() -> list[dict]:
        """Return sample data so dry-run works without API credentials."""
        now_iso = datetime.now(timezone.utc).isoformat()
        return [
            {
                "id": "mock_comment_001",
                "type": "comment",
                "from_name": "Jane Smith",
                "text": "Great insights on AI productivity! Would love to discuss further.",
                "post_urn": "urn:li:share:7000000001",
                "timestamp": now_iso,
            },
            {
                "id": "mock_mention_002",
                "type": "mention",
                "from_name": "Tech Startup Inc.",
                "text": "Mentioned you in a post about innovative AI solutions.",
                "post_urn": "urn:li:share:7000000002",
                "timestamp": now_iso,
            },
        ]


# ══════════════════════════════════════════════════════════════════════════
#  TASK FILE CREATION
# ══════════════════════════════════════════════════════════════════════════
def create_interaction_task(item: dict, dry_run: bool = False) -> bool:
    """Write a LINKEDIN_{id}.md file into data/Needs_Action/."""
    interaction_id = re.sub(r"[^\w\-]", "_", str(item["id"]))[:60]
    filename = f"LINKEDIN_{interaction_id}.md"
    filepath = NEEDS_ACTION_DIR / filename

    if filepath.exists():
        logger.debug("Task file already exists, skipping: %s", filename)
        return False

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    from_name = item["from_name"].replace('"', '\\"')
    text = item["text"].replace('"', '\\"')

    content = f"""---
type: linkedin
from: "{from_name}"
text: "{text}"
status: pending
interaction_type: {item["type"]}
post_urn: {item["post_urn"]}
linkedin_id: {item["id"]}
created: {now_iso}
---

## LinkedIn {item["type"].title()}

**From:** {item["from_name"]}
**Type:** {item["type"]}
**Post:** {item["post_urn"]}
**Received:** {item["timestamp"]}

## Content

{item["text"]}

## Suggested Actions
- [ ] Reply / comment back
- [ ] Like / react
- [ ] Forward to team
- [ ] Use as input for next LinkedIn draft (skill-linkedin-draft)
- [ ] Archive after processing
"""

    if dry_run:
        logger.info("[DRY RUN] Would create %s (from=%s)", filename, item["from_name"])
        return True

    NEEDS_ACTION_DIR.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content, encoding="utf-8")
    logger.info(
        "Created task: %s | from=%s | type=%s",
        filename, item["from_name"], item["type"],
    )
    return True


def create_daily_draft_task(dry_run: bool = False) -> bool:
    """Create a SCHEDULED_linkedin_draft task to trigger skill-linkedin-draft."""
    today = datetime.now().strftime("%Y%m%d")
    filename = f"SCHEDULED_linkedin_draft_{today}.md"
    filepath = NEEDS_ACTION_DIR / filename

    if filepath.exists():
        logger.info("Daily draft task already exists for today, skipping")
        return False

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    content = f"""---
type: scheduled_task
task_type: linkedin_draft
status: pending
scheduled_by: linkedin_watcher
scheduled_time: {now_iso}
created: {now_iso}
---

## Scheduled Task: LinkedIn Draft

This task was automatically created by linkedin_watcher.py (daily trigger).

**Action Required:** Generate a LinkedIn post draft for today.

**Post Type:** thought_leadership
**Goal:** Boost sales engagement and professional visibility

Use skill-linkedin-draft to generate the draft content.
The draft will require HITL approval before posting.
"""

    if dry_run:
        logger.info("[DRY RUN] Would create daily draft task: %s", filename)
        return True

    NEEDS_ACTION_DIR.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content, encoding="utf-8")
    logger.info("Created daily draft task: %s", filename)
    return True


# ══════════════════════════════════════════════════════════════════════════
#  MAIN WATCHER
# ══════════════════════════════════════════════════════════════════════════
class LinkedInWatcher:
    """Polls LinkedIn API for interactions and triggers daily drafts."""

    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run or DRY_RUN_ENV
        self.state = load_state()
        self.processed_ids: set[str] = set(self.state.get("processed_ids", []))
        self.client = LinkedInClient(LINKEDIN_TOKEN, LINKEDIN_PERSON_URN)

    def check_interactions(self) -> None:
        """One poll cycle: fetch notifications, dedup, create task files."""
        logger.info("Checking LinkedIn for new interactions ...")
        notifications = self.client.get_notifications()

        new_count = 0
        for item in notifications:
            item_id = str(item["id"])
            if item_id in self.processed_ids:
                continue

            created = create_interaction_task(item, dry_run=self.dry_run)
            if created:
                new_count += 1
            self.processed_ids.add(item_id)

        if new_count:
            logger.info("Processed %d new interaction(s)", new_count)
        else:
            logger.info("No new interactions")

        self._save()

    def check_daily_draft(self) -> None:
        """Trigger skill-linkedin-draft once per day at DRAFT_HOUR."""
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        last_draft = self.state.get("last_draft_date")

        if last_draft == today_str:
            return  # already triggered today

        if now.hour >= DRAFT_HOUR:
            logger.info("Daily draft trigger: generating linkedin_draft task")
            created = create_daily_draft_task(dry_run=self.dry_run)
            if created:
                self.state["last_draft_date"] = today_str
                self._save()

    def _save(self) -> None:
        """Persist state."""
        self.state["processed_ids"] = sorted(self.processed_ids)
        save_state(self.state)

    def run(self, interval: int) -> None:
        """Blocking poll loop."""
        mode = "DRY RUN" if self.dry_run else "ACTIVE"
        logger.info("LinkedIn Watcher started (%s)", mode)
        logger.info("Poll interval: %ds | Draft hour: %02d:00", interval, DRAFT_HOUR)
        logger.info("Person URN: %s", LINKEDIN_PERSON_URN or "(not set)")
        logger.info(
            "Token: %s",
            "configured" if LINKEDIN_TOKEN and not LINKEDIN_TOKEN.startswith("your_") else "NOT SET (demo mode)",
        )

        try:
            while True:
                try:
                    self.check_interactions()
                    self.check_daily_draft()
                except Exception:
                    logger.exception("Error during poll cycle")
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("LinkedIn Watcher stopped by user")
        finally:
            self._save()
            logger.info("Final state saved")


# ══════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════
def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "LinkedIn Watcher - polls LinkedIn API for mentions/comments "
            "and triggers daily draft generation via skill-linkedin-draft"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log actions without creating task files or calling API",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=CHECK_INTERVAL,
        help=f"Poll interval in seconds (default: {CHECK_INTERVAL})",
    )
    parser.add_argument(
        "--force-draft",
        action="store_true",
        help="Immediately create a daily draft task (bypass time check)",
    )
    parser.add_argument(
        "--list-state",
        action="store_true",
        help="Print current state and exit",
    )

    args = parser.parse_args()

    # ── --list-state ──────────────────────────────────────────────────
    if args.list_state:
        state = load_state()
        print(json.dumps(state, indent=2))
        return

    dry_run = args.dry_run or DRY_RUN_ENV

    # ── --force-draft ─────────────────────────────────────────────────
    if args.force_draft:
        logger.info("Force-triggering daily LinkedIn draft task")
        create_daily_draft_task(dry_run=dry_run)
        state = load_state()
        state["last_draft_date"] = datetime.now().strftime("%Y-%m-%d")
        save_state(state)
        return

    # ── Normal operation ──────────────────────────────────────────────
    if not LINKEDIN_TOKEN or LINKEDIN_TOKEN.startswith("your_"):
        logger.warning(
            "LINKEDIN_TOKEN not set in .env — running in DEMO mode. "
            "API calls will return mock data."
        )

    watcher = LinkedInWatcher(dry_run=dry_run)
    watcher.run(interval=args.interval)


if __name__ == "__main__":
    main()
