#!/usr/bin/env python3
"""
X (Twitter) Watcher — Platinum Tier

Polls X/Twitter for new mentions/replies via X API v2 (through social-mcp-x).
Creates task files in data/Needs_Action/cloud/ for cloud agent triage/draft processing.

Cloud zone: Social watchers route to cloud for draft generation.

Usage:
    python x_watcher.py             # Start polling (300s interval)
    python x_watcher.py --dry-run   # Use mock data, no API calls
    python x_watcher.py --once      # Single poll then exit
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
LOG_FILE = LOG_DIR / "x_watcher.log"
STATE_FILE = VAULT_DIR / "data" / "x_processed_ids.pkl"
MCP_SERVER = VAULT_DIR / "mcp-servers" / "social-mcp-x" / "social-mcp-x.js"

CHECK_INTERVAL = int(os.environ.get("X_CHECK_INTERVAL", "300"))
DRY_RUN = os.environ.get("X_DRY_RUN", "true").lower() == "true"
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
logger = logging.getLogger("XWatcher")

# ── MOCK DATA ─────────────────────────────────────────────────────────────
MOCK_MENTIONS = [
    {"id": "x_m_001", "from": "@devtools_daily", "message": "@you This AI employee concept is genius!",
     "created_time": "2026-02-18T12:00:00Z", "type": "mention",
     "metrics": {"likes": 12, "retweets": 3, "replies": 2}},
    {"id": "x_m_002", "from": "@startup_hub", "message": "@you Would you be open to a demo?",
     "created_time": "2026-02-18T17:45:00Z", "type": "reply",
     "metrics": {"likes": 5, "retweets": 0, "replies": 1}},
    {"id": "x_m_003", "from": "@ai_researcher", "message": "@you Interesting use of MCP protocol here",
     "created_time": "2026-02-19T07:30:00Z", "type": "mention",
     "metrics": {"likes": 28, "retweets": 7, "replies": 4}},
]

MOCK_SUMMARY = {
    "platform": "x",
    "tweets_analyzed": 6,
    "total_likes": 198,
    "total_retweets": 45,
    "total_replies": 32,
    "total_engagement": 275,
    "top_tweet": {"id": "x_006", "text": "Shipped Gold Tier! Full Odoo + social integration",
                  "likes": 67, "retweets": 18},
    "impressions": 12400,
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
    """Call social-mcp-x via stdin/stdout JSON-RPC."""
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
class XWatcher:
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
        logger.info(f"X Watcher started (DRY_RUN={self.dry_run}, interval={CHECK_INTERVAL}s)")
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
        """Check for new mentions/replies on X/Twitter."""
        if self.dry_run:
            mentions = MOCK_MENTIONS
            logger.info(f"[DRY RUN] Checking {len(mentions)} mock X mentions")
        else:
            try:
                data = with_backoff(lambda: call_mcp("get_summary", {"limit": 10}))
                mentions = []
                for tweet in data.get("tweets", []):
                    if tweet.get("replies", 0) > 0 or "mention" in tweet.get("type", ""):
                        mentions.append({
                            "id": f"x_t_{tweet['id']}",
                            "from": tweet.get("author", "@unknown"),
                            "message": tweet.get("text", "")[:280],
                            "created_time": tweet.get("created_at", datetime.now().isoformat()),
                            "type": tweet.get("type", "mention"),
                            "metrics": {
                                "likes": tweet.get("likes", 0),
                                "retweets": tweet.get("retweets", 0),
                                "replies": tweet.get("replies", 0),
                            },
                        })
            except Exception as e:
                logger.error(f"Failed to fetch X mentions: {e}")
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
            logger.info(f"Created {new_count} new X/Twitter task(s)")
            self._save_state()
        else:
            logger.debug("No new X mentions")

    def _create_task_file(self, mention):
        """Create a .md task file in Needs_Action for the agent."""
        now = datetime.now()
        safe_id = mention["id"].replace("/", "_").replace(":", "_")
        filename = f"SOCIAL_x_{safe_id}.md"
        filepath = NEEDS_ACTION_DIR / filename

        from_user = mention.get("from", "@unknown")
        message = mention.get("message", "")
        mention_type = mention.get("type", "mention")
        created = mention.get("created_time", now.isoformat())
        metrics = mention.get("metrics", {})

        content = f"""---
type: social
action: x_post
platform: x
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

# X {mention_type.title()} from {from_user}

**Platform:** X (Twitter)
**Type:** {mention_type}
**From:** {from_user}
**Time:** {created}

## Content

{message}

## Engagement
- Likes: {metrics.get('likes', 0)}
- Retweets: {metrics.get('retweets', 0)}
- Replies: {metrics.get('replies', 0)}

## Suggested Actions
- Reply to {mention_type} (max 280 chars)
- Route to skill-social-integrator for response
- Log engagement via skill-audit-logger
"""
        filepath.write_text(content, encoding="utf-8")
        logger.info(f"Created task: {filename}")

    def _generate_summary(self):
        """Generate an engagement summary .md file."""
        now = datetime.now()
        summary_file = BRIEFINGS_DIR / f"SUMMARY_x_{now.strftime('%Y%m%d_%H%M')}.md"

        existing = list(BRIEFINGS_DIR.glob(f"SUMMARY_x_{now.strftime('%Y%m%d')}*.md"))
        if existing:
            logger.debug("X summary already exists for today, skipping")
            return

        if self.dry_run:
            summary = MOCK_SUMMARY
            logger.info("[DRY RUN] Generating mock X summary")
        else:
            try:
                data = with_backoff(lambda: call_mcp("get_summary", {"limit": 10}))
                summary = data.get("summary", {})
            except Exception as e:
                logger.error(f"Failed to generate X summary: {e}")
                return

        content = f"""---
type: social_summary
platform: x
generated: {now.isoformat()}
period: {summary.get('period', 'last_7_days')}
---

# X (Twitter) Engagement Summary — {now.strftime('%Y-%m-%d')}

## Metrics
| Metric | Value |
|--------|-------|
| Tweets Analyzed | {summary.get('tweets_analyzed', 0)} |
| Total Likes | {summary.get('total_likes', 0)} |
| Total Retweets | {summary.get('total_retweets', 0)} |
| Total Replies | {summary.get('total_replies', 0)} |
| **Total Engagement** | **{summary.get('total_engagement', 0)}** |
| Impressions | {summary.get('impressions', 'N/A')} |

## Top Tweet
{json.dumps(summary.get('top_tweet', {}), indent=2)}

*Generated by x_watcher.py — Platinum Tier*
"""
        summary_file.write_text(content, encoding="utf-8")
        logger.info(f"Generated summary: {summary_file.name}")


# ── MAIN ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="X (Twitter) Watcher — Gold Tier")
    parser.add_argument("--dry-run", action="store_true", help="Use mock data, no API calls")
    parser.add_argument("--once", action="store_true", help="Single poll then exit")
    args = parser.parse_args()

    watcher = XWatcher(dry_run=args.dry_run, once=args.once)
    watcher.run()
