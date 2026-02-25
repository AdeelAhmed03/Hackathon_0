#!/usr/bin/env node
/**
 * Twitter/X MCP Server (Gold Tier)
 *
 * Posts tweets and retrieves engagement summaries via the X API v2.
 *
 * Transport : stdio (stdin/stdout newline-delimited JSON-RPC 2.0)
 * API       : X API v2 (OAuth 1.0a User Context for posting, Bearer for reading)
 * Safety    : X_DRY_RUN env — when "true", logs but never posts
 *
 * Env vars (from .env):
 *   X_API_KEY        — API Key (Consumer Key)
 *   X_API_SECRET     — API Secret (Consumer Secret)
 *   X_ACCESS_TOKEN   — Access Token
 *   X_ACCESS_SECRET  — Access Token Secret
 *   X_BEARER_TOKEN   — Bearer Token (for read-only endpoints)
 *   X_DRY_RUN        — "true" to skip actual API calls
 *
 * Run:
 *   cd mcp-servers/social-mcp-x && node social-mcp-x.js
 */

import { createInterface } from "node:readline";
import { createHmac, randomBytes } from "node:crypto";

// ── CONFIG ───────────────────────────────────────────────────────────────
const API_KEY        = process.env.X_API_KEY || "";
const API_SECRET     = process.env.X_API_SECRET || "";
const ACCESS_TOKEN   = process.env.X_ACCESS_TOKEN || "";
const ACCESS_SECRET  = process.env.X_ACCESS_SECRET || "";
const BEARER_TOKEN   = process.env.X_BEARER_TOKEN || "";
const DRY_RUN        = (process.env.X_DRY_RUN || "true").toLowerCase() === "true";
const API_BASE       = "https://api.twitter.com/2";
const MAX_TWEET_LEN  = 280;

const log = (level, msg) =>
  process.stderr.write(`${new Date().toISOString()} [X-MCP] ${level}: ${msg}\n`);

// ── MOCK DATA ────────────────────────────────────────────────────────────
const MOCK_TWEET = {
  id: "1892345678901234567",
  text: "",
  tweet_url: "https://twitter.com/user/status/1892345678901234567",
  created_at: new Date().toISOString(),
};

const MOCK_TIMELINE = [
  { id: "x_001", text: "Excited to share our latest AI Employee project at GIAIC! #AI #hackathon",
    created_at: "2026-02-18T12:00:00Z",
    like_count: 89, retweet_count: 34, reply_count: 12, impression_count: 4200 },
  { id: "x_002", text: "Just deployed our Odoo MCP integration. Accounting meets AI. The future is here.",
    created_at: "2026-02-16T08:30:00Z",
    like_count: 156, retweet_count: 67, reply_count: 23, impression_count: 7800 },
  { id: "x_003", text: "Building in public: our AI assistant now handles FB, IG, and X posts autonomously",
    created_at: "2026-02-13T15:00:00Z",
    like_count: 243, retweet_count: 98, reply_count: 41, impression_count: 12500 },
];

// ── OAUTH 1.0a SIGNATURE ─────────────────────────────────────────────────
function generateOAuthHeader(method, url, params = {}) {
  const oauthParams = {
    oauth_consumer_key: API_KEY,
    oauth_nonce: randomBytes(16).toString("hex"),
    oauth_signature_method: "HMAC-SHA1",
    oauth_timestamp: Math.floor(Date.now() / 1000).toString(),
    oauth_token: ACCESS_TOKEN,
    oauth_version: "1.0",
  };

  const allParams = { ...oauthParams, ...params };
  const sortedKeys = Object.keys(allParams).sort();
  const paramString = sortedKeys
    .map((k) => `${encodeURIComponent(k)}=${encodeURIComponent(allParams[k])}`)
    .join("&");

  const baseString = [
    method.toUpperCase(),
    encodeURIComponent(url),
    encodeURIComponent(paramString),
  ].join("&");

  const signingKey = `${encodeURIComponent(API_SECRET)}&${encodeURIComponent(ACCESS_SECRET)}`;
  const signature = createHmac("sha1", signingKey).update(baseString).digest("base64");

  oauthParams.oauth_signature = signature;

  const headerParts = Object.keys(oauthParams)
    .sort()
    .map((k) => `${encodeURIComponent(k)}="${encodeURIComponent(oauthParams[k])}"`)
    .join(", ");

  return `OAuth ${headerParts}`;
}

// ── TOOL: post_tweet ─────────────────────────────────────────────────────
async function postTweet({ text, reply_to }) {
  if (!text) return { success: false, error: "text is required" };
  if (text.length > MAX_TWEET_LEN) {
    return { success: false, error: `Tweet exceeds ${MAX_TWEET_LEN} characters (got ${text.length})` };
  }

  if (DRY_RUN) {
    const mock = { ...MOCK_TWEET, text };
    log("INFO", `[DRY RUN] Would tweet: "${text.slice(0, 80)}..."`);
    return { success: true, dry_run: true, tweet: mock };
  }

  const url = `${API_BASE}/tweets`;
  const body = { text };
  if (reply_to) body.reply = { in_reply_to_tweet_id: reply_to };

  const authHeader = generateOAuthHeader("POST", url);
  const res = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: authHeader,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`X API ${res.status}: ${err}`);
  }

  const data = await res.json();
  const tweetId = data.data?.id;
  log("INFO", `Tweeted: ${tweetId}`);

  return {
    success: true,
    dry_run: false,
    tweet: {
      id: tweetId,
      text,
      tweet_url: `https://twitter.com/user/status/${tweetId}`,
      created_at: new Date().toISOString(),
    },
  };
}

// ── TOOL: get_summary ────────────────────────────────────────────────────
async function getSummary({ limit }) {
  const count = limit || 10;

  if (DRY_RUN) {
    const tweets = MOCK_TIMELINE.slice(0, count);
    const totalLikes = tweets.reduce((s, t) => s + t.like_count, 0);
    const totalRetweets = tweets.reduce((s, t) => s + t.retweet_count, 0);
    const totalReplies = tweets.reduce((s, t) => s + t.reply_count, 0);
    const totalImpressions = tweets.reduce((s, t) => s + t.impression_count, 0);
    log("INFO", `[DRY RUN] Returning ${tweets.length} mock tweets`);
    return {
      success: true,
      dry_run: true,
      summary: {
        platform: "x",
        tweets_analyzed: tweets.length,
        total_likes: totalLikes,
        total_retweets: totalRetweets,
        total_replies: totalReplies,
        total_impressions: totalImpressions,
        total_engagement: totalLikes + totalRetweets + totalReplies,
        top_tweet: tweets.sort((a, b) =>
          (b.like_count + b.retweet_count + b.reply_count) -
          (a.like_count + a.retweet_count + a.reply_count)
        )[0],
        period: "last_7_days",
      },
      tweets,
    };
  }

  // Use Bearer token for read-only user timeline
  const fields = "created_at,public_metrics,text";
  const url = `${API_BASE}/users/me/tweets?max_results=${Math.min(count, 100)}&tweet.fields=${fields}`;

  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${BEARER_TOKEN}` },
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`X API ${res.status}: ${err}`);
  }

  const data = await res.json();
  const tweets = (data.data || []).map((t) => ({
    id: t.id,
    text: t.text.slice(0, 280),
    created_at: t.created_at,
    like_count: t.public_metrics?.like_count || 0,
    retweet_count: t.public_metrics?.retweet_count || 0,
    reply_count: t.public_metrics?.reply_count || 0,
    impression_count: t.public_metrics?.impression_count || 0,
  }));

  const totalLikes = tweets.reduce((s, t) => s + t.like_count, 0);
  const totalRetweets = tweets.reduce((s, t) => s + t.retweet_count, 0);
  const totalReplies = tweets.reduce((s, t) => s + t.reply_count, 0);
  const totalImpressions = tweets.reduce((s, t) => s + t.impression_count, 0);

  return {
    success: true,
    dry_run: false,
    summary: {
      platform: "x",
      tweets_analyzed: tweets.length,
      total_likes: totalLikes,
      total_retweets: totalRetweets,
      total_replies: totalReplies,
      total_impressions: totalImpressions,
      total_engagement: totalLikes + totalRetweets + totalReplies,
      top_tweet: tweets.sort((a, b) =>
        (b.like_count + b.retweet_count + b.reply_count) -
        (a.like_count + a.retweet_count + a.reply_count)
      )[0] || null,
      period: "last_7_days",
    },
    tweets,
  };
}

// ── MCP TOOL DEFINITIONS ─────────────────────────────────────────────────
const TOOLS = [
  {
    name: "post_tweet",
    description: "Post a tweet to X/Twitter. Max 280 characters. Requires HITL-approved file.",
    inputSchema: {
      type: "object",
      properties: {
        text:     { type: "string", description: "The tweet text (max 280 chars)" },
        reply_to: { type: "string", description: "Optional tweet ID to reply to" },
      },
      required: ["text"],
    },
  },
  {
    name: "get_summary",
    description: "Get engagement summary (likes, retweets, replies, impressions) from recent tweets.",
    inputSchema: {
      type: "object",
      properties: {
        limit: { type: "number", description: "Number of recent tweets to analyze (default 10)" },
      },
    },
  },
];

const HANDLERS = { post_tweet: postTweet, get_summary: getSummary };

// ── JSON-RPC STDIO TRANSPORT ─────────────────────────────────────────────
function handleRequest(req) {
  const { method, params, id } = req;

  if (method === "initialize") {
    return { jsonrpc: "2.0", id, result: {
      name: "social-mcp-x", version: "1.0.0",
      capabilities: { tools: TOOLS.map((t) => t.name) },
    }};
  }

  if (method === "tools/list") {
    return { jsonrpc: "2.0", id, result: { tools: TOOLS } };
  }

  if (method === "tools/call") {
    const toolName = params?.name;
    const toolArgs = params?.arguments || {};
    const handler = HANDLERS[toolName];
    if (!handler) {
      return { jsonrpc: "2.0", id, error: { code: -32601, message: `Unknown tool: ${toolName}` } };
    }
    return handler(toolArgs)
      .then((result) => ({
        jsonrpc: "2.0", id,
        result: { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] },
      }))
      .catch((err) => ({
        jsonrpc: "2.0", id,
        error: { code: -32000, message: err.message },
      }));
  }

  return { jsonrpc: "2.0", id, error: { code: -32601, message: `Unknown method: ${method}` } };
}

// ── MAIN ─────────────────────────────────────────────────────────────────
log("INFO", `X/Twitter MCP server starting (DRY_RUN=${DRY_RUN})`);

const rl = createInterface({ input: process.stdin, terminal: false });

rl.on("line", async (line) => {
  if (!line.trim()) return;
  try {
    const req = JSON.parse(line);
    const res = await handleRequest(req);
    process.stdout.write(JSON.stringify(res) + "\n");
  } catch (e) {
    process.stdout.write(
      JSON.stringify({ jsonrpc: "2.0", id: null, error: { code: -32700, message: "Parse error" } }) + "\n"
    );
  }
});
