#!/usr/bin/env node
/**
 * Facebook MCP Server (Gold Tier)
 *
 * Posts messages and retrieves engagement summaries via the Facebook Graph API v19.0.
 *
 * Transport : stdio (stdin/stdout newline-delimited JSON-RPC 2.0)
 * API       : Facebook Graph API (Page tokens)
 * Safety    : FB_DRY_RUN env — when "true", logs but never posts
 *
 * Env vars (from .env):
 *   FB_PAGE_ID        — Facebook Page ID
 *   FB_ACCESS_TOKEN   — Page Access Token (long-lived)
 *   FB_DRY_RUN        — "true" to skip actual API calls
 *
 * Run:
 *   cd mcp-servers/social-mcp-fb && npm install && node social-mcp-fb.js
 */

import { createInterface } from "node:readline";

// ── CONFIG ───────────────────────────────────────────────────────────────
const PAGE_ID      = process.env.FB_PAGE_ID || "";
const ACCESS_TOKEN = process.env.FB_ACCESS_TOKEN || "";
const DRY_RUN      = (process.env.FB_DRY_RUN || "true").toLowerCase() === "true";
const API_BASE     = "https://graph.facebook.com/v19.0";

const log = (level, msg) =>
  process.stderr.write(`${new Date().toISOString()} [FB-MCP] ${level}: ${msg}\n`);

// ── MOCK DATA ────────────────────────────────────────────────────────────
const MOCK_POST = {
  id: "123456789_987654321",
  post_url: "https://facebook.com/123456789/posts/987654321",
  message: "",
  created_time: new Date().toISOString(),
};

const MOCK_FEED = [
  { id: "123_001", message: "Excited to announce our Q1 results!", created_time: "2026-02-18T09:00:00Z",
    likes: 47, comments: 12, shares: 8 },
  { id: "123_002", message: "New partnership with TechStart Inc!", created_time: "2026-02-15T14:30:00Z",
    likes: 85, comments: 23, shares: 15 },
  { id: "123_003", message: "Join us at the GIAIC Hackathon this weekend", created_time: "2026-02-12T11:00:00Z",
    likes: 132, comments: 31, shares: 44 },
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
    const errorData = await res.json().catch(() => ({})); // Parse error response if possible
    throw new Error(`Graph API ${res.status}: ${err} ${JSON.stringify(errorData)}`);
  }
  return res.json();
}

// ── TOOL: post_message ───────────────────────────────────────────────────
async function postMessage({ message, link }) {
  if (!message) return { success: false, error: "message is required" };

  if (DRY_RUN) {
    const mock = { ...MOCK_POST, message, link: link || null };
    log("INFO", `[DRY RUN] Would post to Facebook: "${message.slice(0, 80)}..."`);
    return { success: true, dry_run: true, post: mock };
  }

  const params = new URLSearchParams({
    message,
    access_token: ACCESS_TOKEN,
  });
  if (link) params.append("link", link);

  const data = await graphFetch(`/${PAGE_ID}/feed?${params}`, "POST");
  log("INFO", `Posted to Facebook: ${data.id}`);
  return {
    success: true,
    dry_run: false,
    post: {
      id: data.id,
      post_url: `https://facebook.com/${data.id.replace("_", "/posts/")}`,
      message,
      created_time: new Date().toISOString(),
    },
  };
}

// ── TOOL: get_summary ────────────────────────────────────────────────────
async function getSummary({ limit }) {
  const count = limit || 10;

  if (DRY_RUN) {
    const posts = MOCK_FEED.slice(0, count);
    const totalLikes = posts.reduce((s, p) => s + p.likes, 0);
    const totalComments = posts.reduce((s, p) => s + p.comments, 0);
    const totalShares = posts.reduce((s, p) => s + p.shares, 0);
    log("INFO", `[DRY RUN] Returning ${posts.length} mock FB posts`);
    return {
      success: true,
      dry_run: true,
      summary: {
        platform: "facebook",
        posts_analyzed: posts.length,
        total_likes: totalLikes,
        total_comments: totalComments,
        total_shares: totalShares,
        total_engagement: totalLikes + totalComments + totalShares,
        top_post: posts.sort((a, b) => (b.likes + b.comments + b.shares) - (a.likes + a.comments + a.shares))[0],
        period: "last_7_days",
      },
      posts,
    };
  }

  const fields = "message,created_time,likes.summary(true),comments.summary(true),shares";
  const data = await graphFetch(
    `/${PAGE_ID}/feed?fields=${fields}&limit=${count}&access_token=${ACCESS_TOKEN}`
  );

  const posts = (data.data || []).map((p) => ({
    id: p.id,
    message: (p.message || "").slice(0, 200),
    created_time: p.created_time,
    likes: p.likes?.summary?.total_count || 0,
    comments: p.comments?.summary?.total_count || 0,
    shares: p.shares?.count || 0,
  }));

  const totalLikes = posts.reduce((s, p) => s + p.likes, 0);
  const totalComments = posts.reduce((s, p) => s + p.comments, 0);
  const totalShares = posts.reduce((s, p) => s + p.shares, 0);

  return {
    success: true,
    dry_run: false,
    summary: {
      platform: "facebook",
      posts_analyzed: posts.length,
      total_likes: totalLikes,
      total_comments: totalComments,
      total_shares: totalShares,
      total_engagement: totalLikes + totalComments + totalShares,
      top_post: posts.sort((a, b) => (b.likes + b.comments + b.shares) - (a.likes + a.comments + a.shares))[0] || null,
      period: "last_7_days",
    },
    posts,
  };
}

// ── MCP TOOL DEFINITIONS ─────────────────────────────────────────────────
const TOOLS = [
  {
    name: "post_message",
    description: "Post a message to the Facebook Page. Requires HITL-approved file.",
    inputSchema: {
      type: "object",
      properties: {
        message: { type: "string", description: "The post text content" },
        link:    { type: "string", description: "Optional URL to attach" },
      },
      required: ["message"],
    },
  },
  {
    name: "get_summary",
    description: "Get engagement summary (likes, comments, shares) from recent Facebook posts.",
    inputSchema: {
      type: "object",
      properties: {
        limit: { type: "number", description: "Number of recent posts to analyze (default 10)" },
      },
    },
  },
];

const HANDLERS = { post_message: postMessage, get_summary: getSummary };

// ── JSON-RPC STDIO TRANSPORT ─────────────────────────────────────────────
function handleRequest(req) {
  const { method, params, id } = req;

  if (method === "initialize") {
    return { jsonrpc: "2.0", id, result: {
      name: "social-mcp-fb", version: "1.0.0",
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
log("INFO", `Facebook MCP server starting (DRY_RUN=${DRY_RUN})`);

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
