#!/usr/bin/env python3
"""
A2A Messaging — Platinum Tier Phase 2

Agent-to-Agent direct messaging between Cloud Executive and Local Executive.
Replaces some file handoffs with low-latency socket messages while keeping
full vault audit trail.

Architecture:
  ┌──────────────┐   TCP socket    ┌──────────────┐
  │ Cloud Agent   │ ──────────────▶ │ Local Agent   │
  │ (port 9100)  │ ◀────────────── │ (port 9101)  │
  └──────────────┘                  └──────────────┘
         │  fallback: file ──▶  data/Updates/  ──▶  │
         │  fallback: file ──▶  Needs_Action/  ──▶  │

Message types (direct, replaces file handoffs):
  - draft_ready         Cloud -> Local: "Draft ready for approval: {id}"
  - approval_complete   Local -> Cloud: "Approved/rejected: {id}"
  - health_ping         Both:          Heartbeat / liveness probe
  - sync_request        Both:          Request immediate Git sync
  - dashboard_update    Cloud -> Local: Metrics update (merge into Dashboard)
  - task_delegation     Both:          Delegate task to other zone

Fallback: If socket fails, every message is ALSO written as a vault .md file
in the appropriate directory so the file-based flow still works.

Audit: Every message logged to:
  1. data/Logs/a2a_{YYYY-MM-DD}.json  (structured JSON array)
  2. data/Logs/a2a_messages/A2A_{id}.md  (vault .md for traceability)

Usage:
    # As a library (imported by orchestrators)
    from a2a_messaging import A2ANode, send_message

    node = A2ANode(role="cloud")
    node.start()
    node.send("local", {"type": "draft_ready", "draft_id": "inv_20260222"})
    node.stop()

    # Standalone listener (for testing / manual operation)
    python a2a_messaging.py --role cloud           # Start cloud node
    python a2a_messaging.py --role local            # Start local node
    python a2a_messaging.py --send local draft_ready '{"draft_id":"x"}'
    python a2a_messaging.py --test                  # Self-test both nodes
"""

import json
import logging
import os
import queue
import socket
import sys
import threading
import time
import uuid
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# ── CONFIG ────────────────────────────────────────────────────────────────
VAULT_DIR = Path(__file__).parent.resolve()
LOG_DIR = VAULT_DIR / "data" / "Logs"
A2A_LOG_DIR = LOG_DIR / "a2a_messages"
UPDATES_DIR = VAULT_DIR / "data" / "Updates"
NEEDS_ACTION_CLOUD = VAULT_DIR / "data" / "Needs_Action" / "cloud"
NEEDS_ACTION_LOCAL = VAULT_DIR / "data" / "Needs_Action" / "local"

# Ensure directories
for _d in (LOG_DIR, A2A_LOG_DIR, UPDATES_DIR, NEEDS_ACTION_CLOUD, NEEDS_ACTION_LOCAL):
    _d.mkdir(parents=True, exist_ok=True)

# Network configuration — ports for each role
CLOUD_HOST = os.environ.get("A2A_CLOUD_HOST", "127.0.0.1")
CLOUD_PORT = int(os.environ.get("A2A_CLOUD_PORT", "9100"))
LOCAL_HOST = os.environ.get("A2A_LOCAL_HOST", "127.0.0.1")
LOCAL_PORT = int(os.environ.get("A2A_LOCAL_PORT", "9101"))

# Feature flag — A2A Phase 2 must be explicitly enabled
A2A_ENABLED = os.environ.get("A2A_PHASE2_ENABLED", "false").lower() == "true"

# Timeouts and limits
SOCKET_TIMEOUT = int(os.environ.get("A2A_SOCKET_TIMEOUT", "5"))
MAX_MSG_SIZE = int(os.environ.get("A2A_MAX_MSG_SIZE", "65536"))  # 64 KB
RECONNECT_DELAY = int(os.environ.get("A2A_RECONNECT_DELAY", "10"))
MAX_QUEUE_SIZE = int(os.environ.get("A2A_MAX_QUEUE_SIZE", "1000"))

# Audit logger integration
try:
    from audit_logger import log_action as _audit_log_action
    HAS_AUDIT_LOGGER = True
except ImportError:
    HAS_AUDIT_LOGGER = False

# ── LOGGING ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - A2A - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "a2a_messaging.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("A2A")

# ── MESSAGE TYPES ─────────────────────────────────────────────────────────
VALID_MSG_TYPES = {
    "draft_ready",          # Cloud -> Local: draft created, ready for approval
    "approval_complete",    # Local -> Cloud: approved or rejected
    "health_ping",          # Both: liveness heartbeat
    "health_pong",          # Both: heartbeat response
    "sync_request",         # Both: request immediate Git sync
    "dashboard_update",     # Cloud -> Local: metrics for Dashboard merge
    "task_delegation",      # Both: delegate task to other zone
    "ack",                  # Both: generic acknowledgment
}

# Maps role -> (listen_host, listen_port, peer_host, peer_port)
ROLE_CONFIG = {
    "cloud": (CLOUD_HOST, CLOUD_PORT, LOCAL_HOST, LOCAL_PORT),
    "local": (LOCAL_HOST, LOCAL_PORT, CLOUD_HOST, CLOUD_PORT),
}


# ══════════════════════════════════════════════════════════════════════════
#  A2A MESSAGE
# ══════════════════════════════════════════════════════════════════════════
class A2AMessage:
    """Structured A2A message with metadata."""

    def __init__(
        self,
        msg_type: str,
        payload: Dict[str, Any],
        sender: str = "",
        recipient: str = "",
        msg_id: str = "",
        correlation_id: str = "",
        timestamp: str = "",
    ):
        self.msg_type = msg_type
        self.payload = payload
        self.sender = sender
        self.recipient = recipient
        self.msg_id = msg_id or f"a2a_{uuid.uuid4().hex[:12]}"
        self.correlation_id = correlation_id or self.msg_id
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "msg_id": self.msg_id,
            "msg_type": self.msg_type,
            "sender": self.sender,
            "recipient": self.recipient,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_json(cls, data: str) -> "A2AMessage":
        d = json.loads(data)
        return cls(
            msg_type=d["msg_type"],
            payload=d.get("payload", {}),
            sender=d.get("sender", ""),
            recipient=d.get("recipient", ""),
            msg_id=d.get("msg_id", ""),
            correlation_id=d.get("correlation_id", ""),
            timestamp=d.get("timestamp", ""),
        )

    def __repr__(self):
        return f"A2AMessage({self.msg_type}, id={self.msg_id[:8]}, {self.sender}->{self.recipient})"


# ══════════════════════════════════════════════════════════════════════════
#  AUDIT LOGGING (dual: JSON log + vault .md)
# ══════════════════════════════════════════════════════════════════════════
_audit_lock = threading.Lock()


def log_a2a_message(msg: A2AMessage, direction: str = "sent", delivery: str = "socket"):
    """Log an A2A message to both JSON audit log and vault .md file.

    Args:
        msg:       The A2AMessage object
        direction: "sent" or "received"
        delivery:  "socket" or "file_fallback"
    """
    now = datetime.now(timezone.utc)

    # ── 1. JSON audit log: data/Logs/a2a_{date}.json ──────────────────
    log_entry = {
        "timestamp": now.isoformat(),
        "direction": direction,
        "delivery_method": delivery,
        "msg_id": msg.msg_id,
        "msg_type": msg.msg_type,
        "sender": msg.sender,
        "recipient": msg.recipient,
        "correlation_id": msg.correlation_id,
        "payload_summary": _summarize_payload(msg.payload),
    }

    today = now.strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"a2a_{today}.json"

    with _audit_lock:
        try:
            existing = []
            if log_file.exists():
                content = log_file.read_text(encoding="utf-8").strip()
                if content:
                    existing = json.loads(content)
            existing.append(log_entry)
            log_file.write_text(json.dumps(existing, indent=2, default=str), encoding="utf-8")
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to write A2A audit JSON: {e}")

    # ── 2. Vault .md file: data/Logs/a2a_messages/A2A_{id}.md ─────────
    md_file = A2A_LOG_DIR / f"A2A_{msg.msg_id}.md"
    md_content = f"""---
type: a2a_message
msg_id: {msg.msg_id}
msg_type: {msg.msg_type}
direction: {direction}
delivery: {delivery}
sender: {msg.sender}
recipient: {msg.recipient}
correlation_id: {msg.correlation_id}
timestamp: {msg.timestamp}
logged: {now.isoformat()}
---

# A2A Message — {msg.msg_type}

- **ID**: {msg.msg_id}
- **Direction**: {direction}
- **Delivery**: {delivery}
- **Sender**: {msg.sender}
- **Recipient**: {msg.recipient}
- **Correlation**: {msg.correlation_id}

## Payload

```json
{json.dumps(msg.payload, indent=2, default=str)}
```
"""
    try:
        md_file.write_text(md_content, encoding="utf-8")
    except OSError as e:
        logger.warning(f"Failed to write A2A vault .md: {e}")

    # ── 3. Centralized audit_logger (if available) ────────────────────
    if HAS_AUDIT_LOGGER:
        _audit_log_action(
            action_type=f"a2a.{msg.msg_type}.{direction}",
            actor=msg.sender or "a2a",
            target=msg.recipient or "a2a",
            parameters={"msg_id": msg.msg_id, "delivery": delivery},
            result="success",
            severity="INFO",
            correlation_id=msg.correlation_id,
        )


def _summarize_payload(payload: dict) -> str:
    """Create a short summary of the payload for the JSON log."""
    s = json.dumps(payload, default=str)
    return s[:200] + "..." if len(s) > 200 else s


# ══════════════════════════════════════════════════════════════════════════
#  FILE FALLBACK — write message as vault file when socket fails
# ══════════════════════════════════════════════════════════════════════════
def file_fallback(msg: A2AMessage):
    """Write the message as a vault .md file in the appropriate directory.

    This ensures the message is processed even if the socket is down —
    the orchestrator's normal file-based loop picks it up.
    """
    now = datetime.now()
    safe_id = msg.msg_id.replace("/", "_")

    # Route to the recipient's input directory
    if msg.recipient == "local":
        if msg.msg_type == "draft_ready":
            target_dir = VAULT_DIR / "data" / "Pending_Approval" / "local"
        elif msg.msg_type == "dashboard_update":
            target_dir = UPDATES_DIR
        else:
            target_dir = NEEDS_ACTION_LOCAL
    elif msg.recipient == "cloud":
        target_dir = NEEDS_ACTION_CLOUD
    else:
        target_dir = UPDATES_DIR

    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"A2A_{msg.msg_type}_{safe_id}.md"
    filepath = target_dir / filename

    content = f"""---
type: a2a_fallback
msg_type: {msg.msg_type}
msg_id: {msg.msg_id}
sender: {msg.sender}
recipient: {msg.recipient}
correlation_id: {msg.correlation_id}
created: {now.strftime('%Y-%m-%d %H:%M')}
delivery: file_fallback
---

# A2A Fallback: {msg.msg_type}

Socket delivery failed — this file was created as a fallback.
The normal file-based orchestrator loop will process this.

## Payload

```json
{json.dumps(msg.payload, indent=2, default=str)}
```

## Recovery
- This file will be processed by the standard file-based flow
- Once processed, move to Done/ as usual
"""

    try:
        filepath.write_text(content, encoding="utf-8")
        logger.info(f"[FALLBACK] Wrote {filename} to {target_dir.name}/")
        log_a2a_message(msg, direction="sent", delivery="file_fallback")
        return True
    except OSError as e:
        logger.error(f"[FALLBACK] Failed to write fallback file: {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════
#  A2A NODE — socket server + client + message queue
# ══════════════════════════════════════════════════════════════════════════
class A2ANode:
    """A2A messaging node that listens for incoming messages and sends outgoing ones.

    Each agent (cloud/local) runs one A2ANode. The node:
      - Listens on its own port for incoming messages
      - Sends messages to the peer's port
      - Queues incoming messages for the agent to process
      - Falls back to file handoffs if socket fails
      - Logs all messages to audit trail

    Usage:
        node = A2ANode(role="cloud")
        node.on_message(my_handler)   # Register callback
        node.start()                  # Start listener thread
        node.send("local", {"type": "draft_ready", "draft_id": "123"})
        msg = node.recv(timeout=5)    # Or poll the queue
        node.stop()
    """

    def __init__(self, role: str = "cloud"):
        if role not in ROLE_CONFIG:
            raise ValueError(f"Invalid role '{role}'. Must be 'cloud' or 'local'.")

        self.role = role
        self.listen_host, self.listen_port, self.peer_host, self.peer_port = ROLE_CONFIG[role]
        self.inbox: queue.Queue = queue.Queue(maxsize=MAX_QUEUE_SIZE)
        self._handlers: List[Callable[[A2AMessage], None]] = []
        self._running = False
        self._server_thread: Optional[threading.Thread] = None
        self._server_socket: Optional[socket.socket] = None
        self._stats = {
            "sent": 0, "received": 0, "send_failures": 0,
            "fallbacks": 0, "started_at": None,
        }

    # ── Lifecycle ─────────────────────────────────────────────────────
    def start(self):
        """Start the listener thread."""
        if not A2A_ENABLED:
            logger.info(f"[{self.role}] A2A Phase 2 disabled (set A2A_PHASE2_ENABLED=true to enable)")
            return

        self._running = True
        self._stats["started_at"] = datetime.now(timezone.utc).isoformat()
        self._server_thread = threading.Thread(
            target=self._listen_loop, daemon=True, name=f"a2a-{self.role}-listener"
        )
        self._server_thread.start()
        logger.info(f"[{self.role}] A2A node started on {self.listen_host}:{self.listen_port}")

    def stop(self):
        """Stop the listener thread and close the server socket."""
        self._running = False
        if self._server_socket:
            try:
                self._server_socket.close()
            except OSError:
                pass
        if self._server_thread and self._server_thread.is_alive():
            self._server_thread.join(timeout=5)
        logger.info(f"[{self.role}] A2A node stopped. Stats: {json.dumps(self._stats)}")

    # ── Message handlers ──────────────────────────────────────────────
    def on_message(self, handler: Callable[[A2AMessage], None]):
        """Register a callback for incoming messages."""
        self._handlers.append(handler)

    def recv(self, timeout: float = 0) -> Optional[A2AMessage]:
        """Poll the inbox queue for the next message. Returns None on timeout."""
        try:
            return self.inbox.get(block=timeout > 0, timeout=timeout if timeout > 0 else None)
        except queue.Empty:
            return None

    # ── Sending ───────────────────────────────────────────────────────
    def send(self, recipient: str, payload: dict, msg_type: str = "",
             correlation_id: str = "") -> bool:
        """Send a message to the peer agent.

        Args:
            recipient: "cloud" or "local"
            payload:   Message payload dict
            msg_type:  Message type (auto-detected from payload["type"] if empty)
            correlation_id: Optional correlation ID for linking related messages

        Returns True if socket delivery succeeded, False if fell back to file.
        """
        if not A2A_ENABLED:
            logger.debug(f"[{self.role}] A2A disabled, using file fallback")
            msg_type = msg_type or payload.get("type", "task_delegation")
            msg = A2AMessage(
                msg_type=msg_type, payload=payload,
                sender=self.role, recipient=recipient,
                correlation_id=correlation_id,
            )
            self._stats["fallbacks"] += 1
            return file_fallback(msg)

        msg_type = msg_type or payload.get("type", "task_delegation")
        if msg_type not in VALID_MSG_TYPES:
            logger.warning(f"[{self.role}] Unknown message type '{msg_type}', sending anyway")

        msg = A2AMessage(
            msg_type=msg_type, payload=payload,
            sender=self.role, recipient=recipient,
            correlation_id=correlation_id,
        )

        # Determine target
        if recipient == self.role:
            logger.warning(f"[{self.role}] Cannot send to self")
            return False

        target_host, target_port = self.peer_host, self.peer_port

        # Try socket delivery
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(SOCKET_TIMEOUT)
                sock.connect((target_host, target_port))
                data = msg.to_json().encode("utf-8")
                if len(data) > MAX_MSG_SIZE:
                    logger.warning(f"[{self.role}] Message too large ({len(data)} bytes), using fallback")
                    raise ConnectionError("Message exceeds MAX_MSG_SIZE")
                sock.sendall(data)

                # Wait for ack
                try:
                    ack = sock.recv(1024).decode("utf-8").strip()
                    if ack:
                        ack_data = json.loads(ack)
                        if ack_data.get("status") != "ok":
                            logger.warning(f"[{self.role}] Peer rejected message: {ack_data}")
                except (socket.timeout, json.JSONDecodeError):
                    pass  # ack is best-effort

            self._stats["sent"] += 1
            log_a2a_message(msg, direction="sent", delivery="socket")
            logger.info(f"[{self.role}] Sent {msg.msg_type} to {recipient} via socket")
            return True

        except (ConnectionRefusedError, ConnectionError, socket.timeout, OSError) as e:
            logger.warning(f"[{self.role}] Socket send failed ({e}), falling back to file")
            self._stats["send_failures"] += 1
            self._stats["fallbacks"] += 1
            return file_fallback(msg)

    # ── Convenience senders ───────────────────────────────────────────
    def notify_draft_ready(self, draft_id: str, draft_type: str = "email",
                           summary: str = "") -> bool:
        """Cloud -> Local: notify that a draft is ready for approval."""
        return self.send("local", {
            "type": "draft_ready",
            "draft_id": draft_id,
            "draft_type": draft_type,
            "summary": summary,
            "created": datetime.now().isoformat(),
        }, msg_type="draft_ready", correlation_id=draft_id)

    def notify_approval_complete(self, draft_id: str, decision: str = "approved",
                                 details: str = "") -> bool:
        """Local -> Cloud: notify that an approval decision was made."""
        return self.send("cloud", {
            "type": "approval_complete",
            "draft_id": draft_id,
            "decision": decision,
            "details": details,
            "decided": datetime.now().isoformat(),
        }, msg_type="approval_complete", correlation_id=draft_id)

    def send_health_ping(self) -> bool:
        """Send a health ping to the peer."""
        peer = "local" if self.role == "cloud" else "cloud"
        return self.send(peer, {
            "type": "health_ping",
            "sender_uptime": self._stats.get("started_at", ""),
            "sent_count": self._stats["sent"],
            "received_count": self._stats["received"],
        }, msg_type="health_ping")

    def request_sync(self) -> bool:
        """Request the peer to perform an immediate Git sync."""
        peer = "local" if self.role == "cloud" else "cloud"
        return self.send(peer, {
            "type": "sync_request",
            "reason": "a2a_triggered",
        }, msg_type="sync_request")

    def send_dashboard_update(self, metrics: dict) -> bool:
        """Cloud -> Local: send metrics for dashboard merge."""
        return self.send("local", {
            "type": "dashboard_update",
            "metrics": metrics,
            "timestamp": datetime.now().isoformat(),
        }, msg_type="dashboard_update")

    # ── Listener ──────────────────────────────────────────────────────
    def _listen_loop(self):
        """TCP listener loop — accepts connections, parses messages, queues them."""
        while self._running:
            try:
                self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self._server_socket.settimeout(2)  # allow periodic running check
                self._server_socket.bind((self.listen_host, self.listen_port))
                self._server_socket.listen(5)
                logger.info(f"[{self.role}] Listening on {self.listen_host}:{self.listen_port}")

                while self._running:
                    try:
                        conn, addr = self._server_socket.accept()
                        threading.Thread(
                            target=self._handle_connection,
                            args=(conn, addr),
                            daemon=True,
                        ).start()
                    except socket.timeout:
                        continue

            except OSError as e:
                if self._running:
                    logger.error(f"[{self.role}] Listener error: {e}, retrying in {RECONNECT_DELAY}s")
                    time.sleep(RECONNECT_DELAY)
            finally:
                if self._server_socket:
                    try:
                        self._server_socket.close()
                    except OSError:
                        pass

    def _handle_connection(self, conn: socket.socket, addr):
        """Handle a single incoming connection."""
        try:
            conn.settimeout(SOCKET_TIMEOUT)
            data = b""
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
                if len(data) >= MAX_MSG_SIZE:
                    break

            if not data:
                return

            msg = A2AMessage.from_json(data.decode("utf-8"))
            self._stats["received"] += 1

            log_a2a_message(msg, direction="received", delivery="socket")
            logger.info(f"[{self.role}] Received {msg.msg_type} from {msg.sender} ({addr[0]})")

            # Send ack
            try:
                ack = json.dumps({"status": "ok", "msg_id": msg.msg_id})
                conn.sendall(ack.encode("utf-8"))
            except OSError:
                pass

            # Auto-respond to health pings
            if msg.msg_type == "health_ping":
                self._respond_health_pong(msg)

            # Queue for processing
            try:
                self.inbox.put_nowait(msg)
            except queue.Full:
                logger.warning(f"[{self.role}] Inbox full, dropping message {msg.msg_id}")

            # Notify handlers
            for handler in self._handlers:
                try:
                    handler(msg)
                except Exception as e:
                    logger.error(f"[{self.role}] Handler error: {e}")

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"[{self.role}] Invalid message from {addr}: {e}")
        except Exception as e:
            logger.error(f"[{self.role}] Connection handler error: {e}")
        finally:
            conn.close()

    def _respond_health_pong(self, ping_msg: A2AMessage):
        """Auto-respond to a health ping with a pong."""
        try:
            peer = "local" if self.role == "cloud" else "cloud"
            self.send(peer, {
                "type": "health_pong",
                "in_reply_to": ping_msg.msg_id,
                "status": "healthy",
                "uptime_since": self._stats.get("started_at", ""),
            }, msg_type="health_pong", correlation_id=ping_msg.correlation_id)
        except Exception as e:
            logger.warning(f"[{self.role}] Failed to send health_pong: {e}")

    # ── Status ────────────────────────────────────────────────────────
    def get_stats(self) -> dict:
        return {
            **self._stats,
            "role": self.role,
            "listen": f"{self.listen_host}:{self.listen_port}",
            "peer": f"{self.peer_host}:{self.peer_port}",
            "inbox_size": self.inbox.qsize(),
            "handlers": len(self._handlers),
            "enabled": A2A_ENABLED,
        }


# ══════════════════════════════════════════════════════════════════════════
#  MODULE-LEVEL CONVENIENCE API
# ══════════════════════════════════════════════════════════════════════════
_default_node: Optional[A2ANode] = None


def init(role: str = "cloud") -> A2ANode:
    """Initialize and start the default A2A node for this process."""
    global _default_node
    if _default_node is not None:
        _default_node.stop()
    _default_node = A2ANode(role=role)
    _default_node.start()
    return _default_node


def send_message(recipient: str, payload: dict, msg_type: str = "",
                 correlation_id: str = "") -> bool:
    """Send a message using the default node (auto-initializes if needed)."""
    if _default_node is None:
        logger.warning("A2A node not initialized. Call a2a_messaging.init(role) first.")
        # Fallback: write as file even without a node
        msg = A2AMessage(
            msg_type=msg_type or payload.get("type", "task_delegation"),
            payload=payload, sender="unknown", recipient=recipient,
            correlation_id=correlation_id,
        )
        return file_fallback(msg)
    return _default_node.send(recipient, payload, msg_type, correlation_id)


def get_node() -> Optional[A2ANode]:
    """Return the default A2A node (or None if not initialized)."""
    return _default_node


# ══════════════════════════════════════════════════════════════════════════
#  SELF-TEST
# ══════════════════════════════════════════════════════════════════════════
def self_test():
    """Run a self-test of A2A messaging (both nodes on localhost)."""
    print("=" * 60)
    print("  A2A MESSAGING SELF-TEST")
    print("=" * 60)

    # Temporarily enable A2A for testing
    global A2A_ENABLED
    original = A2A_ENABLED
    A2A_ENABLED = True

    passed = 0
    total = 0

    # Test 1: Message serialization
    total += 1
    msg = A2AMessage("draft_ready", {"draft_id": "test_001"}, sender="cloud", recipient="local")
    restored = A2AMessage.from_json(msg.to_json())
    ok = restored.msg_type == "draft_ready" and restored.payload["draft_id"] == "test_001"
    print(f"  [{'PASS' if ok else 'FAIL'}] Message serialize/deserialize")
    if ok: passed += 1

    # Test 2: File fallback
    total += 1
    msg2 = A2AMessage("draft_ready", {"draft_id": "fallback_test"}, sender="cloud", recipient="local")
    ok = file_fallback(msg2)
    print(f"  [{'PASS' if ok else 'FAIL'}] File fallback writes vault .md")
    if ok: passed += 1

    # Test 3: Audit logging
    total += 1
    log_a2a_message(msg, direction="sent", delivery="test")
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"a2a_{today}.json"
    ok = log_file.exists()
    print(f"  [{'PASS' if ok else 'FAIL'}] Audit JSON log created: a2a_{today}.json")
    if ok: passed += 1

    # Test 4: Vault .md audit
    total += 1
    md_file = A2A_LOG_DIR / f"A2A_{msg.msg_id}.md"
    ok = md_file.exists()
    print(f"  [{'PASS' if ok else 'FAIL'}] Vault .md audit created")
    if ok: passed += 1

    # Test 5: Socket round-trip (cloud -> local)
    total += 1
    received_msgs = []

    cloud_node = A2ANode(role="cloud")
    local_node = A2ANode(role="local")
    local_node.on_message(lambda m: received_msgs.append(m))

    cloud_node.start()
    local_node.start()
    time.sleep(0.5)  # Let listeners bind

    ok_send = cloud_node.send("local", {"draft_id": "socket_test"}, msg_type="draft_ready")
    time.sleep(1)  # Allow delivery

    ok = ok_send and len(received_msgs) > 0
    if ok:
        ok = received_msgs[0].msg_type == "draft_ready"
    print(f"  [{'PASS' if ok else 'FAIL'}] Socket round-trip cloud -> local")
    if ok: passed += 1

    # Test 6: Socket round-trip (local -> cloud)
    total += 1
    cloud_received = []
    cloud_node.on_message(lambda m: cloud_received.append(m))

    ok_send2 = local_node.send("cloud", {"draft_id": "x", "decision": "approved"},
                                msg_type="approval_complete")
    time.sleep(1)

    ok = ok_send2 and len(cloud_received) > 0
    print(f"  [{'PASS' if ok else 'FAIL'}] Socket round-trip local -> cloud")
    if ok: passed += 1

    # Test 7: Stats
    total += 1
    stats = cloud_node.get_stats()
    ok = stats["role"] == "cloud" and stats["sent"] > 0
    print(f"  [{'PASS' if ok else 'FAIL'}] Node stats: sent={stats['sent']} recv={stats['received']}")
    if ok: passed += 1

    # Test 8: Health ping
    total += 1
    ok_ping = cloud_node.send_health_ping()
    time.sleep(1)
    ok = ok_ping
    print(f"  [{'PASS' if ok else 'FAIL'}] Health ping sent")
    if ok: passed += 1

    # Cleanup
    cloud_node.stop()
    local_node.stop()
    A2A_ENABLED = original

    print(f"\n  Result: {passed}/{total} tests passed")
    print("=" * 60)
    return passed == total


# ══════════════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════════════
def main():
    global A2A_ENABLED

    parser = argparse.ArgumentParser(
        description="A2A Messaging — Platinum Tier Phase 2 direct agent communication"
    )
    parser.add_argument("--role", choices=["cloud", "local"],
                        help="Start as cloud or local node listener")
    parser.add_argument("--send", nargs=3, metavar=("RECIPIENT", "MSG_TYPE", "PAYLOAD_JSON"),
                        help="Send a single message: --send local draft_ready '{\"draft_id\":\"x\"}'")
    parser.add_argument("--test", action="store_true", help="Run self-tests")
    parser.add_argument("--status", action="store_true", help="Show config and exit")
    args = parser.parse_args()

    if args.test:
        success = self_test()
        sys.exit(0 if success else 1)

    if args.status:
        print(f"A2A Phase 2 Configuration:")
        print(f"  Enabled:     {A2A_ENABLED}")
        print(f"  Cloud:       {CLOUD_HOST}:{CLOUD_PORT}")
        print(f"  Local:       {LOCAL_HOST}:{LOCAL_PORT}")
        print(f"  Timeout:     {SOCKET_TIMEOUT}s")
        print(f"  Max msg:     {MAX_MSG_SIZE} bytes")
        print(f"  Log dir:     {LOG_DIR}")
        print(f"  Vault audit: {A2A_LOG_DIR}")
        return

    if args.send:
        recipient, msg_type, payload_json = args.send
        try:
            payload = json.loads(payload_json)
        except json.JSONDecodeError as e:
            print(f"Invalid JSON payload: {e}")
            sys.exit(1)

        # For one-shot sends, create a temporary node
        role = "local" if recipient == "cloud" else "cloud"
        node = A2ANode(role=role)
        node.start()
        time.sleep(0.3)
        success = node.send(recipient, payload, msg_type=msg_type)
        node.stop()
        print(f"{'Sent' if success else 'Fallback used'}: {msg_type} -> {recipient}")
        sys.exit(0 if success else 1)

    if args.role:
        # Start as a persistent listener
        A2A_ENABLED = True
        node = A2ANode(role=args.role)

        def print_message(msg: A2AMessage):
            print(f"  [{msg.msg_type}] from={msg.sender} payload={json.dumps(msg.payload, default=str)[:200]}")

        node.on_message(print_message)
        node.start()

        print(f"A2A {args.role} node listening on {node.listen_host}:{node.listen_port}")
        print("Press Ctrl+C to stop.\n")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            node.stop()
        return

    parser.print_help()


if __name__ == "__main__":
    main()
