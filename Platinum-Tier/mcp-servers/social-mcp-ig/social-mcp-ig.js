#!/usr/bin/env node
/**
 * Instagram MCP Server (Gold Tier)
 *
 * Posts media and retrieves engagement summaries via the Instagram Graph API.
 *
 * Transport : stdio (stdin/stdout newline-delimited JSON-RPC 2.0)
 * API       : Instagram Graph API (Business/Creator accounts via Facebook Graph)
 * Safety    : IG_DRY_RUN env — when "true", logs but never posts
 *
 * Env vars (from .env):
 *   IG_BUSINESS_ACCOUNT_ID — Instagram Business Account ID
 *   FB_ACCESS_TOKEN        — Page Access Token (shared with FB, long-lived)
 *   IG_DRY_RUN             — "true" to skip actual API calls
 *
 * Run:
 *   cd mcp-servers/social-mcp-ig && node social-mcp-ig.js
 */

import { createInterface } from "node:readline";

// ── CONFIG ───────────────────────────────────────────────────────────────
const IG_ACCOUNT_ID = process.env.IG_BUSINESS_ACCOUNT_ID || "";
const ACCESS_TOKEN  = process.env.FB_ACCESS_TOKEN || "";
const DRY_RUN       = (process.env.IG_DRY_RUN || "true").toLowerCase() === "true";
const API_BASE      = "https://graph.facebook.com/v19.0";

const log = (level, msg) =>
  process.stderr.write(`${new Date().toISOString()} [IG-MCP] ${level}: ${msg}\n`);

// ── MOCK DATA ────────────────────────────────────────────────────────────
const MOCK_MEDIA = {
  id: "17841405793049573",
  media_url: "https://instagram.com/p/mock_post_id/",
  caption: "",
  media_type: "IMAGE",
  timestamp: new Date().toISOString(),
};

const MOCK_FEED = [
  { id: "ig_001", caption: "Behind the scenes at GIAIC Hackathon #AI #tech",
    media_type: "IMAGE", timestamp: "2026-02-18T10:00:00Z",
    like_count: 234, comments_count: 18 },
  { id: "ig_002", caption: "Our team building the future of AI assistants",
    media_type: "CAROUSEL_ALBUM", timestamp: "2026-02-15T16:00:00Z",
    like_count: 412, comments_count: 45 },
  { id: "ig_003", caption: "Celebrating Q1 milestones! #startup #growth",
    media_type: "IMAGE", timestamp: "2026-02-12T09:30:00Z",
    like_count: 189, comments_count: 27 },
];

// ── HELPERS ──────────────────────────────────────────────────────────────
async function graphFetch(endpoint, method = "GET", body = null) {
  const url = `${API_BASE}${endpoint}`;
  const opts = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(url, opts);
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Graph API ${res.status}: ${err}`);
  }
  return res.json();
}

// ── TOOL: post_media ─────────────────────────────────────────────────────
async function postMedia({ caption, image_url, media_type }) {
  if (!caption) return { success: false, error: "caption is required" };
  if (!image_url && !DRY_RUN) return { success: false, error: "image_url is required for live posts" };

  const type = (media_type || "IMAGE").toUpperCase();

  if (DRY_RUN) {
    const mock = { ...MOCK_MEDIA, caption, media_type: type };
    log("INFO", `[DRY RUN] Would post to Instagram (${type}): "${caption.slice(0, 80)}..."`);
    return { success: true, dry_run: true, media: mock };
  }

  // Step 1: Create media container
  const containerParams = new URLSearchParams({
    caption,
    access_token: ACCESS_TOKEN,
  });
  if (type === "IMAGE") {
    containerParams.append("image_url", image_url);
  } else if (type === "VIDEO") {
    containerParams.append("video_url", image_url);
    containerParams.append("media_type", "REELS");
  }

  const container = await graphFetch(
    `/${IG_ACCOUNT_ID}/media?${containerParams}`, "POST"
  );

  // Step 2: Publish the container
  const publishParams = new URLSearchParams({
    creation_id: container.id,
    access_token: ACCESS_TOKEN,
  });
  const published = await graphFetch(
    `/${IG_ACCOUNT_ID}/media_publish?${publishParams}`, "POST"
  );

  log("INFO", `Posted to Instagram: ${published.id}`);
  return {
    success: true,
    dry_run: false,
    media: {
      id: published.id,
      media_url: `https://instagram.com/p/${published.id}/`,
      caption,
      media_type: type,
      timestamp: new Date().toISOString(),
    },
  };
}

// ── TOOL: get_summary ────────────────────────────────────────────────────
async function getSummary({ limit }) {
  const count = limit || 10;

  if (DRY_RUN) {
    const posts = MOCK_FEED.slice(0, count);
    const totalLikes = posts.reduce((s, p) => s + p.like_count, 0);
    const totalComments = posts.reduce((s, p) => s + p.comments_count, 0);
    log("INFO", `[DRY RUN] Returning ${posts.length} mock IG media items`);
    return {
      success: true,
      dry_run: true,
      summary: {
        platform: "instagram",
        posts_analyzed: posts.length,
        total_likes: totalLikes,
        total_comments: totalComments,
        total_engagement: totalLikes + totalComments,
        top_post: posts.sort((a, b) =>
          (b.like_count + b.comments_count) - (a.like_count + a.comments_count)
        )[0],
        period: "last_7_days",
      },
      posts,
    };
  }

  const fields = "id,caption,media_type,timestamp,like_count,comments_count,media_url";
  const data = await graphFetch(
    `/${IG_ACCOUNT_ID}/media?fields=${fields}&limit=${count}&access_token=${ACCESS_TOKEN}`
  );

  const posts = (data.data || []).map((p) => ({
    id: p.id,
    caption: (p.caption || "").slice(0, 200),
    media_type: p.media_type,
    timestamp: p.timestamp,
    like_count: p.like_count || 0,
    comments_count: p.comments_count || 0,
  }));

  const totalLikes = posts.reduce((s, p) => s + p.like_count, 0);
  const totalComments = posts.reduce((s, p) => s + p.comments_count, 0);

  return {
    success: true,
    dry_run: false,
    summary: {
      platform: "instagram",
      posts_analyzed: posts.length,
      total_likes: totalLikes,
      total_comments: totalComments,
      total_engagement: totalLikes + totalComments,
      top_post: posts.sort((a, b) =>
        (b.like_count + b.comments_count) - (a.like_count + a.comments_count)
      )[0] || null,
      period: "last_7_days",
    },
    posts,
  };
}

// ── MCP TOOL DEFINITIONS ─────────────────────────────────────────────────
const TOOLS = [
  {
    name: "post_media",
    description: "Post an image or carousel to Instagram. Requires HITL-approved file.",
    inputSchema: {
      type: "object",
      properties: {
        caption:    { type: "string", description: "The post caption text" },
        image_url:  { type: "string", description: "Public URL of the image to post" },
        media_type: { type: "string", description: "IMAGE or CAROUSEL_ALBUM (default IMAGE)", enum: ["IMAGE", "CAROUSEL_ALBUM", "VIDEO"] },
      },
      required: ["caption"],
    },
  },
  {
    name: "get_summary",
    description: "Get engagement summary (likes, comments) from recent Instagram media.",
    inputSchema: {
      type: "object",
      properties: {
        limit: { type: "number", description: "Number of recent media items to analyze (default 10)" },
      },
    },
  },
];

const HANDLERS = { post_media: postMedia, get_summary: getSummary };

// ── JSON-RPC STDIO TRANSPORT ─────────────────────────────────────────────
function handleRequest(req) {
  const { method, params, id } = req;

  if (method === "initialize") {
    return { jsonrpc: "2.0", id, result: {
      name: "social-mcp-ig", version: "1.0.0",
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
log("INFO", `Instagram MCP server starting (DRY_RUN=${DRY_RUN})`);

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
