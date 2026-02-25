#!/usr/bin/env python3
"""
Facebook Watcher — Platinum Tier

Polls Facebook Page for new comments/mentions via Graph API (through social-mcp-fb).
Creates task files in data/Needs_Action/cloud/ for cloud agent triage/draft processing.
Generates engagement summaries periodically.

Cloud zone: Social watchers route to cloud for draft generation.

Usage:
    python facebook_watcher.py             # Start polling (300s interval)
    python facebook_watcher.py --dry-run   # Use mock data, no API calls
    python facebook_watcher.py --once      # Single poll then exit
"""

import os
import sys
import json
import time
import logging
import pickle
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from random import uniform

# ── CONFIG ────────────────────────────────────────────────────────────────
VAULT_DIR = Path(__file__).parent.parent.resolve()
# Platinum: Route to cloud zone — social triage is a cloud task
NEEDS_ACTION_DIR = VAULT_DIR / "data" / "Needs_Action" / "cloud"
BRIEFINGS_DIR = VAULT_DIR / "data" / "Briefings"
LOG_DIR = VAULT_DIR / "data" / "Logs"
LOG_FILE = LOG_DIR / "facebook_watcher.log"
STATE_FILE = VAULT_DIR / "data" / "fb_processed_ids.pkl"
MCP_SERVER = VAULT_DIR / "mcp-servers" / "social-mcp-fb" / "social-mcp-fb.js"

CHECK_INTERVAL = int(os.environ.get("FB_CHECK_INTERVAL", "300"))
DRY_RUN = os.environ.get("FB_DRY_RUN", "true").lower() == "true"
MAX_RETRIES = int(os.environ.get("MAX_RETRY_ATTEMPTS", "3"))

# ── LOGGING ───────────────────────────────────────────────────────────────
LOG_DIR.mkdir(parents=True, exist_ok=True)
NEEDS_ACTION_DIR.mkdir(parents=True, exist_ok=True)
BRIEFINGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger("FacebookWatcher")

# ── MOCK DATA ─────────────────────────────────────────────────────────────
MOCK_MENTIONS = [
    {"id": "fb_m_001", "from": "Jane Customer", "message": "Love your product! How do I get started?",
     "created_time": "2026-02-18T10:30:00Z", "type": "comment"},
    {"id": "fb_m_002", "from": "Tech Reviewer", "message": "Great demo at the hackathon!",
     "created_time": "2026-02-18T14:15:00Z", "type": "mention"},
    {"id": "fb_m_003", "from": "Potential Lead", "message": "Can you DM me pricing details?",
     "created_time": "2026-02-19T08:00:00Z", "type": "comment"},
]

MOCK_SUMMARY = {
    "platform": "facebook",
    "posts_analyzed": 5,
    "total_likes": 264,
    "total_comments": 66,
    "total_shares": 67,
    "total_engagement": 397,
    "top_post": {"id": "123_003", "message": "Join us at the GIAIC Hackathon", "likes": 132},
    "period": "last_7_days",
}


# ── RETRY / BACKOFF ──────────────────────────────────────────────────────
def with_backoff(func, max_attempts=None, base_delay=2):
    """Execute func with exponential backoff on failure."""
    attempts = max_attempts or MAX_RETRIES
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return func()
        except Exception as e:
            last_error = e
            if attempt == attempts:
                break
            delay = base_delay * (2 ** (attempt - 1)) + uniform(0, 0.5)
            logger.warning(f"Attempt {attempt}/{attempts} failed: {e}. Retrying in {delay:.1f}s...")
            time.sleep(delay)
    logger.error(f"All {attempts} attempts failed: {last_error}")
    raise last_error


# ── MCP CALL ──────────────────────────────────────────────────────────────
def call_mcp(tool_name, arguments):
    """Call social-mcp-fb via stdin/stdout JSON-RPC."""
    request = json.dumps({
        "jsonrpc": "2.0", "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    })
    try:
        proc = subprocess.run(
            ["node", str(MCP_SERVER)],
            input=request + "\n",
            capture_output=True, text=True, timeout=30,
        )
        for line in proc.stdout.strip().split("\n"):
            if line.strip():
                resp = json.loads(line)
                if "result" in resp:
                    return json.loads(resp["result"]["content"][0]["text"])
                elif "error" in resp:
                    raise RuntimeError(resp["error"]["message"])
    except subprocess.TimeoutExpired:
        raise TimeoutError("MCP call timed out")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid MCP response: {e}")
    return None


# ── WATCHER ───────────────────────────────────────────────────────────────
class FacebookWatcher:
    def __init__(self, dry_run=False, once=False):
        self.dry_run = dry_run or DRY_RUN
        self.once = once
        self.processed_ids = set()
        self._load_state()

    def _load_state(self):
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE, "rb") as f:
                    self.processed_ids = pickle.load(f)
            except Exception:
                self.processed_ids = set()

    def _save_state(self):
        try:
            with open(STATE_FILE, "wb") as f:
                pickle.dump(self.processed_ids, f)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def run(self):
        logger.info(f"Facebook Watcher started (DRY_RUN={self.dry_run}, interval={CHECK_INTERVAL}s)")
        while True:
            try:
                self._poll_mentions()
                self._generate_summary()
            except Exception as e:
                logger.exception(f"Poll cycle error: {e}")
            if self.once:
                break
            time.sleep(CHECK_INTERVAL)

    def _poll_mentions(self):
        """Check for new comments/mentions on the Facebook Page."""
        if self.dry_run:
            mentions = MOCK_MENTIONS
            logger.info(f"[DRY RUN] Checking {len(mentions)} mock mentions")
        else:
            # In production, this would call the Graph API for page comments/mentions
            # For now, route through MCP summary which includes recent activity
            try:
                data = with_backoff(lambda: call_mcp("get_summary", {"limit": 10}))
                # Extract mentions from post comments (simplified)
                mentions = []
                for post in data.get("posts", []):
                    if post.get("comments", 0) > 0:
                        mentions.append({
                            "id": f"fb_c_{post['id']}",
                            "from": "Page Visitor",
                            "message": f"New comments on: {post.get('message', '')[:100]}",
                            "created_time": post.get("created_time", datetime.now().isoformat()),
                            "type": "comment",
                        })
            except Exception as e:
                logger.error(f"Failed to fetch mentions: {e}")
                return

        new_count = 0
        for mention in mentions:
            mid = mention["id"]
            if mid in self.processed_ids:
                continue

            self._create_task_file(mention)
            self.processed_ids.add(mid)
            new_count += 1

        if new_count > 0:
            logger.info(f"Created {new_count} new Facebook task(s)")
            self._save_state()
        else:
            logger.debug("No new Facebook mentions")

    def _create_task_file(self, mention):
        """Create a .md task file in Needs_Action for the agent."""
        now = datetime.now()
        safe_id = mention["id"].replace("/", "_").replace(":", "_")
        filename = f"SOCIAL_fb_{safe_id}.md"
        filepath = NEEDS_ACTION_DIR / filename

        from_user = mention.get("from", "Unknown")
        message = mention.get("message", "")
        mention_type = mention.get("type", "comment")
        created = mention.get("created_time", now.isoformat())

        content = f"""---
type: social
action: facebook_post
platform: fb
social_type: {mention_type}
from: "{from_user}"
text: "{message[:200]}"
social_id: "{mention['id']}"
received: {created}
status: pending
priority: normal
zone: cloud
created: {now.isoformat()}
---

# Facebook {mention_type.title()} from {from_user}

**Platform:** Facebook
**Type:** {mention_type}
**From:** {from_user}
**Time:** {created}

## Content

{message}

## Suggested Actions
- Reply to {mention_type}
- Route to skill-social-integrator for response
- Log engagement via skill-audit-logger
"""
        filepath.write_text(content, encoding="utf-8")
        logger.info(f"Created task: {filename}")

    def _generate_summary(self):
        """Generate an engagement summary .md file."""
        now = datetime.now()
        summary_file = BRIEFINGS_DIR / f"SUMMARY_fb_{now.strftime('%Y%m%d_%H%M')}.md"

        # Don't generate more than once per poll
        existing = list(BRIEFINGS_DIR.glob(f"SUMMARY_fb_{now.strftime('%Y%m%d')}*.md"))
        if existing:
            logger.debug("Summary already exists for today, skipping")
            return

        if self.dry_run:
            summary = MOCK_SUMMARY
            logger.info("[DRY RUN] Generating mock Facebook summary")
        else:
            try:
                data = with_backoff(lambda: call_mcp("get_summary", {"limit": 10}))
                summary = data.get("summary", {})
            except Exception as e:
                logger.error(f"Failed to generate summary: {e}")
                return

        content = f"""---
type: social_summary
platform: facebook
generated: {now.isoformat()}
period: {summary.get('period', 'last_7_days')}
---

# Facebook Engagement Summary — {now.strftime('%Y-%m-%d')}

## Metrics
| Metric | Value |
|--------|-------|
| Posts Analyzed | {summary.get('posts_analyzed', 0)} |
| Total Likes | {summary.get('total_likes', 0)} |
| Total Comments | {summary.get('total_comments', 0)} |
| Total Shares | {summary.get('total_shares', 0)} |
| **Total Engagement** | **{summary.get('total_engagement', 0)}** |

## Top Post
{json.dumps(summary.get('top_post', {}), indent=2)}

*Generated by facebook_watcher.py — Platinum Tier*
"""
        summary_file.write_text(content, encoding="utf-8")
        logger.info(f"Generated summary: {summary_file.name}")


# ── MAIN ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Facebook Watcher — Platinum Tier")
    parser.add_argument("--dry-run", action="store_true", help="Use mock data, no API calls")
    parser.add_argument("--once", action="store_true", help="Single poll then exit")
    args = parser.parse_args()

    watcher = FacebookWatcher(dry_run=args.dry_run, once=args.once)
    watcher.run()
