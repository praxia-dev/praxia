"""Chat-thread endpoints for cross-device continuity.

Threads are the persistent unit of conversation between a user and the
Praxia agent. They're stored as one JSON file per thread under
``<storage>/chats/<user_id>/<thread_id>.json`` so a desktop client and
a mobile client speaking to the same Praxia server see the same
history.

Endpoints (all under ``/api/v1``):

  GET    /threads                          → list user's threads (newest first)
  POST   /threads                          → create a new thread
  GET    /threads/{thread_id}              → full thread + messages
  POST   /threads/{thread_id}/messages     → append a message
  DELETE /threads/{thread_id}              → remove a thread

The shape is deliberately small — just enough for the desktop/mobile
clients to render a conversation and continue it across devices. Agent
runs (which append an assistant message) go through
:mod:`praxia.server.routers.agent`; this router is the data plane only.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models (module-level so Pydantic / FastAPI can introspect them cleanly)
# ---------------------------------------------------------------------------


class ThreadMessage(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    role: str                                # "user" | "assistant" | "system"
    content: str
    timestamp: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = {}


class Thread(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    user_id: str
    title: str = ""
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    messages: list[ThreadMessage] = []


class CreateThreadRequest(BaseModel):
    title: str = ""


class AppendMessageRequest(BaseModel):
    role: str
    content: str
    metadata: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------


def build_router(*, current_user: Any, storage: Path):
    from fastapi import APIRouter, Depends, HTTPException

    chats_root = Path(storage) / "chats"

    # --- storage helpers ------------------------------------------------

    def _user_dir(user_id: str) -> Path:
        d = chats_root / user_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _thread_path(user_id: str, thread_id: str) -> Path:
        return _user_dir(user_id) / f"{thread_id}.json"

    def _load(user_id: str, thread_id: str) -> Thread:
        p = _thread_path(user_id, thread_id)
        if not p.exists():
            raise HTTPException(404, f"Thread not found: {thread_id}")
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            raise HTTPException(500, f"Thread file corrupt: {e}")
        return Thread.model_validate(data)

    def _save(thread: Thread) -> None:
        p = _thread_path(thread.user_id, thread.id)
        p.write_text(
            json.dumps(thread.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # --- routes ---------------------------------------------------------

    router = APIRouter()

    @router.get("/threads")
    def list_threads(user=Depends(current_user)) -> list[dict[str, Any]]:
        d = chats_root / user.id
        if not d.exists():
            return []
        out: list[dict[str, Any]] = []
        for f in d.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            out.append({
                "id": data.get("id"),
                "title": data.get("title", ""),
                "created_at": data.get("created_at", 0),
                "updated_at": data.get("updated_at", 0),
                "message_count": len(data.get("messages", [])),
            })
        out.sort(key=lambda t: t.get("updated_at", 0), reverse=True)
        return out

    @router.post("/threads")
    def create_thread(
        req: CreateThreadRequest,
        user=Depends(current_user),
    ) -> dict[str, Any]:
        thread = Thread(user_id=user.id, title=req.title)
        _save(thread)
        return {
            "id": thread.id,
            "title": thread.title,
            "created_at": thread.created_at,
            "updated_at": thread.updated_at,
            "message_count": 0,
        }

    @router.get("/threads/{thread_id}")
    def get_thread(thread_id: str, user=Depends(current_user)) -> dict[str, Any]:
        return _load(user.id, thread_id).model_dump()

    @router.post("/threads/{thread_id}/messages")
    def append_message(
        thread_id: str,
        req: AppendMessageRequest,
        user=Depends(current_user),
    ) -> dict[str, Any]:
        if req.role not in {"user", "assistant", "system"}:
            raise HTTPException(400, f"Invalid role: {req.role!r}")
        thread = _load(user.id, thread_id)
        msg = ThreadMessage(role=req.role, content=req.content, metadata=req.metadata)
        thread.messages.append(msg)
        thread.updated_at = time.time()
        # Auto-derive a title from the first user message if none is set
        if not thread.title and req.role == "user":
            thread.title = req.content[:80].replace("\n", " ").strip()
        _save(thread)
        return msg.model_dump()

    @router.delete("/threads/{thread_id}")
    def delete_thread(thread_id: str, user=Depends(current_user)) -> dict[str, Any]:
        p = _thread_path(user.id, thread_id)
        if not p.exists():
            raise HTTPException(404, f"Thread not found: {thread_id}")
        try:
            p.unlink()
        except OSError as e:
            raise HTTPException(500, f"Failed to delete: {e}")
        return {"deleted": thread_id}

    return router
