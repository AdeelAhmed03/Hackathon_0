#!/usr/bin/env node
/**
 * Email MCP Server (Gold Tier)
 *
 * A Model Context Protocol server that exposes "draft" and "send" tools
 * for email via stdin/stdout JSON-RPC, ready for Claude Code invocation.
 *
 * Transport : stdio (stdin/stdout newline-delimited JSON-RPC 2.0)
 * Mailer    : nodemailer (Gmail SMTP with app-password)
 * Safety    : DRY_RUN env — when "true", send logs but does not transmit
 *
 * Env vars (from .env or shell):
 *   MCP_EMAIL_SERVER       — SMTP host     (default: smtp.gmail.com)
 *   MCP_EMAIL_PORT         — SMTP port     (default: 587)
 *   MCP_EMAIL_ADDRESS      — sender / auth (required)
 *   MCP_EMAIL_APP_PASSWORD — app password   (required for real sends)
 *   MCP_EMAIL_DRY_RUN      — "true" to skip actual SMTP delivery
 *
 * Run:
 *   cd mcp-servers/email-mcp && npm install && node index.js
 */

import { createInterface } from "node:readline";
import nodemailer from "nodemailer";

// ── CONFIG ───────────────────────────────────────────────────────────────
const SMTP_HOST = process.env.MCP_EMAIL_SERVER || "smtp.gmail.com";
const SMTP_PORT = parseInt(process.env.MCP_EMAIL_PORT || "587", 10);
const EMAIL_ADDRESS = process.env.MCP_EMAIL_ADDRESS || "";
const EMAIL_PASSWORD = process.env.MCP_EMAIL_APP_PASSWORD || "";
const DRY_RUN =
  (process.env.MCP_EMAIL_DRY_RUN || "true").toLowerCase() === "true";

// ── NODEMAILER TRANSPORT ─────────────────────────────────────────────────
const transporter = nodemailer.createTransport({
  host: SMTP_HOST,
  port: SMTP_PORT,
  secure: SMTP_PORT === 465,
  auth: {
    user: EMAIL_ADDRESS,
    pass: EMAIL_PASSWORD,
  },
});

// ── TOOL DEFINITIONS (MCP schema) ────────────────────────────────────────
const TOOLS = [
  {
    name: "draft",
    description:
      "Draft an email — returns the composed text without sending. " +
      "Always safe to call (no side-effects).",
    inputSchema: {
      type: "object",
      properties: {
        to: { type: "string", description: "Recipient email address" },
        subject: { type: "string", description: "Email subject line" },
        body: { type: "string", description: "Email body (plain text)" },
      },
      required: ["to", "subject", "body"],
    },
  },
  {
    name: "send",
    description:
      "Send an email via SMTP. Respects MCP_EMAIL_DRY_RUN — when true " +
      "the email is logged but NOT transmitted. Requires HITL approval " +
      "in the vault workflow before calling.",
    inputSchema: {
      type: "object",
      properties: {
        to: { type: "string", description: "Recipient email address" },
        subject: { type: "string", description: "Email subject line" },
        body: { type: "string", description: "Email body (plain text)" },
        cc: { type: "string", description: "CC recipients (optional)" },
        bcc: { type: "string", description: "BCC recipients (optional)" },
      },
      required: ["to", "subject", "body"],
    },
  },
];

// ── TOOL HANDLERS ────────────────────────────────────────────────────────

/**
 * draft — compose an email and return the text, no side-effects.
 */
function handleDraft(params) {
  const { to, subject, body } = params;
  const timestamp = new Date().toISOString();

  const draftText = [
    `To: ${to}`,
    `From: ${EMAIL_ADDRESS || "(not configured)"}`,
    `Subject: ${subject}`,
    `Date: ${timestamp}`,
    ``,
    body,
  ].join("\n");

  log(`[DRAFT] Would draft to ${to} | Subject: ${subject}`);

  return {
    content: [
      {
        type: "text",
        text:
          `Email drafted successfully.\n\n` +
          `---\n${draftText}\n---\n\n` +
          `Status: draft (not sent). Call "send" tool after HITL approval.`,
      },
    ],
  };
}

/**
 * send — transmit (or dry-run log) an email via SMTP.
 */
async function handleSend(params) {
  const { to, subject, body, cc, bcc } = params;
  const timestamp = new Date().toISOString();

  // ── DRY RUN ────────────────────────────────────────────────────────
  if (DRY_RUN) {
    log(`[DRY RUN] Would send to ${to} | Subject: ${subject}`);
    return {
      content: [
        {
          type: "text",
          text:
            `[DRY RUN] Email NOT sent (MCP_EMAIL_DRY_RUN=true).\n\n` +
            `To: ${to}\nSubject: ${subject}\nCC: ${cc || "(none)"}\n` +
            `BCC: ${bcc || "(none)"}\nBody preview: ${body.slice(0, 200)}...\n` +
            `Timestamp: ${timestamp}`,
        },
      ],
    };
  }

  // ── REAL SEND ──────────────────────────────────────────────────────
  if (!EMAIL_ADDRESS || !EMAIL_PASSWORD) {
    const msg =
      "Cannot send: MCP_EMAIL_ADDRESS or MCP_EMAIL_APP_PASSWORD not set.";
    log(`[ERROR] ${msg}`);
    return { content: [{ type: "text", text: msg }], isError: true };
  }

  const mailOptions = {
    from: EMAIL_ADDRESS,
    to,
    subject,
    text: body,
    ...(cc && { cc }),
    ...(bcc && { bcc }),
  };

  // Retry up to 3 times with exponential backoff (per Company_Handbook policy)
  const MAX_RETRIES = 3;
  let lastError = null;

  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    try {
      const info = await transporter.sendMail(mailOptions);
      log(`[SENT] to=${to} | messageId=${info.messageId} (attempt ${attempt}/${MAX_RETRIES})`);

      return {
        content: [
          {
            type: "text",
            text:
              `Email sent successfully.\n\n` +
              `To: ${to}\nSubject: ${subject}\nMessage-ID: ${info.messageId}\n` +
              `SMTP response: ${info.response}\nTimestamp: ${timestamp}\n` +
              `Attempts: ${attempt}/${MAX_RETRIES}`,
          },
        ],
      };
    } catch (err) {
      lastError = err;
      log(`[ERROR] Send attempt ${attempt}/${MAX_RETRIES} failed: ${err.message}`);
      if (attempt < MAX_RETRIES) {
        const delay = Math.pow(2, attempt) * 1000; // 2s, 4s
        log(`[RETRY] Waiting ${delay}ms before retry...`);
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
    }
  }

  // All retries exhausted
  log(`[ERROR] All ${MAX_RETRIES} send attempts failed: ${lastError.message}`);
  return {
    content: [
      {
        type: "text",
        text: `Email send failed after ${MAX_RETRIES} attempts: ${lastError.message}`,
      },
    ],
    isError: true,
  };
}

// ── JSON-RPC OVER STDIO (MCP transport) ──────────────────────────────────

/** Send a JSON-RPC response to stdout. */
function respond(id, result) {
  const msg = JSON.stringify({ jsonrpc: "2.0", id, result });
  process.stdout.write(msg + "\n");
}

/** Send a JSON-RPC error to stdout. */
function respondError(id, code, message) {
  const msg = JSON.stringify({
    jsonrpc: "2.0",
    id,
    error: { code, message },
  });
  process.stdout.write(msg + "\n");
}

/** Log to stderr (so it doesn't pollute the JSON-RPC stdout channel). */
function log(message) {
  process.stderr.write(`[email-mcp] ${new Date().toISOString()} ${message}\n`);
}

/** Route an incoming JSON-RPC request to the correct handler. */
async function handleRequest(request) {
  const { id, method, params } = request;

  switch (method) {
    // ── MCP lifecycle ────────────────────────────────────────────────
    case "initialize":
      respond(id, {
        protocolVersion: "2024-11-05",
        capabilities: { tools: {} },
        serverInfo: {
          name: "email-mcp",
          version: "1.0.0",
        },
      });
      break;

    case "notifications/initialized":
      // Client acknowledgement — no response needed
      break;

    // ── Tool discovery ───────────────────────────────────────────────
    case "tools/list":
      respond(id, { tools: TOOLS });
      break;

    // ── Tool execution ───────────────────────────────────────────────
    case "tools/call": {
      const toolName = params?.name;
      const toolArgs = params?.arguments || {};

      if (toolName === "draft") {
        respond(id, handleDraft(toolArgs));
      } else if (toolName === "send") {
        const result = await handleSend(toolArgs);
        respond(id, result);
      } else {
        respondError(id, -32601, `Unknown tool: ${toolName}`);
      }
      break;
    }

    default:
      if (id !== undefined) {
        respondError(id, -32601, `Unknown method: ${method}`);
      }
  }
}

// ── MAIN ─────────────────────────────────────────────────────────────────
log("Email MCP server starting ...");
log(`SMTP: ${SMTP_HOST}:${SMTP_PORT} | From: ${EMAIL_ADDRESS || "(not set)"}`);
log(`DRY_RUN: ${DRY_RUN}`);

const rl = createInterface({ input: process.stdin });

rl.on("line", async (line) => {
  const trimmed = line.trim();
  if (!trimmed) return;

  try {
    const request = JSON.parse(trimmed);
    await handleRequest(request);
  } catch (err) {
    log(`[ERROR] Failed to parse request: ${err.message}`);
    respondError(null, -32700, "Parse error");
  }
});

rl.on("close", () => {
  log("stdin closed — shutting down");
  process.exit(0);
});
