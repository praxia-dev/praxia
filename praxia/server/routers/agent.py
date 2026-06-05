"""Autonomous-agent endpoint: POST /agent/run.

Synchronous wrapper around :class:`praxia.agent.AutonomousAgent` and
:class:`praxia.agent.CommandedAgent` so a thin client (desktop / mobile)
can ask the server to "do this task" and get back the final answer + tool
trace without orchestrating Python locally.

This is the data-plane companion to :mod:`praxia.server.routers.threads`:
when a client posts a user message into a thread and wants an agent
reply, it calls this endpoint, then appends the returned text as an
assistant message (or passes ``thread_id`` so the server does both in
one round trip).

Streaming + WebSocket variants land in a later phase.
"""
from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel

_log = logging.getLogger(__name__)


# Module-level models so FastAPI / Pydantic introspection works cleanly
class AgentRunRequest(BaseModel):
    prompt: str
    thread_id: str | None = None      # if set, append both user msg + reply
    org_id: str = "default-org"
    model: str = "claude"
    max_steps: int = 8
    verified: bool = False            # use CommandedAgent if True
    max_verify_rounds: int = 3
    memory_dir: str | None = None     # override server's default


class AgentRunResponse(BaseModel):
    text: str
    tool_calls: list[dict[str, Any]] = []
    usage: dict[str, int] = {}
    steps: int = 0
    stopped_reason: str = "completed"
    # Commander-only:
    verdict_decision: str | None = None
    verdict_groundedness: float | None = None
    citations: list[str] = []
    rounds: int | None = None
    # If thread_id was supplied, the new message ids
    user_message_id: str | None = None
    assistant_message_id: str | None = None


def build_router(*, current_user: Any, storage: Path):
    from fastapi import APIRouter, Depends, HTTPException

    chats_root = Path(storage) / "chats"

    # --- thread persistence (lightweight clone — keeps this router self-contained) ----

    def _append_to_thread(
        user_id: str,
        thread_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        import json
        d = chats_root / user_id
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{thread_id}.json"
        if not p.exists():
            raise HTTPException(404, f"Thread not found: {thread_id}")
        data = json.loads(p.read_text(encoding="utf-8"))
        msg_id = uuid.uuid4().hex
        data["messages"].append({
            "id": msg_id,
            "role": role,
            "content": content,
            "timestamp": time.time(),
            "metadata": metadata or {},
        })
        data["updated_at"] = time.time()
        if not data.get("title") and role == "user":
            data["title"] = content[:80].replace("\n", " ").strip()
        p.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return msg_id

    # --- routes --------------------------------------------------------

    router = APIRouter()

    @router.post("/agent/run", response_model=AgentRunResponse)
    def run_agent(req: AgentRunRequest, user=Depends(current_user)):
        if not req.prompt.strip():
            raise HTTPException(400, "Empty prompt")

        # Lazy imports — keeps server router cheap when agent isn't called
        try:
            from praxia.agent import AutonomousAgent, CommandedAgent
            from praxia.core.llm import LLM
        except ImportError as e:  # pragma: no cover
            raise HTTPException(500, f"Praxia agent not available: {e}")

        memory_dir = req.memory_dir or str(Path(storage))

        try:
            llm = LLM(req.model)
        except Exception as e:
            raise HTTPException(500, f"LLM init failed: {e}")

        inner = AutonomousAgent(
            user_id=user.id,
            role=user.role,
            org_id=req.org_id,
            llm=llm,
            memory_dir=memory_dir,
            max_steps=max(1, int(req.max_steps)),
        )

        # If thread_id supplied, persist user message first (so the agent
        # sees it as user-said, and so retries pick it up).
        user_msg_id = None
        if req.thread_id:
            user_msg_id = _append_to_thread(
                user.id, req.thread_id, "user", req.prompt,
            )

        # Execute
        try:
            if req.verified:
                agent = CommandedAgent(
                    inner,
                    max_verify_rounds=max(1, int(req.max_verify_rounds)),
                    require_citations=True,
                )
                cresult = agent.run(req.prompt)
                final_text = cresult.answer
                resp = AgentRunResponse(
                    text=final_text,
                    tool_calls=[],
                    usage=cresult.usage,
                    steps=sum((r.inner_result.steps if r.inner_result else 0) for r in cresult.rounds),
                    stopped_reason=cresult.stopped_reason,
                    verdict_decision=cresult.verdict.decision,
                    verdict_groundedness=cresult.verdict.groundedness,
                    citations=list(cresult.citations),
                    rounds=len(cresult.rounds),
                )
            else:
                result = inner.run(req.prompt)
                resp = AgentRunResponse(
                    text=result.final_text,
                    tool_calls=[
                        {
                            "name": tc.name,
                            "ok": tc.ok,
                            "arguments_preview": tc.arguments_text[:200],
                            "result_preview": tc.result_text[:200],
                        }
                        for tc in result.tool_calls
                    ],
                    usage=result.usage,
                    steps=result.steps,
                    stopped_reason=result.stopped_reason,
                )
                final_text = result.final_text
        except Exception as e:
            _log.exception("Agent run failed")
            raise HTTPException(500, f"Agent run failed: {e}")

        # Persist assistant reply
        if req.thread_id:
            asst_msg_id = _append_to_thread(
                user.id, req.thread_id, "assistant", final_text,
                metadata={"verified": req.verified, "model": req.model},
            )
            resp.user_message_id = user_msg_id
            resp.assistant_message_id = asst_msg_id

        return resp

    return router
