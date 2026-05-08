"""Per-user persistent chat-thread storage.

A ``ChatThread`` is a single ongoing conversation with the autonomous
agent (Run → Agent in the UI). Each thread is one JSON file under
``.praxia/chats/<user_id>/<thread_id>.json`` so threads survive
browser reloads and Streamlit-server restarts.

Public API:

    from praxia.data.threads import ChatMessage, ChatThread, ThreadStore

    store = ThreadStore(memory_dir / "chats")
    threads = store.list_for_user("alice")               # newest first
    thread = store.create("alice", title="Acme prep")    # empty thread
    thread.messages.append(ChatMessage(role="user", content="Hello"))
    store.save(thread)
    later = store.load("alice", thread.id)
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ChatMessage:
    role: str  # "user" or "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)
    # Tool-use trace for assistant messages — list of dicts produced by
    # AutonomousAgent.run().tool_calls. Stored as plain dicts so JSON
    # round-trips cleanly.
    trace: list[dict[str, Any]] = field(default_factory=list)
    # Vision attachments (user messages only). Each entry:
    # {"data": "<base64>", "mime": "image/png"}.
    images: list[dict[str, str]] = field(default_factory=list)


@dataclass
class ChatThread:
    id: str
    user_id: str
    title: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    messages: list[ChatMessage] = field(default_factory=list)


def _auto_title(first_message: str, max_chars: int = 60) -> str:
    """Derive a thread title from the first user message."""
    line = first_message.strip().splitlines()[0] if first_message.strip() else ""
    if len(line) <= max_chars:
        return line or "(untitled)"
    return line[: max_chars - 1].rstrip() + "…"


class ThreadStore:
    """JSON-backed per-user chat-thread store."""

    def __init__(self, storage_dir: Path | str) -> None:
        self.root = Path(storage_dir)
        self.root.mkdir(parents=True, exist_ok=True)

    # ---- internals -------------------------------------------------------

    def _user_dir(self, user_id: str) -> Path:
        d = self.root / user_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _thread_path(self, user_id: str, thread_id: str) -> Path:
        return self._user_dir(user_id) / f"{thread_id}.json"

    def _read(self, path: Path) -> ChatThread | None:
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        _msg_fields = {f.name for f in ChatMessage.__dataclass_fields__.values()}
        msgs = [
            ChatMessage(**{k: v for k, v in m.items() if k in _msg_fields})
            if isinstance(m, dict) else m
            for m in data.get("messages", [])
        ]
        return ChatThread(
            id=data["id"],
            user_id=data["user_id"],
            title=data.get("title", "(untitled)"),
            created_at=float(data.get("created_at", time.time())),
            updated_at=float(data.get("updated_at", time.time())),
            messages=msgs,
        )

    def _write(self, thread: ChatThread) -> None:
        path = self._thread_path(thread.user_id, thread.id)
        # asdict doesn't recurse into ChatMessage cleanly — it does for
        # dataclasses, but we want a known shape, so just dump the fields.
        payload = {
            "id": thread.id,
            "user_id": thread.user_id,
            "title": thread.title,
            "created_at": thread.created_at,
            "updated_at": thread.updated_at,
            "messages": [asdict(m) for m in thread.messages],
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ---- public API ------------------------------------------------------

    def list_for_user(self, user_id: str) -> list[ChatThread]:
        """Return all threads for ``user_id``, newest-updated first."""
        out: list[ChatThread] = []
        for f in self._user_dir(user_id).glob("*.json"):
            t = self._read(f)
            if t is not None:
                out.append(t)
        out.sort(key=lambda t: t.updated_at, reverse=True)
        return out

    def load(self, user_id: str, thread_id: str) -> ChatThread | None:
        return self._read(self._thread_path(user_id, thread_id))

    def create(self, user_id: str, title: str = "") -> ChatThread:
        tid = uuid.uuid4().hex[:12]
        thread = ChatThread(
            id=tid,
            user_id=user_id,
            title=title or "(new conversation)",
        )
        self._write(thread)
        return thread

    def save(self, thread: ChatThread) -> None:
        thread.updated_at = time.time()
        # Auto-title the first time a real user message lands.
        if (
            thread.title in ("", "(new conversation)", "(untitled)")
            and thread.messages
        ):
            first_user = next(
                (m for m in thread.messages if m.role == "user"), None,
            )
            if first_user is not None:
                thread.title = _auto_title(first_user.content)
        self._write(thread)

    def rename(self, user_id: str, thread_id: str, new_title: str) -> bool:
        thread = self.load(user_id, thread_id)
        if thread is None:
            return False
        thread.title = new_title.strip() or thread.title
        self._write(thread)
        return True

    def delete(self, user_id: str, thread_id: str) -> bool:
        path = self._thread_path(user_id, thread_id)
        if not path.exists():
            return False
        try:
            path.unlink()
            return True
        except OSError:
            return False


__all__ = ["ChatMessage", "ChatThread", "ThreadStore"]
