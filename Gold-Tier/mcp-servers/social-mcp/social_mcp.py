#!/usr/bin/env python3
"""
Social Media MCP Server — Gold Tier

Unified interface for Facebook, Instagram, and Twitter/X posting and feed summaries.
Uses Facebook Graph API v19.0, Instagram Graph API, and X API v2 (via tweepy).

DRY_RUN mode returns realistic mock data without calling any APIs.

Usage:
    python social_mcp.py                # Start MCP server
    python social_mcp.py --dry-run      # Test with mock data
    python social_mcp.py --test         # Run self-test
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


# ── MCP STDIO PROTOCOL ──────────────────────────────────────────────────
TOOLS = {
    "post_to_facebook": {
        "description": "Post a message to the Facebook Page",
        "parameters": {"message": "string"},
        "handler": post_to_facebook
    },
    "get_fb_feed_summary": {
        "description": "Get engagement summary of recent Facebook posts",
        "parameters": {"limit": "integer (optional)"},
        "handler": get_fb_feed_summary
    },
    "post_to_instagram": {
        "description": "Post to Instagram Business account",
        "parameters": {"caption": "string", "image_url": "string (optional)"},
        "handler": post_to_instagram
    },
    "get_ig_media_summary": {
        "description": "Get engagement summary of recent Instagram posts",
        "parameters": {"limit": "integer (optional)"},
        "handler": get_ig_media_summary
    },
    "post_tweet": {
        "description": "Post a tweet to X (Twitter), max 280 chars",
        "parameters": {"text": "string"},
        "handler": post_tweet
    },
    "get_x_timeline_summary": {
        "description": "Get engagement summary of recent tweets",
        "parameters": {"limit": "integer (optional)"},
        "handler": get_x_timeline_summary
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
                    result=f"unknown tool: {tool_name}",
                    severity="ERROR",
                    duration_ms=int((time.time() - start_time) * 1000) if 'start_time' in locals() else None,
                )
            return {"jsonrpc": "2.0", "id": req_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}}

        try:
            handler = TOOLS[tool_name]["handler"]
            # Gold Tier: wrap read-only tools with retry for transient failures
            read_only_tools = {"get_fb_feed_summary", "get_ig_media_summary", "get_x_timeline_summary"}
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
                       "x" if "tweet" in tool_name or "_x_" in tool_name else "social"
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
    global FB_DRY_RUN, X_DRY_RUN
    FB_DRY_RUN = True
    X_DRY_RUN = True
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
