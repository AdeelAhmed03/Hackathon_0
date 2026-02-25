#!/usr/bin/env python3
"""
WhatsApp Watcher (Silver Tier)

Monitors WhatsApp Web via Playwright for unread messages matching business
keywords, then creates structured .md task files in data/Needs_Action/.

Requires: pip install playwright && python -m playwright install chromium

IMPORTANT — Terms of Service Notice:
  WhatsApp's ToS prohibit automated/non-personal use of WhatsApp Web.
  This watcher is for HACKATHON DEMONSTRATION PURPOSES ONLY.
  A production system should use the official WhatsApp Business API.
  A warning is logged on every startup.
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
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

# ── CONFIG ────────────────────────────────────────────────────────────────
VAULT_DIR = Path(__file__).parent.parent.resolve()
LOGS_DIR = VAULT_DIR / "data" / "Logs"
LOG_FILE = LOGS_DIR / "whatsapp_watcher.log"
# Platinum: Route to local zone — WhatsApp requires local secrets (Playwright session)
NEEDS_ACTION_DIR = VAULT_DIR / "data" / "Needs_Action" / "local"
STATE_FILE = LOGS_DIR / "whatsapp_processed.json"
USER_DATA_DIR = VAULT_DIR / ".whatsapp_session"

CHECK_INTERVAL = int(os.environ.get("WHATSAPP_CHECK_INTERVAL_SECONDS", "30"))
KEYWORDS: list[str] = [
    kw.strip()
    for kw in os.environ.get(
        "WHATSAPP_KEYWORDS", "urgent,asap,invoice,payment,help"
    ).split(",")
    if kw.strip()
]

TOS_WARNING = (
    "WARNING: WhatsApp's Terms of Service prohibit automated access to "
    "WhatsApp Web. This watcher is for HACKATHON / EDUCATIONAL purposes "
    "only. For production use, migrate to the official WhatsApp Business "
    "API (https://developers.facebook.com/docs/whatsapp)."
)


# ── LOGGING SETUP ─────────────────────────────────────────────────────────
def setup_logging() -> logging.Logger:
    """Configure dual logging — file + stdout."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger("WhatsAppWatcher")


logger = setup_logging()


# ══════════════════════════════════════════════════════════════════════════
#  BASE WATCHER (abstract — shared contract with gmail_watcher pattern)
# ══════════════════════════════════════════════════════════════════════════
class BaseWatcher(ABC):
    """Abstract watcher that all vault watchers can extend.

    Mirrors the polling-loop pattern used by GmailWatcher in
    watcher/gmail_watcher.py:
      __init__  → authenticate / set up client
      run       → infinite loop calling check()
      check     → one poll cycle (find new items → process each)
      process   → handle a single item (create .md, log, etc.)
    """

    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run
        self.processed_ids: set[str] = set()

    # ── persistence ────────────────────────────────────────────────────
    def load_state(self, path: Path) -> None:
        """Load previously-processed IDs from a JSON file."""
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self.processed_ids = set(data.get("processed_ids", []))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("State file corrupt, starting fresh: %s", exc)
                self.processed_ids = set()
        else:
            self.processed_ids = set()

    def save_state(self, path: Path) -> None:
        """Persist processed IDs to JSON."""
        try:
            path.write_text(
                json.dumps(
                    {"processed_ids": sorted(self.processed_ids),
                     "last_saved": datetime.now(timezone.utc).isoformat()},
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.error("Failed to save state: %s", exc)

    # ── interface ──────────────────────────────────────────────────────
    @abstractmethod
    def check(self) -> None:
        """Run one poll cycle — find new items and process each."""

    @abstractmethod
    def process(self, item: dict) -> None:
        """Handle a single incoming item (message, email, etc.)."""

    def run(self, interval: int) -> None:
        """Blocking poll loop. Ctrl-C to stop."""
        mode = "DRY RUN" if self.dry_run else "ACTIVE"
        logger.info("Watcher started (%s). Polling every %ds …", mode, interval)
        try:
            while True:
                try:
                    self.check()
                except Exception:
                    logger.exception("Error during poll cycle")
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("Watcher stopped by user")


# ══════════════════════════════════════════════════════════════════════════
#  WHATSAPP WATCHER
# ══════════════════════════════════════════════════════════════════════════
class WhatsAppWatcher(BaseWatcher):
    """Polls WhatsApp Web for unread messages that match business keywords."""

    def __init__(self, dry_run: bool = False, headless: bool = True) -> None:
        super().__init__(dry_run=dry_run)
        self._headless = headless

        # Lazy-import so the module can be parsed even without playwright
        try:
            from playwright.sync_api import sync_playwright  # noqa: F401
        except ImportError:
            logger.error(
                "Playwright not installed. Run:\n"
                "  pip install playwright\n"
                "  python -m playwright install chromium"
            )
            sys.exit(1)

        NEEDS_ACTION_DIR.mkdir(parents=True, exist_ok=True)
        self.load_state(STATE_FILE)

        # Playwright objects — initialised in _launch_browser()
        self._pw = None
        self._browser = None
        self._context = None
        self.page = None

    # ── browser lifecycle ──────────────────────────────────────────────
    def _launch_browser(self) -> None:
        """Start a persistent Chromium context pointing at WhatsApp Web."""
        from playwright.sync_api import sync_playwright

        USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

        self._pw = sync_playwright().start()
        self._context = self._pw.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_DIR),
            headless=self._headless,
            # WhatsApp Web needs a real-looking UA to avoid blocks
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        self.page = self._context.pages[0] if self._context.pages else self._context.new_page()
        logger.info("Navigating to WhatsApp Web (headless=%s) …", self._headless)
        self.page.goto("https://web.whatsapp.com", wait_until="domcontentloaded", timeout=120_000)

    def _wait_for_login(self, timeout_seconds: int = 120) -> bool:
        """Wait for WhatsApp Web to finish loading / QR scan.

        On first run the user must scan the QR code manually (even in
        headless mode — set headless=False temporarily for first auth).
        Subsequent runs reuse the persistent session in user_data_dir.
        """
        logger.info(
            "Waiting for WhatsApp Web to load (timeout %ds). "
            "If this is your first run, set headless=False and scan the QR code.",
            timeout_seconds,
        )
        try:
            # The side panel (chat list) appears once logged in
            # Supports both old div-based and new grid/role-based layouts
            self.page.wait_for_selector(
                '[aria-label="Chat list"], [data-testid="chat-list"]',
                timeout=timeout_seconds * 1_000,
            )
            logger.info("WhatsApp Web session active")
            return True
        except Exception:
            logger.error(
                "WhatsApp Web did not load within %ds. "
                "Make sure you have scanned the QR code at least once "
                "with headless=False.",
                timeout_seconds,
            )
            return False

    def _shutdown_browser(self) -> None:
        """Gracefully close Playwright."""
        try:
            if self._context:
                self._context.close()
            if self._pw:
                self._pw.stop()
        except Exception:
            pass

    # ── keyword matching ───────────────────────────────────────────────
    @staticmethod
    def _matches_keywords(text: str) -> list[str]:
        """Return the list of matched keywords (case-insensitive)."""
        lower = text.lower()
        return [kw for kw in KEYWORDS if kw.lower() in lower]

    @staticmethod
    def _make_msg_id(chat_name: str, text: str, timestamp: str) -> str:
        """Deterministic dedup ID from message content."""
        raw = f"{chat_name}|{text}|{timestamp}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    # ── core polling ───────────────────────────────────────────────────
    def check(self) -> None:
        """One poll cycle: scrape unread chats, match keywords, process."""
        unread_chats = self._get_unread_chats()
        if not unread_chats:
            logger.debug("No unread chats with keyword matches")
            return

        for chat in unread_chats:
            msg_id = self._make_msg_id(chat["name"], chat["text"], chat["timestamp"])
            if msg_id in self.processed_ids:
                continue
            self.process(chat)
            self.processed_ids.add(msg_id)

        self.save_state(STATE_FILE)

    def _get_unread_chats(self) -> list[dict]:
        """Scrape the WhatsApp Web sidebar for unread conversations.

        Returns a list of dicts with keys: name, text, badge, timestamp, keywords.
        Only includes chats whose last message matches at least one keyword.
        """
        results: list[dict] = []

        try:
            # ── Strategy 1: role-based selectors (current WhatsApp Web 2025+) ──
            # WhatsApp Web now uses a grid with role="grid" or role="listbox"
            chat_rows = self.page.query_selector_all(
                '[aria-label="Chat list"] [role="row"], '
                '[aria-label="Chat list"] [role="listitem"], '
                '[data-testid="chat-list"] [role="row"], '
                '[data-testid="chat-list"] [role="listitem"]'
            )

            if not chat_rows:
                # ── Strategy 2: div-based selectors (legacy layouts) ──
                chat_rows = self.page.query_selector_all(
                    'div[aria-label="Chat list"] > div > div'
                )
            if not chat_rows:
                # ── Strategy 3: cell-frame containers ──
                chat_rows = self.page.query_selector_all(
                    'div[data-testid="chat-list"] div[data-testid="cell-frame-container"]'
                )

            logger.info("Found %d chat rows in sidebar", len(chat_rows))

            for row in chat_rows:
                # ── Detect unread badge ──
                # Modern: span with aria-label containing "unread"
                badge = row.query_selector('span[aria-label*="unread"]')
                if not badge:
                    badge = row.query_selector('span[data-testid="icon-unread-count"]')
                if not badge:
                    badge = row.query_selector('span.aumms1qt')
                if not badge:
                    # Fallback: any element whose aria-label contains "unread message"
                    badge = row.query_selector('[aria-label*="unread message"]')
                if not badge:
                    continue

                # Extract badge count from text content or aria-label
                badge_text = badge.inner_text().strip()
                if not badge_text:
                    # Try extracting number from aria-label like "11 unread messages"
                    badge_label = badge.get_attribute("aria-label") or ""
                    digits = re.findall(r"\d+", badge_label)
                    badge_text = digits[0] if digits else ""
                if not badge_text or not badge_text.isdigit():
                    continue

                # ── Extract chat name ──
                title_el = row.query_selector('span[title]')
                if not title_el:
                    title_el = row.query_selector('span[dir="auto"]')
                chat_name = ""
                if title_el:
                    chat_name = title_el.get_attribute("title") or ""
                    if not chat_name:
                        chat_name = title_el.inner_text().strip()
                chat_name = chat_name or "Unknown"

                # ── Extract last message preview ──
                msg_text = ""
                # Try multiple selectors for the message preview
                for sel in [
                    'span[data-testid="last-msg-status"] ~ span',
                    'div[data-testid="cell-frame-secondary"] span[title]',
                    'span[data-testid="last-msg-status"] + span',
                    'span.matched-text',
                    'span._11JPr',
                ]:
                    msg_el = row.query_selector(sel)
                    if msg_el:
                        msg_text = msg_el.inner_text().strip()
                        if msg_text:
                            break

                # If no message text found via selectors, try getting all text
                # from the secondary frame area
                if not msg_text:
                    secondary = row.query_selector(
                        'div[data-testid="cell-frame-secondary"], '
                        '[role="gridcell"]:nth-child(2)'
                    )
                    if secondary:
                        msg_text = secondary.inner_text().strip()
                        # Remove timestamp from the text (usually first line)
                        lines = msg_text.split("\n")
                        if len(lines) > 1:
                            msg_text = " ".join(lines[1:]).strip()

                # ── Extract timestamp ──
                ts_text = ""
                ts_el = row.query_selector(
                    'div[data-testid="cell-frame-primary-detail"] span, '
                    'span[data-testid="cell-frame-primary-detail"]'
                )
                if ts_el:
                    ts_text = ts_el.inner_text().strip()

                logger.info(
                    "Chat: name=%s | badge=%s | preview=%s",
                    chat_name, badge_text, msg_text[:60],
                )

                # ── Match keywords ──
                matched = self._matches_keywords(msg_text)
                if matched:
                    results.append({
                        "name": chat_name,
                        "text": msg_text,
                        "badge": badge_text,
                        "timestamp": ts_text or datetime.now().strftime("%H:%M"),
                        "keywords": matched,
                    })
                    logger.info("  → MATCHED keywords: %s", matched)

        except Exception:
            logger.exception("Error scraping WhatsApp Web sidebar")

        return results

    # ── process a single matched chat ──────────────────────────────────
    def process(self, item: dict) -> None:
        """Create a .md task file in data/Needs_Action/ for one chat."""
        chat_name = item["name"]
        msg_text = item["text"]
        keywords = item["keywords"]
        badge = item["badge"]
        ts = item["timestamp"]

        # Sanitise chat name for filename
        safe_name = re.sub(r"[^\w\-]", "_", chat_name)[:40]
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        chat_id = f"{safe_name}_{date_str}"
        filename = f"WHATSAPP_{chat_id}.md"

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        content = f"""---
type: whatsapp
action: reply_whatsapp
from: {chat_name}
text: "{msg_text.replace('"', '\\"')}"
status: pending
priority: {"high" if any(k in ("urgent", "asap") for k in keywords) else "normal"}
keywords: {", ".join(keywords)}
unread_count: {badge}
received: {ts}
zone: local
created: {now_iso}
---

## WhatsApp Message

**From:** {chat_name}
**Preview:** {msg_text}
**Unread count:** {badge}
**Matched keywords:** {", ".join(keywords)}
**Received:** {ts}

## Suggested Actions
- [ ] Read full conversation
- [ ] Reply (requires HITL approval for external sends)
- [ ] Forward to relevant team member
- [ ] Archive after processing
"""

        if self.dry_run:
            logger.info("[DRY RUN] Would create %s", filename)
            logger.info("[DRY RUN]   from=%s  text=%s  keywords=%s", chat_name, msg_text[:80], keywords)
            return

        filepath = NEEDS_ACTION_DIR / filename
        filepath.write_text(content, encoding="utf-8")
        logger.info(
            "Created task: %s | from=%s | keywords=%s | unread=%s",
            filename, chat_name, keywords, badge,
        )


# ══════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════
def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "WhatsApp Watcher — monitors WhatsApp Web for unread messages "
            "matching business keywords and creates task files."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log actions without creating task files",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=CHECK_INTERVAL,
        help=f"Poll interval in seconds (default: {CHECK_INTERVAL})",
    )
    parser.add_argument(
        "--keywords",
        type=str,
        default=None,
        help="Comma-separated keywords to match (overrides env/default)",
    )
    parser.add_argument(
        "--headless",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run browser headless (default: true). Use --no-headless for first-time QR scan.",
    )
    parser.add_argument(
        "--login-timeout",
        type=int,
        default=300,
        help="Seconds to wait for WhatsApp Web to load/login (default: 300)",
    )
    args = parser.parse_args()

    # Override keywords from CLI if provided
    if args.keywords:
        global KEYWORDS
        KEYWORDS = [kw.strip() for kw in args.keywords.split(",") if kw.strip()]

    # ── ToS warning (always) ──────────────────────────────────────────
    logger.warning(TOS_WARNING)
    print(f"\n{'='*70}\n{TOS_WARNING}\n{'='*70}\n")

    logger.info("Keywords: %s", KEYWORDS)
    logger.info("Poll interval: %ds", args.interval)
    logger.info("Session dir: %s", USER_DATA_DIR)

    watcher = WhatsAppWatcher(dry_run=args.dry_run, headless=args.headless)

    # Launch browser and wait for login
    watcher._launch_browser()
    if not watcher._wait_for_login(timeout_seconds=args.login_timeout):
        watcher._shutdown_browser()
        sys.exit(1)

    # Enter poll loop
    try:
        watcher.run(interval=args.interval)
    finally:
        watcher.save_state(STATE_FILE)
        watcher._shutdown_browser()
        logger.info("Browser closed. Final state saved.")


if __name__ == "__main__":
    main()
