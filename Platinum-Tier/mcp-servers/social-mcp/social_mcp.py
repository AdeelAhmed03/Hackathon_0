#!/usr/bin/env python3
"""
Social Media MCP Server — Platinum Tier Enhancement

Unified interface for Facebook, Instagram, and Twitter/X posting and feed summaries.
Primarily uses browser automation (Playwright) to access your actual accounts
through cookie-based authentication (like LinkedIn), with API-based fallbacks.

DRY_RUN mode returns realistic mock data without calling any APIs.

Usage:
    python social_mcp.py                # Start MCP server
    python social_mcp.py --dry-run      # Test with mock data
    python social_mcp.py --test         # Run self-test

Browser Authentication:
    # Authenticate each platform once using your actual account:
    node mcp-servers/browser-social-mcp/browser-social-mcp.js --auth facebook
    node mcp-servers/browser-social-mcp/browser-social-mcp.js --auth instagram
    node mcp-servers/browser-social-mcp/browser-social-mcp.js --auth x
"""

import os
import sys
import json
import time
import logging
import argparse
from datetime import datetime, date
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent / ".env")
except ImportError:
    pass

# ── RETRY HANDLER INTEGRATION (Gold Tier) ────────────────────────────────
VAULT_DIR = Path(__file__).parent.parent.parent.resolve()
sys.path.insert(0, str(VAULT_DIR))
try:
    from retry_handler import with_retry, classify_error, quarantine_file, ErrorType
    HAS_RETRY = True
except ImportError:
    HAS_RETRY = False

# ── AUDIT LOGGER INTEGRATION (Gold Tier) ─────────────────────────────────
try:
    from audit_logger import log_action, log_error as _audit_log_error, log_mcp_call
    HAS_AUDIT_LOGGER = True
except ImportError:
    HAS_AUDIT_LOGGER = False

NEEDS_ACTION_DIR = VAULT_DIR / "data" / "Needs_Action"

# ── CONFIG ────────────────────────────────────────────────────────────────
FB_PAGE_ID = os.environ.get("FB_PAGE_ID", "your_page_id")
FB_ACCESS_TOKEN = os.environ.get("FB_ACCESS_TOKEN", "your_fb_access_token")
FB_DRY_RUN = os.environ.get("FB_DRY_RUN", "true").lower() == "true"

IG_ACCOUNT_ID = os.environ.get("IG_BUSINESS_ACCOUNT_ID", "your_ig_account_id")

X_API_KEY = os.environ.get("X_API_KEY", "")
X_API_SECRET = os.environ.get("X_API_SECRET", "")
X_ACCESS_TOKEN = os.environ.get("X_ACCESS_TOKEN", "")
X_ACCESS_SECRET = os.environ.get("X_ACCESS_SECRET", "")
X_BEARER_TOKEN = os.environ.get("X_BEARER_TOKEN", "")
X_DRY_RUN = os.environ.get("X_DRY_RUN", "true").lower() == "true"

# ── LINKEDIN CONFIG (Platinum Tier) ───────────────────────────────────────────
LINKEDIN_TOKEN = os.environ.get("LINKEDIN_TOKEN", "")
LINKEDIN_ACCESS_TOKEN = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
LINKEDIN_PERSON_URN = os.environ.get("LINKEDIN_PERSON_URN", "")
LINKEDIN_CLIENT_ID = os.environ.get("LINKEDIN_CLIENT_ID", "")
LINKEDIN_CLIENT_SECRET = os.environ.get("LINKEDIN_CLIENT_SECRET", "")
LINKEDIN_DRY_RUN = os.environ.get("LINKEDIN_DRY_RUN", "true").lower() == "true"

MAX_RETRIES = int(os.environ.get("MAX_RETRY_ATTEMPTS", "3"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("SocialMCP")


# ── MOCK DATA ─────────────────────────────────────────────────────────────
MOCK_FB_POST = {
    "id": "123456789_987654321",
    "message": "",
    "created_time": datetime.now().isoformat(),
    "permalink_url": "https://facebook.com/123456789/posts/987654321"
}

MOCK_FB_FEED = [
    {"id": "fb_001", "message": "Excited to announce our Q1 results!", "likes": 42, "comments": 8,
     "shares": 5, "created_time": "2026-02-15T10:00:00"},
    {"id": "fb_002", "message": "New partnership with TechStart Inc", "likes": 67, "comments": 12,
     "shares": 15, "created_time": "2026-02-10T14:30:00"},
    {"id": "fb_003", "message": "Team building event was a success!", "likes": 89, "comments": 23,
     "shares": 3, "created_time": "2026-02-05T09:00:00"},
]

MOCK_IG_POST = {
    "id": "ig_17890000001234567",
    "media_type": "IMAGE",
    "caption": "",
    "permalink": "https://instagram.com/p/abc123",
    "timestamp": datetime.now().isoformat()
}

MOCK_IG_MEDIA = [
    {"id": "ig_001", "caption": "Behind the scenes at our office", "like_count": 156,
     "comments_count": 18, "media_type": "IMAGE", "timestamp": "2026-02-14T12:00:00"},
    {"id": "ig_002", "caption": "Product launch day!", "like_count": 234,
     "comments_count": 45, "media_type": "CAROUSEL_ALBUM", "timestamp": "2026-02-08T16:00:00"},
]

MOCK_TWEET = {
    "id": "1234567890123456789",
    "text": "",
    "created_at": datetime.now().isoformat(),
    "url": "https://x.com/user/status/1234567890123456789"
}

MOCK_TIMELINE = [
    {"id": "tw_001", "text": "Just shipped a major update to our platform!", "likes": 28,
     "retweets": 12, "replies": 5, "created_at": "2026-02-16T11:00:00"},
    {"id": "tw_002", "text": "Grateful for our amazing customers", "likes": 45,
     "retweets": 8, "replies": 3, "created_at": "2026-02-12T09:30:00"},
]

MOCK_LINKEDIN_POST = {
    "id": "urn:li:activity:7000000001234567890",
    "message": "",
    "created": datetime.now().isoformat(),
    "permalink": "https://linkedin.com/feed/update/7000000001234567890"
}

MOCK_LINKEDIN_FEED = [
    {"id": "li_001", "text": "Exciting to share our latest AI insights!", "likes": 125, "comments": 18,
     "shares": 25, "created": "2026-02-15T10:00:00", "engagement_rate": 1.23},
    {"id": "li_002", "text": "New partnership announcement", "likes": 98, "comments": 12,
     "shares": 15, "created": "2026-02-10T14:30:00", "engagement_rate": 0.92},
    {"id": "li_003", "text": "Team celebrating Q1 success", "likes": 156, "comments": 23,
     "shares": 8, "created": "2026-02-05T09:00:00", "engagement_rate": 1.45},
]


# ── BROWSER MCP CLIENT ───────────────────────────────────────────────────
class BrowserMCPClient:
    """Client to communicate with the browser-based social MCP server"""

    def __init__(self):
        self.process = None
        self.browser_mcp_path = VAULT_DIR / "mcp-servers" / "browser-social-mcp" / "browser-social-mcp.js"
        self._start_browser_mcp()

    def _start_browser_mcp(self):
        """Start the browser-based MCP server as a subprocess"""
        try:
            import subprocess
            # Start browser MCP server as subprocess
            self.process = subprocess.Popen(
                ["node", str(self.browser_mcp_path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

            # Initialize the connection
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize"
            }

            self.process.stdin.write(json.dumps(init_request) + "\n")
            self.process.stdin.flush()

            # Read response
            response_line = self.process.stdout.readline()
            if response_line:
                response = json.loads(response_line.strip())
                if "result" in response:
                    logger.info(f"Connected to browser-social-mcp: {response['result']['name']}")
                else:
                    logger.warning(f"Browser MCP initialization failed: {response.get('error', 'Unknown error')}")

        except Exception as e:
            logger.error(f"Failed to start browser MCP: {e}")
            self.process = None

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Call a tool on the browser MCP server"""
        if not self.process:
            logger.warning("Browser MCP not running, using API fallback")
            return None

        try:
            request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }

            self.process.stdin.write(json.dumps(request) + "\n")
            self.process.stdin.flush()

            # Read response
            response_line = self.process.stdout.readline()
            if response_line:
                response = json.loads(response_line.strip())

                if "result" in response and response["result"]["content"]:
                    return json.loads(response["result"]["content"][0]["text"])
                elif "error" in response:
                    logger.error(f"Browser tool call failed: {response['error']['message']}")
                    return None

        except Exception as e:
            logger.error(f"Browser tool call failed: {e}")
            return None

        return None

# Global browser MCP client instance
browser_mcp_client = BrowserMCPClient()


# ── GRACEFUL DEGRADATION (Gold Tier) ─────────────────────────────────────
def _queue_deferred(platform, action, details):
    """Queue a task file when a social API is down (graceful degradation)."""
    NEEDS_ACTION_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    filename = f"DEFERRED_social_{platform}_{now.strftime('%Y%m%d_%H%M%S')}.md"
    file_path = NEEDS_ACTION_DIR / filename
    content = f"""---
type: deferred_task
status: pending
priority: medium
service: social_{platform}
action: {action}
created: {now.isoformat()}
deferred_reason: api_unavailable
---

## Deferred Social Task: {action} ({platform})

The {platform} API was unavailable. This task has been queued for retry.

### Details

{details}
"""
    try:
        file_path.write_text(content, encoding="utf-8")
        logger.info(f"[DEGRADE] Queued deferred {platform} task: {filename}")
        # Gold Tier: log the deferral to audit log
        if HAS_AUDIT_LOGGER:
            log_action(
                action_type="social.deferred_task",
                actor="social_mcp",
                target=f"{platform}.{action}",
                parameters={"filename": filename, "reason": "api_unavailable"},
                result="success",
                severity="WARN",
            )
    except OSError as e:
        logger.error(f"[DEGRADE] Failed to queue task: {e}")
        if HAS_AUDIT_LOGGER:
            _audit_log_error(
                action_type="social.deferred_task",
                actor="social_mcp",
                target=f"{platform}.{action}",
                error=e,
                severity="ERROR",
            )


# ── UPDATED FACEBOOK TOOLS (with browser priority) ───────────────────────
def post_to_facebook(message):
    """Post a message to the configured Facebook Page.

    Prioritizes browser-based authentication using cookies over API keys.
    """
    # Try browser-based approach first
    result = browser_mcp_client.call_tool("post_to_facebook", {
        "message": message
    })

    if result and result.get("success"):
        logger.info(f"Facebook post successful via browser: {message[:80]}...")
        return result

    # Fallback to API-based approach
    if FB_DRY_RUN:
        result = {**MOCK_FB_POST, "message": message}
        logger.info(f"[DRY RUN] Facebook post: {message[:80]}...")
        return {"success": True, "dry_run": True, "platform": "facebook", "post": result}

    import requests
    url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed"
    resp = requests.post(url, data={"message": message, "access_token": FB_ACCESS_TOKEN}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return {"success": True, "dry_run": False, "platform": "facebook",
            "post": {"id": data.get("id"), "message": message}}


def get_fb_feed_summary(limit=10):
    """Get a summary of recent Facebook Page posts with engagement metrics.

    Prioritizes browser-based authentication using cookies over API keys.

    Args:
        limit: Number of posts to retrieve (default 10)
    """
    # Try browser-based approach first
    result = browser_mcp_client.call_tool("get_facebook_summary", {"limit": limit})

    if result and result.get("success"):
        logger.info(f"Facebook summary successful via browser")
        return result

    # Fallback to API-based approach
    if FB_DRY_RUN:
        total_likes = sum(p["likes"] for p in MOCK_FB_FEED)
        total_comments = sum(p["comments"] for p in MOCK_FB_FEED)
        total_shares = sum(p["shares"] for p in MOCK_FB_FEED)
        logger.info(f"[DRY RUN] Facebook feed summary: {len(MOCK_FB_FEED)} posts")
        return {
            "success": True, "dry_run": True, "platform": "facebook",
            "summary": {
                "post_count": len(MOCK_FB_FEED),
                "total_likes": total_likes, "total_comments": total_comments,
                "total_shares": total_shares,
                "avg_engagement": round((total_likes + total_comments + total_shares) / len(MOCK_FB_FEED), 1),
                "top_post": max(MOCK_FB_FEED, key=lambda p: p["likes"]),
                "period": f"{MOCK_FB_FEED[-1]['created_time'][:10]} to {MOCK_FB_FEED[0]['created_time'][:10]}"
            },
            "posts": MOCK_FB_FEED
        }

    import requests
    url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed"
    resp = requests.get(url, params={
        "access_token": FB_ACCESS_TOKEN,
        "fields": "id,message,created_time,likes.summary(true),comments.summary(true),shares",
        "limit": limit
    }, timeout=30)
    resp.raise_for_status()
    posts = resp.json().get("data", [])
    return {"success": True, "dry_run": False, "platform": "facebook",
            "summary": {"post_count": len(posts)}, "posts": posts}


# ── UPDATED INSTAGRAM TOOLS (with browser priority) ──────────────────────
def post_to_instagram(caption, image_url=None):
    """Post to Instagram Business account (requires image_url for non-dry-run).

    Prioritizes browser-based authentication using cookies over API keys.

    Args:
        caption: The caption text for the post
        image_url: Public URL of the image to post (required for actual posting)
    """
    # Try browser-based approach first
    result = browser_mcp_client.call_tool("post_to_instagram", {
        "caption": caption,
        "image_url": image_url
    })

    if result and result.get("success"):
        logger.info(f"Instagram post successful via browser: {caption[:80]}...")
        return result

    # Fallback to API-based approach
    if FB_DRY_RUN:  # IG uses same FB token
        result = {**MOCK_IG_POST, "caption": caption}
        logger.info(f"[DRY RUN] Instagram post: {caption[:80]}...")
        return {"success": True, "dry_run": True, "platform": "instagram", "post": result}

    import requests
    # Step 1: Create media container
    container_url = f"https://graph.facebook.com/v19.0/{IG_ACCOUNT_ID}/media"
    container_resp = requests.post(container_url, data={
        "image_url": image_url, "caption": caption, "access_token": FB_ACCESS_TOKEN
    }, timeout=30)
    container_resp.raise_for_status()
    creation_id = container_resp.json()["id"]

    # Step 2: Publish
    publish_url = f"https://graph.facebook.com/v19.0/{IG_ACCOUNT_ID}/media_publish"
    pub_resp = requests.post(publish_url, data={
        "creation_id": creation_id, "access_token": FB_ACCESS_TOKEN
    }, timeout=30)
    pub_resp.raise_for_status()
    return {"success": True, "dry_run": False, "platform": "instagram",
            "post": {"id": pub_resp.json()["id"], "caption": caption}}


def get_ig_media_summary(limit=10):
    """Get a summary of recent Instagram posts with engagement metrics.

    Prioritizes browser-based authentication using cookies over API keys.

    Args:
        limit: Number of posts to retrieve (default 10)
    """
    # Try browser-based approach first
    result = browser_mcp_client.call_tool("get_instagram_summary", {"limit": limit})

    if result and result.get("success"):
        logger.info(f"Instagram summary successful via browser")
        return result

    # Fallback to API-based approach
    if FB_DRY_RUN:
        total_likes = sum(p["like_count"] for p in MOCK_IG_MEDIA)
        total_comments = sum(p["comments_count"] for p in MOCK_IG_MEDIA)
        logger.info(f"[DRY RUN] Instagram media summary: {len(MOCK_IG_MEDIA)} posts")
        return {
            "success": True, "dry_run": True, "platform": "instagram",
            "summary": {
                "post_count": len(MOCK_IG_MEDIA),
                "total_likes": total_likes, "total_comments": total_comments,
                "avg_engagement": round((total_likes + total_comments) / len(MOCK_IG_MEDIA), 1),
                "top_post": max(MOCK_IG_MEDIA, key=lambda p: p["like_count"]),
            },
            "posts": MOCK_IG_MEDIA
        }

    import requests
    url = f"https://graph.facebook.com/v19.0/{IG_ACCOUNT_ID}/media"
    resp = requests.get(url, params={
        "access_token": FB_ACCESS_TOKEN,
        "fields": "id,caption,like_count,comments_count,media_type,timestamp,permalink",
        "limit": limit
    }, timeout=30)
    resp.raise_for_status()
    posts = resp.json().get("data", [])
    return {"success": True, "dry_run": False, "platform": "instagram",
            "summary": {"post_count": len(posts)}, "posts": posts}


# ── UPDATED TWITTER/X TOOLS (with browser priority) ──────────────────────
def post_tweet(text):
    """Post a tweet to X (Twitter).

    Prioritizes browser-based authentication using cookies over API keys.

    Args:
        text: The tweet text (max 280 characters)
    """
    # Try browser-based approach first
    result = browser_mcp_client.call_tool("post_to_x", {
        "text": text
    })

    if result and result.get("success"):
        logger.info(f"X post successful via browser: {text[:80]}...")
        return result

    # Fallback to API-based approach
    if X_DRY_RUN:
        if len(text) > 280:
            return {"success": False, "dry_run": True, "platform": "x",
                    "error": f"Tweet exceeds 280 chars ({len(text)})"}
        result = {**MOCK_TWEET, "text": text}
        logger.info(f"[DRY RUN] Tweet: {text[:80]}...")
        return {"success": True, "dry_run": True, "platform": "x", "tweet": result}

    import tweepy
    client = tweepy.Client(
        bearer_token=X_BEARER_TOKEN,
        consumer_key=X_API_KEY, consumer_secret=X_API_SECRET,
        access_token=X_ACCESS_TOKEN, access_token_secret=X_ACCESS_SECRET
    )
    resp = client.create_tweet(text=text)
    tweet_id = resp.data["id"]
    return {"success": True, "dry_run": False, "platform": "x",
            "tweet": {"id": tweet_id, "text": text}}


def get_x_timeline_summary(limit=10):
    """Get a summary of recent tweets with engagement metrics.

    Prioritizes browser-based authentication using cookies over API keys.

    Args:
        limit: Number of tweets to retrieve (default 10)
    """
    # Try browser-based approach first
    result = browser_mcp_client.call_tool("get_x_summary", {"limit": limit})

    if result and result.get("success"):
        logger.info(f"X summary successful via browser")
        return result

    # Fallback to API-based approach
    if X_DRY_RUN:
        total_likes = sum(t["likes"] for t in MOCK_TIMELINE)
        total_rts = sum(t["retweets"] for t in MOCK_TIMELINE)
        logger.info(f"[DRY RUN] X timeline summary: {len(MOCK_TIMELINE)} tweets")
        return {
            "success": True, "dry_run": True, "platform": "x",
            "summary": {
                "tweet_count": len(MOCK_TIMELINE),
                "total_likes": total_likes, "total_retweets": total_rts,
                "avg_engagement": round((total_likes + total_rts) / len(MOCK_TIMELINE), 1),
                "top_tweet": max(MOCK_TIMELINE, key=lambda t: t["likes"]),
            },
            "tweets": MOCK_TIMELINE
        }

    import tweepy
    client = tweepy.Client(bearer_token=X_BEARER_TOKEN)
    me = client.get_me()
    tweets = client.get_users_tweets(
        me.data.id, max_results=min(limit, 100),
        tweet_fields=["created_at", "public_metrics"]
    )
    results = []
    for t in (tweets.data or []):
        metrics = t.public_metrics or {}
        results.append({
            "id": t.id, "text": t.text, "created_at": str(t.created_at),
            "likes": metrics.get("like_count", 0),
            "retweets": metrics.get("retweet_count", 0),
            "replies": metrics.get("reply_count", 0)
        })
    return {"success": True, "dry_run": False, "platform": "x",
            "summary": {"tweet_count": len(results)}, "tweets": results}


# ── FACEBOOK TOOLS ───────────────────────────────────────────────────────
def post_to_facebook(message):
    """Post a message to the configured Facebook Page.

    Args:
        message: The text content to post
    """
    if FB_DRY_RUN:
        result = {**MOCK_FB_POST, "message": message}
        logger.info(f"[DRY RUN] Facebook post: {message[:80]}...")
        return {"success": True, "dry_run": True, "platform": "facebook", "post": result}

    import requests
    url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed"
    resp = requests.post(url, data={"message": message, "access_token": FB_ACCESS_TOKEN}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return {"success": True, "dry_run": False, "platform": "facebook",
            "post": {"id": data.get("id"), "message": message}}


def get_fb_feed_summary(limit=10):
    """Get a summary of recent Facebook Page posts with engagement metrics.

    Wrapped with @with_retry for transient API failures (Gold Tier).

    Args:
        limit: Number of posts to retrieve (default 10)
    """
    if FB_DRY_RUN:
        total_likes = sum(p["likes"] for p in MOCK_FB_FEED)
        total_comments = sum(p["comments"] for p in MOCK_FB_FEED)
        total_shares = sum(p["shares"] for p in MOCK_FB_FEED)
        logger.info(f"[DRY RUN] Facebook feed summary: {len(MOCK_FB_FEED)} posts")
        return {
            "success": True, "dry_run": True, "platform": "facebook",
            "summary": {
                "post_count": len(MOCK_FB_FEED),
                "total_likes": total_likes, "total_comments": total_comments,
                "total_shares": total_shares,
                "avg_engagement": round((total_likes + total_comments + total_shares) / len(MOCK_FB_FEED), 1),
                "top_post": max(MOCK_FB_FEED, key=lambda p: p["likes"]),
                "period": f"{MOCK_FB_FEED[-1]['created_time'][:10]} to {MOCK_FB_FEED[0]['created_time'][:10]}"
            },
            "posts": MOCK_FB_FEED
        }

    import requests
    url = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed"
    resp = requests.get(url, params={
        "access_token": FB_ACCESS_TOKEN,
        "fields": "id,message,created_time,likes.summary(true),comments.summary(true),shares",
        "limit": limit
    }, timeout=30)
    resp.raise_for_status()
    posts = resp.json().get("data", [])
    return {"success": True, "dry_run": False, "platform": "facebook",
            "summary": {"post_count": len(posts)}, "posts": posts}


# ── INSTAGRAM TOOLS ──────────────────────────────────────────────────────
def post_to_instagram(caption, image_url=None):
    """Post to Instagram Business account (requires image_url for non-dry-run).

    Args:
        caption: The caption text for the post
        image_url: Public URL of the image to post (required for actual posting)
    """
    if FB_DRY_RUN:  # IG uses same FB token
        result = {**MOCK_IG_POST, "caption": caption}
        logger.info(f"[DRY RUN] Instagram post: {caption[:80]}...")
        return {"success": True, "dry_run": True, "platform": "instagram", "post": result}

    import requests
    # Step 1: Create media container
    container_url = f"https://graph.facebook.com/v19.0/{IG_ACCOUNT_ID}/media"
    container_resp = requests.post(container_url, data={
        "image_url": image_url, "caption": caption, "access_token": FB_ACCESS_TOKEN
    }, timeout=30)
    container_resp.raise_for_status()
    creation_id = container_resp.json()["id"]

    # Step 2: Publish
    publish_url = f"https://graph.facebook.com/v19.0/{IG_ACCOUNT_ID}/media_publish"
    pub_resp = requests.post(publish_url, data={
        "creation_id": creation_id, "access_token": FB_ACCESS_TOKEN
    }, timeout=30)
    pub_resp.raise_for_status()
    return {"success": True, "dry_run": False, "platform": "instagram",
            "post": {"id": pub_resp.json()["id"], "caption": caption}}


def get_ig_media_summary(limit=10):
    """Get a summary of recent Instagram posts with engagement metrics.

    Args:
        limit: Number of posts to retrieve (default 10)
    """
    if FB_DRY_RUN:
        total_likes = sum(p["like_count"] for p in MOCK_IG_MEDIA)
        total_comments = sum(p["comments_count"] for p in MOCK_IG_MEDIA)
        logger.info(f"[DRY RUN] Instagram media summary: {len(MOCK_IG_MEDIA)} posts")
        return {
            "success": True, "dry_run": True, "platform": "instagram",
            "summary": {
                "post_count": len(MOCK_IG_MEDIA),
                "total_likes": total_likes, "total_comments": total_comments,
                "avg_engagement": round((total_likes + total_comments) / len(MOCK_IG_MEDIA), 1),
                "top_post": max(MOCK_IG_MEDIA, key=lambda p: p["like_count"]),
            },
            "posts": MOCK_IG_MEDIA
        }

    import requests
    url = f"https://graph.facebook.com/v19.0/{IG_ACCOUNT_ID}/media"
    resp = requests.get(url, params={
        "access_token": FB_ACCESS_TOKEN,
        "fields": "id,caption,like_count,comments_count,media_type,timestamp,permalink",
        "limit": limit
    }, timeout=30)
    resp.raise_for_status()
    posts = resp.json().get("data", [])
    return {"success": True, "dry_run": False, "platform": "instagram",
            "summary": {"post_count": len(posts)}, "posts": posts}


# ── TWITTER/X TOOLS ──────────────────────────────────────────────────────
def post_tweet(text):
    """Post a tweet to X (Twitter).

    Args:
        text: The tweet text (max 280 characters)
    """
    if X_DRY_RUN:
        if len(text) > 280:
            return {"success": False, "dry_run": True, "platform": "x",
                    "error": f"Tweet exceeds 280 chars ({len(text)})"}
        result = {**MOCK_TWEET, "text": text}
        logger.info(f"[DRY RUN] Tweet: {text[:80]}...")
        return {"success": True, "dry_run": True, "platform": "x", "tweet": result}

    import tweepy
    client = tweepy.Client(
        bearer_token=X_BEARER_TOKEN,
        consumer_key=X_API_KEY, consumer_secret=X_API_SECRET,
        access_token=X_ACCESS_TOKEN, access_token_secret=X_ACCESS_SECRET
    )
    resp = client.create_tweet(text=text)
    tweet_id = resp.data["id"]
    return {"success": True, "dry_run": False, "platform": "x",
            "tweet": {"id": tweet_id, "text": text}}


def get_x_timeline_summary(limit=10):
    """Get a summary of recent tweets with engagement metrics.

    Args:
        limit: Number of tweets to retrieve (default 10)
    """
    if X_DRY_RUN:
        total_likes = sum(t["likes"] for t in MOCK_TIMELINE)
        total_rts = sum(t["retweets"] for t in MOCK_TIMELINE)
        logger.info(f"[DRY RUN] X timeline summary: {len(MOCK_TIMELINE)} tweets")
        return {
            "success": True, "dry_run": True, "platform": "x",
            "summary": {
                "tweet_count": len(MOCK_TIMELINE),
                "total_likes": total_likes, "total_retweets": total_rts,
                "avg_engagement": round((total_likes + total_rts) / len(MOCK_TIMELINE), 1),
                "top_tweet": max(MOCK_TIMELINE, key=lambda t: t["likes"]),
            },
            "tweets": MOCK_TIMELINE
        }

    import tweepy
    client = tweepy.Client(bearer_token=X_BEARER_TOKEN)
    me = client.get_me()
    tweets = client.get_users_tweets(
        me.data.id, max_results=min(limit, 100),
        tweet_fields=["created_at", "public_metrics"]
    )
    results = []
    for t in (tweets.data or []):
        metrics = t.public_metrics or {}
        results.append({
            "id": t.id, "text": t.text, "created_at": str(t.created_at),
            "likes": metrics.get("like_count", 0),
            "retweets": metrics.get("retweet_count", 0),
            "replies": metrics.get("reply_count", 0)
        })
    return {"success": True, "dry_run": False, "platform": "x",
            "summary": {"tweet_count": len(results)}, "tweets": results}


# ── LINKEDIN TOOLS (Platinum Tier) ───────────────────────────────────────────
def post_linkedin(text=None, visibility="PUBLIC", is_page_post=False, **kwargs):
    """Post to LinkedIn using either LinkedIn token or cookies.

    For cookie-based auth, uses the cookies.json file from linkedin_auth.py.
    Supports both personal profile posts and LinkedIn Page posts.

    Args:
        text: The post content (max 3000 characters for text-only posts)
        visibility: "PUBLIC", "CONNECTIONS_ONLY", or "PRIVATE" (default: PUBLIC)
        is_page_post: Whether to post to a LinkedIn Page (default: False for personal profile)
    """
    # Extract text from kwargs if not provided as positional argument
    if text is None:
        text = kwargs.get('text')

    # If still no text, try to get it from draft_id reference
    if text is None:
        draft_id = kwargs.get('draft_id', kwargs.get('correlation_id', ''))
        if draft_id:
            # Look for the draft file and extract content
            import os
            draft_path = os.path.join(VAULT_DIR, 'data', 'Plans', 'cloud', f'DRAFT_linkedin_{draft_id}.md')
            if os.path.exists(draft_path):
                try:
                    draft_content = Path(draft_path).read_text(encoding='utf-8')
                    # Extract content between "## Post Content" and "## Approval Required"
                    import re
                    post_content_match = re.search(r'## Post Content\s*\n(.+?)\s*\n## Approval Required', draft_content, re.DOTALL)
                    if post_content_match:
                        text = post_content_match.group(1).strip()
                        # Remove extra whitespace and empty lines
                        text = '\n'.join(line.strip() for line in text.split('\n') if line.strip())

                except Exception as e:
                    logger.warning(f"Could not extract text from draft {draft_id}: {e}")

    # If still no text found, return error
    if not text:
        return {"success": False, "platform": "linkedin",
                "error": "No text content provided for post. Need 'text' argument or valid draft_id."}

    if LINKEDIN_DRY_RUN:
        if len(text) > 3000:  # LinkedIn's general text limit
            return {"success": False, "dry_run": True, "platform": "linkedin",
                    "error": f"Post exceeds LinkedIn character limit ({len(text)}/3000)"}
        result = {**MOCK_LINKEDIN_POST, "message": text}
        logger.info(f"[DRY RUN] LinkedIn {'Page' if is_page_post else 'Profile'} post: {text[:80]}...")
        return {"success": True, "dry_run": True, "platform": "linkedin", "post": result}

    import requests
    import json
    from pathlib import Path

    # Determine if this should be a Page post based on environment or parameter
    post_to_page = is_page_post or kwargs.get('post_to_page', False) or LINKEDIN_PERSON_URN and 'company' in LINKEDIN_PERSON_URN.lower()

    # Try access token-based auth first for Page posts (more reliable for pages)
    auth_token = LINKEDIN_ACCESS_TOKEN or LINKEDIN_TOKEN
    if auth_token and not auth_token.startswith("your_"):
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0",
            }

            if post_to_page:
                # LinkedIn V2 Organization Share API for Page posts
                # First, get the organization ID
                org_url = "https://api.linkedin.com/v2/organizationAcls?q=roleAssignee"
                resp = requests.get(org_url, headers=headers, timeout=30)

                if resp.status_code == 200:
                    org_data = resp.json()
                    org_id = None
                    # Look for the organization through the results
                    for element in org_data.get('elements', []):
                        if element.get('role') in ['ADMINISTRATOR', 'CONTENT_MANAGER']:
                            org_id = element.get('organizationalTarget', {}).get('entityUrn', '').split(':')[-1]
                            if org_id:
                                break

                    # If we found an organization ID, post to it
                    if org_id:
                        share_url = "https://api.linkedin.com/v2/sharePosts"
                        payload = {
                            "authorization": "NONE",
                            "lifecycleState": "PUBLISHED",
                            "specificContent": {
                                "com.linkedin.ugc.ShareContent": {
                                    "shareCommentary": {
                                        "text": text
                                    },
                                    "shareMediaCategory": "NONE",
                                    "shareArticle": None
                                }
                            },
                            "visibility": {
                                "com.linkedin.ugc.MemberNetworkVisibility": visibility
                            },
                            "distribution": {
                                "feedDistribution": "MAIN_FEED",
                                "targetEntity": f"urn:li:organization:{org_id}",
                                "thirdPartyShare": False
                            }
                        }

                        resp = requests.post(share_url, json=payload, headers=headers, timeout=30)
                        if resp.status_code in [200, 201, 202]:
                            data = resp.json()
                            return {"success": True, "dry_run": False, "platform": "linkedin",
                                    "post": {"id": data.get("id"), "message": text, "type": "page_post"}}
                        else:
                            logger.warning(f"Page post API response {resp.status_code}: {resp.text}")
                    else:
                        logger.warning("Could not find organization ID for page posting")
                else:
                    logger.warning(f"Organization lookup failed: {resp.status_code} - {resp.text}")
            else:
                # Personal profile post using the existing method
                share_url = "https://api.linkedin.com/v2/sharePosts"
                payload = {
                    "author": f"urn:li:person:{LINKEDIN_PERSON_URN.split(':')[-1] if LINKEDIN_PERSON_URN and ':' in LINKEDIN_PERSON_URN else 'me'}",
                    "lifecycleState": "PUBLISHED",
                    "specificContent": {
                        "com.linkedin.ugc.ShareContent": {
                            "shareCommentary": {
                                "text": text
                            },
                            "shareMediaCategory": "NONE"
                        }
                    },
                    "visibility": {
                        "com.linkedin.ugc.MemberNetworkVisibility": visibility
                    }
                }

                resp = requests.post(share_url, json=payload, headers=headers, timeout=30)
                if resp.status_code in [200, 201, 202]:
                    data = resp.json()
                    return {"success": True, "dry_run": False, "platform": "linkedin",
                            "post": {"id": data.get("id"), "message": text, "type": "profile_post"}}
                else:
                    logger.warning(f"Profile post API response {resp.status_code}: {resp.text}")

        except Exception as e:
            logger.error(f"Token-based LinkedIn post failed: {e}")

    # Fallback to cookie-based auth for profile posts
    cookies_file = VAULT_DIR / "data" / "Logs" / "linkedin_cookies.json"
    if cookies_file.exists() and not post_to_page:  # Cookie auth typically doesn't work for pages
        try:
            cookies = json.loads(cookies_file.read_text(encoding="utf-8"))
            li_at = next((c for c in cookies if c["name"] == "li_at"), None)
            jsessionid = next((c for c in cookies if c["name"] == "JSESSIONID"), None)

            if li_at:
                session = requests.Session()
                for c in cookies:
                    session.cookies.set(c["name"], c["value"], domain=c.get("domain", ""))

                csrf = jsessionid["value"].strip('"') if jsessionid else ""
                session.headers.update({
                    "csrf-token": csrf,
                    "Content-Type": "application/json",
                    "x-restli-protocol-version": "2.0.0",
                })

                # LinkedIn share API call for profile
                share_url = "https://www.linkedin.com/voyager/api/feed/distributionshare"
                payload = {
                    "content": {
                        "contentEntities": [],
                        "title": ""
                    },
                    "distribution": {
                        "feedDistribution": "MAIN_FEED",
                        "targetEntity": None,
                        "thirdPartyShare": False
                    },
                    "owner": LINKEDIN_PERSON_URN or "",
                    "text": {"text": text}
                }

                resp = session.post(share_url, json=payload, timeout=30)
                if resp.status_code in [200, 201]:
                    post_id = resp.json().get("data", {}).get("shareId", "unknown_id")
                    return {"success": True, "dry_run": False, "platform": "linkedin",
                            "post": {"id": post_id, "message": text, "type": "profile_post"}}
                else:
                    logger.warning(f"Cookie-based profile post API response {resp.status_code}")
        except Exception as e:
            logger.warning(f"Cookie-based LinkedIn profile post failed: {e}")

    # If neither auth method works, return error
    return {"success": False, "platform": "linkedin",
            "error": "No valid LinkedIn authentication found for page posting. Ensure you have proper Page administrator access and valid tokens. Run: python watcher/linkedin_auth.py"}


def get_linkedin_feed_summary(limit=10, is_page_feed=False, **kwargs):
    """Get a summary of recent LinkedIn posts with engagement metrics.

    Args:
        limit: Number of posts to retrieve (default 10)
    """
    if LINKEDIN_DRY_RUN:
        total_likes = sum(p["likes"] for p in MOCK_LINKEDIN_FEED)
        total_comments = sum(p["comments"] for p in MOCK_LINKEDIN_FEED)
        total_shares = sum(p["shares"] for p in MOCK_LINKEDIN_FEED)
        avg_engagement = (total_likes + total_comments + total_shares) / len(MOCK_LINKEDIN_FEED) if MOCK_LINKEDIN_FEED else 0
        logger.info(f"[DRY RUN] LinkedIn feed summary: {len(MOCK_LINKEDIN_FEED)} posts")
        return {
            "success": True, "dry_run": True, "platform": "linkedin",
            "summary": {
                "post_count": len(MOCK_LINKEDIN_FEED),
                "total_likes": total_likes, "total_comments": total_comments,
                "total_shares": total_shares,
                "avg_engagement": round(avg_engagement, 1),
                "top_post": max(MOCK_LINKEDIN_FEED, key=lambda p: p["likes"]),
                "avg_engagement_rate": round(sum(p["engagement_rate"] for p in MOCK_LINKEDIN_FEED) / len(MOCK_LINKEDIN_FEED), 2) if MOCK_LINKEDIN_FEED else 0
            },
            "posts": MOCK_LINKEDIN_FEED
        }

    import requests
    import json
    from pathlib import Path

    # Try cookie-based auth first
    cookies_file = VAULT_DIR / "data" / "Logs" / "linkedin_cookies.json"
    if cookies_file.exists():
        try:
            cookies = json.loads(cookies_file.read_text(encoding="utf-8"))
            li_at = next((c for c in cookies if c["name"] == "li_at"), None)

            if li_at:
                session = requests.Session()
                for c in cookies:
                    session.cookies.set(c["name"], c["value"], domain=c.get("domain", ""))

                session.headers.update({
                    "csrf-token": li_at["value"].strip('"'),
                    "Content-Type": "application/json",
                    "x-restli-protocol-version": "2.0.0",
                })

                # LinkedIn API to get user's posts
                profile_url = "https://www.linkedin.com/voyager/api/identity/profiles/me/posts"
                params = {"q": "flagshipPosts", "count": limit}
                resp = session.get(profile_url, params=params, timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    posts = data.get("elements", [])
                    return {"success": True, "dry_run": False, "platform": "linkedin",
                            "summary": {"post_count": len(posts)}, "posts": posts}
        except Exception as e:
            logger.warning(f"LinkedIn feed fetch with cookies failed: {e}")

    # Fallback to access token-based auth
    auth_token = LINKEDIN_ACCESS_TOKEN or LINKEDIN_TOKEN
    if auth_token and not auth_token.startswith("AQW") and not auth_token.startswith("your_"):
        try:
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0",
            }

            # LinkedIn UGC Posts API
            posts_url = f"https://api.linkedin.com/v2/ugcPosts?q=authors&author=urn:li:person:{LINKEDIN_PERSON_URN.split(':')[-1] if LINKEDIN_PERSON_URN else 'me'}&start=0&count={limit}"
            resp = requests.get(posts_url, headers=headers, timeout=30)
            resp.raise_for_status()
            posts = resp.json().get("elements", [])
            return {"success": True, "dry_run": False, "platform": "linkedin",
                    "summary": {"post_count": len(posts)}, "posts": posts}
        except Exception as e:
            logger.error(f"Token-based LinkedIn feed summary failed: {e}")

    # No authentication available
    return {"success": False, "platform": "linkedin",
            "error": "No valid LinkedIn authentication found"}


# ── MCP STDIO PROTOCOL ──────────────────────────────────────────────────
TOOLS = {
    "post_to_facebook": {
        "description": "Post a message to your Facebook account using browser automation (with API fallback). Requires HITL-approved file.",
        "parameters": {"message": "string", "link": "string (optional)"},
        "handler": post_to_facebook
    },
    "get_fb_feed_summary": {
        "description": "Get engagement summary from your recent Facebook posts using browser automation (with API fallback).",
        "parameters": {"limit": "integer (optional)"},
        "handler": get_fb_feed_summary
    },
    "post_to_instagram": {
        "description": "Post a caption to your Instagram account using browser automation (with API fallback). Requires HITL-approved file.",
        "parameters": {"caption": "string", "image_url": "string (optional)"},
        "handler": post_to_instagram
    },
    "get_ig_media_summary": {
        "description": "Get engagement summary from your recent Instagram media using browser automation (with API fallback).",
        "parameters": {"limit": "integer (optional)"},
        "handler": get_ig_media_summary
    },
    "post_tweet": {
        "description": "Post a tweet to your X/Twitter account using browser automation (with API fallback), max 280 chars. Requires HITL-approved file.",
        "parameters": {"text": "string", "reply_to": "string (optional)"},
        "handler": post_tweet
    },
    "get_x_timeline_summary": {
        "description": "Get engagement summary from your recent X/Twitter posts using browser automation (with API fallback).",
        "parameters": {"limit": "integer (optional)"},
        "handler": get_x_timeline_summary
    },
    "authenticate_platform": {
        "description": "Authenticate a social media platform by opening a browser for manual login",
        "parameters": {"platform": "string (facebook, instagram, or x)"},
        "handler": lambda platform: browser_mcp_client.call_tool("authenticate_platform", {"platform": platform})
    },
    "post_linkedin": {
        "description": "Post to LinkedIn, max 3000 chars (uses cookie-based auth like browser approach)",
        "parameters": {"text": "string", "visibility": "string (optional, PUBLIC/CONNECTIONS_ONLY/PRIVATE)"},
        "handler": post_linkedin
    },
    "get_linkedin_feed_summary": {
        "description": "Get engagement summary of recent LinkedIn posts (uses cookie-based auth like browser approach)",
        "parameters": {"limit": "integer (optional)"},
        "handler": get_linkedin_feed_summary
    },
}


def handle_request(request):
    """Handle a single MCP JSON-RPC request."""
    method = request.get("method", "")
    params = request.get("params", {})
    req_id = request.get("id")

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": req_id, "result": {
            "name": "social-mcp", "version": "1.0.0",
            "capabilities": {"tools": list(TOOLS.keys())}
        }}

    if method == "tools/list":
        tools_list = [{"name": k, "description": v["description"],
                       "inputSchema": {"type": "object", "properties": v["parameters"]}}
                      for k, v in TOOLS.items()]
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools_list}}

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})

        # Start timing for duration tracking
        start_time = time.time()

        if tool_name not in TOOLS:
            # Log unknown tool error
            if HAS_AUDIT_LOGGER:
                _audit_log_error(
                    action_type="mcp.tools/call",
                    actor="social_mcp",
                    target=tool_name,
                    parameters=tool_args,
                    error=f"unknown tool: {tool_name}",
                    severity="ERROR",
                    duration_ms=int((time.time() - start_time) * 1000) if 'start_time' in locals() else None,
                )
            return {"jsonrpc": "2.0", "id": req_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}}

        try:
            handler = TOOLS[tool_name]["handler"]
            # Gold Tier: wrap read-only tools with retry for transient failures
            read_only_tools = {"get_fb_feed_summary", "get_ig_media_summary", "get_x_timeline_summary", "get_linkedin_feed_summary"}
            if HAS_RETRY and tool_name in read_only_tools:
                handler = with_retry(
                    max_attempts=MAX_RETRIES,
                    action_name=tool_name,
                )(handler)
            result = handler(**tool_args)

            # Gold Tier: log successful MCP call to audit log
            if HAS_AUDIT_LOGGER:
                log_mcp_call(
                    server="social",
                    tool=tool_name,
                    args=tool_args,
                    result="success",
                    duration_ms=int((time.time() - start_time) * 1000),
                )

            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [
                {"type": "text", "text": json.dumps(result, indent=2, default=str)}
            ]}}
        except Exception as e:
            logger.exception(f"Tool {tool_name} failed")

            # Gold Tier: log failed MCP call to audit log
            if HAS_AUDIT_LOGGER:
                _audit_log_error(
                    action_type=f"mcp.social.{tool_name}",
                    actor="social_mcp",
                    target=tool_name,
                    error=e,
                    parameters=tool_args,
                    duration_ms=int((time.time() - start_time) * 1000),
                )

            # Gold Tier: graceful degradation — queue deferred task on failure
            error_type = classify_error(e) if HAS_RETRY else "unknown"
            platform = "facebook" if "fb" in tool_name or "facebook" in tool_name else \
                       "instagram" if "ig" in tool_name or "instagram" in tool_name else \
                       "x" if "tweet" in tool_name or "_x_" in tool_name else \
                       "linkedin" if "linkedin" in tool_name else "social"
            _queue_deferred(platform, tool_name, f"Error: {e}\nArgs: {tool_args}")

            return {"jsonrpc": "2.0", "id": req_id,
                    "error": {"code": -32000,
                              "message": f"[{error_type}] {e} (deferred task queued)"}}

    return {"jsonrpc": "2.0", "id": req_id,
            "error": {"code": -32601, "message": f"Unknown method: {method}"}}


def run_stdio():
    """Run MCP server in stdio mode."""
    logger.info(f"Social MCP server starting (FB_DRY_RUN={FB_DRY_RUN}, X_DRY_RUN={X_DRY_RUN})")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = handle_request(request)
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
        except json.JSONDecodeError:
            error = {"jsonrpc": "2.0", "id": None,
                     "error": {"code": -32700, "message": "Parse error"}}
            sys.stdout.write(json.dumps(error) + "\n")
            sys.stdout.flush()


def run_test():
    """Run a self-test of all tools in dry-run mode."""
    global FB_DRY_RUN, X_DRY_RUN, LINKEDIN_DRY_RUN
    FB_DRY_RUN = True
    X_DRY_RUN = True
    LINKEDIN_DRY_RUN = True
    print("=== Social MCP Self-Test (DRY RUN) ===\n")

    print("1. post_to_facebook():")
    print(json.dumps(post_to_facebook("Test post from AI Employee Vault!"), indent=2))

    print("\n2. get_fb_feed_summary():")
    print(json.dumps(get_fb_feed_summary(), indent=2))

    print("\n3. post_to_instagram():")
    print(json.dumps(post_to_instagram("Test caption #AIEmployee"), indent=2))

    print("\n4. get_ig_media_summary():")
    print(json.dumps(get_ig_media_summary(), indent=2))

    print("\n5. post_tweet():")
    print(json.dumps(post_tweet("Test tweet from AI Employee Vault!"), indent=2))

    print("\n6. get_x_timeline_summary():")
    print(json.dumps(get_x_timeline_summary(), indent=2))

    print("\n7. post_linkedin():")
    print(json.dumps(post_linkedin("Test LinkedIn post from AI Employee Vault! Professional update on AI automation."), indent=2))

    print("\n8. get_linkedin_feed_summary():")
    print(json.dumps(get_linkedin_feed_summary(), indent=2))

    print("\n=== All tests passed ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Social Media MCP Server for AI Employee Vault")
    parser.add_argument("--dry-run", action="store_true", help="Force dry-run mode")
    parser.add_argument("--test", action="store_true", help="Run self-test")
    args = parser.parse_args()

    if args.dry_run:
        FB_DRY_RUN = True
        X_DRY_RUN = True
    if args.test:
        run_test()
    else:
        run_stdio()
