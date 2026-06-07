"""Background task queue — long-running agent runs, persisted state.

The synchronous ``/agent/run`` route is fine for sub-30s queries, but
falls over for anything longer: the browser / mobile app times out,
the user can't switch threads to do other work, and a crash mid-run
loses the result. This module adds an opt-in async task queue.

Flow:

    1. POST /api/v1/tasks/run-agent {prompt, ...}   → 200 {task_id, status: "pending"}
    2. The route schedules the actual agent run on the asyncio event
       loop (FastAPI's default executor for sync work) and returns
       immediately.
    3. The client polls GET /api/v1/tasks/{task_id} or subscribes to
       the SSE stream at GET /api/v1/tasks/stream.
    4. When the task completes the result lands in the task record on
       disk under ``<storage>/tasks/<user_id>/<task_id>.json``.
    5. GET /api/v1/tasks lists the user's recent tasks (across server
       restarts — that's why we persist).

State is persisted to disk so that:
- A crashed server doesn't lose pending work the user is waiting on.
  (We can't resume mid-LLM, but we can mark it as ``error`` on next
  boot.)
- The desktop app can list "tasks you started yesterday" even after
  a reboot.
"""
from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Task model
# ---------------------------------------------------------------------------


@dataclass
class TaskRecord:
    id: str
    user_id: str
    kind: str                                    # "agent_run" — extensible
    args: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"                      # pending | running | done | error | cancelled
    created_at: float = 0.0
    started_at: float | None = None
    finished_at: float | None = None
    result: dict[str, Any] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RunAgentTaskRequest(BaseModel):
    """Body for POST /tasks/run-agent — same fields as /agent/run.

    Kept loose (dict[str, Any]) because mirroring every /agent/run
    field here would re-couple this module to the agent router. The
    task handler hands the dict back through the same path so the
    schemas stay in lockstep by passing through, not by duplication.
    """
    prompt: str
    args: dict[str, Any] = {}


class CreateTaskResponse(BaseModel):
    task_id: str
    status: str
    created_at: float


# ---------------------------------------------------------------------------
# On-disk persistence — JSON file per task
# ---------------------------------------------------------------------------


def _tasks_dir(storage: Path, user_id: str) -> Path:
    p = Path(storage) / "tasks" / user_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def _task_path(storage: Path, user_id: str, task_id: str) -> Path:
    return _tasks_dir(storage, user_id) / f"{task_id}.json"


def _save(storage: Path, rec: TaskRecord) -> None:
    """Persist a TaskRecord atomically.

    On Windows, ``os.replace`` fails (WinError 5) if another process /
    thread has the destination open for reading. Tasks are read by
    GET /tasks/{id} polls running in parallel, so collisions are
    real — retry a handful of times with a tiny backoff before giving
    up. POSIX systems don't hit this and the first attempt always
    wins.
    """
    p = _task_path(storage, rec.user_id, rec.id)
    tmp = p.with_suffix(".json.tmp")
    payload = json.dumps(rec.to_dict(), ensure_ascii=False)
    tmp.write_text(payload, encoding="utf-8")
    last_err: OSError | None = None
    for attempt in range(8):
        try:
            tmp.replace(p)
            return
        except PermissionError as e:
            last_err = e
            time.sleep(0.02 * (attempt + 1))
    # Final fallback: write directly. Loses atomicity but avoids
    # losing the record entirely if something pathological is going
    # on with the disk.
    try:
        p.write_text(payload, encoding="utf-8")
    except OSError:
        if last_err is not None:
            raise last_err
        raise
    try:
        tmp.unlink()
    except OSError:
        pass


def _load(storage: Path, user_id: str, task_id: str) -> TaskRecord | None:
    p = _task_path(storage, user_id, task_id)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return TaskRecord(**data)


def _list_for_user(storage: Path, user_id: str) -> list[TaskRecord]:
    out: list[TaskRecord] = []
    for f in sorted(_tasks_dir(storage, user_id).glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            out.append(TaskRecord(**data))
        except (OSError, json.JSONDecodeError):
            continue
    return out


def _reap_running_on_startup(storage: Path) -> None:
    """Server restarted while tasks were mid-flight — mark them as
    errored so clients polling get a clear answer instead of
    forever-pending. Called once by the router factory."""
    root = Path(storage) / "tasks"
    if not root.exists():
        return
    for user_dir in root.iterdir():
        if not user_dir.is_dir():
            continue
        for f in user_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if data.get("status") in {"pending", "running"}:
                data["status"] = "error"
                data["error"] = "Server restarted while task was running; result lost."
                data["finished_at"] = time.time()
                try:
                    f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                except OSError:
                    pass


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------


def build_router(*, current_user: Any, storage: Path):
    from fastapi import APIRouter, Depends, HTTPException

    # Reap any half-finished tasks left over from a previous run.
    _reap_running_on_startup(storage)

    router = APIRouter()

    @router.post("/tasks/run-agent", response_model=CreateTaskResponse)
    def create_run_agent_task(
        req: RunAgentTaskRequest,
        user=Depends(current_user),
    ):
        if not req.prompt.strip():
            raise HTTPException(400, "Empty prompt")

        rec = TaskRecord(
            id=uuid.uuid4().hex,
            user_id=user.id,
            kind="agent_run",
            args={"prompt": req.prompt, **(req.args or {})},
            created_at=time.time(),
        )
        _save(storage, rec)

        # Background OS thread, NOT asyncio.create_task. The latter
        # ties task progress to the FastAPI event loop, which is fine
        # under uvicorn but pauses between requests under TestClient
        # — leaving record.status stuck at "running" forever. A bare
        # daemon thread is decoupled from the loop's lifecycle, runs
        # the same in test and prod, and the GIL still lets us share
        # the storage Path + user record safely (we only mutate files,
        # never the in-memory user object).
        thread = threading.Thread(
            target=_run_agent_task_threaded,
            args=(storage, user, rec),
            daemon=True,
            name=f"praxia-task-{rec.id[:8]}",
        )
        thread.start()

        return CreateTaskResponse(
            task_id=rec.id, status=rec.status, created_at=rec.created_at
        )

    @router.get("/tasks/{task_id}")
    def get_task(task_id: str, user=Depends(current_user)):
        rec = _load(storage, user.id, task_id)
        if rec is None:
            raise HTTPException(404, f"Task {task_id} not found")
        return rec.to_dict()

    @router.get("/tasks")
    def list_tasks(user=Depends(current_user), limit: int = 50):
        out = _list_for_user(storage, user.id)
        return {"tasks": [r.to_dict() for r in out[: max(1, int(limit))]]}

    @router.delete("/tasks/{task_id}")
    def delete_task(task_id: str, user=Depends(current_user)):
        rec = _load(storage, user.id, task_id)
        if rec is None:
            raise HTTPException(404, f"Task {task_id} not found")
        # Best-effort cancel: we can't yank the underlying LLM call,
        # but we can mark the record so polling clients stop waiting.
        if rec.status in {"pending", "running"}:
            rec.status = "cancelled"
            rec.finished_at = time.time()
            _save(storage, rec)
        # Then physically delete the record. If a still-running task
        # eventually finishes it will write back a fresh record with
        # the same id; that's an edge case the next reap will tidy up.
        try:
            _task_path(storage, user.id, task_id).unlink()
        except OSError:
            pass
        return {"deleted": True, "id": task_id}

    return router


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------


def _run_agent_task_threaded(storage: Path, user, rec: TaskRecord) -> None:
    """Execute the queued agent run on a background OS thread.

    Synchronous all the way down — no asyncio inside. The thread is a
    daemon so it doesn't block process exit; if the server is killed
    mid-run the next boot's reaper marks the record as errored.
    """
    rec.status = "running"
    rec.started_at = time.time()
    _save(storage, rec)
    try:
        rec.result = _invoke_agent(storage, user, rec.args)
        rec.status = "done"
    except Exception as e:  # pragma: no cover - integration paths
        _log.exception("Background agent task %s failed", rec.id)
        rec.status = "error"
        rec.error = str(e)
    finally:
        rec.finished_at = time.time()
        _save(storage, rec)


def _invoke_agent(storage: Path, user, args: dict[str, Any]) -> dict[str, Any]:
    """Synchronous entry point — invoked off the event loop.

    Mirrors the /agent/run handler in praxia.server.routers.agent but
    intentionally lightweight: we don't re-implement thread-message
    persistence here. Background tasks are "send + come back later";
    the agent's reply lands on the task record, not on a chat thread,
    unless the caller wires `thread_id` into args and we forward it.
    """
    from praxia.agent import AutonomousAgent, CommandedAgent
    from praxia.core.llm import LLM

    prompt = args.get("prompt") or ""
    model = args.get("model") or "claude"
    scout_model = args.get("scout_model") or None
    max_steps = max(1, int(args.get("max_steps", 8)))
    verified = bool(args.get("verified", False))
    workspace_root = args.get("workspace_root") or None

    llm = LLM(model)
    scout_llm = None
    if scout_model and scout_model != model:
        try:
            scout_llm = LLM(scout_model)
        except Exception:  # pragma: no cover
            scout_llm = None

    extra_tools = []
    pending_file_ops: list[dict[str, Any]] = []
    if workspace_root:
        try:
            from praxia.agent.file_tools import workspace_tools
            tools_dict = workspace_tools(
                workspace_root,
                require_confirmation=True,
                pending_sink=pending_file_ops,
            )
            extra_tools = list(tools_dict.values())
        except Exception as e:
            return {"error": f"workspace_tools failed: {e}"}

    inner = AutonomousAgent(
        user_id=user.id,
        role=user.role,
        org_id=args.get("org_id", "default-org"),
        llm=llm,
        memory_dir=str(storage),
        max_steps=max_steps,
        extra_tools=extra_tools or None,
    )

    if verified:
        agent = CommandedAgent(
            inner,
            scout_llm=scout_llm,
            max_verify_rounds=max(1, int(args.get("max_verify_rounds", 3))),
            require_citations=True,
        )
        cresult = agent.run(prompt)
        # Same source serialisation as /agent/run so Tasks-tab consumers
        # can render the citation panel with full doc paths.
        sources_payload: list[dict[str, Any]] = []
        for s in cresult.sources:
            sources_payload.append({
                "id": s.id,
                "kind": s.kind,
                "text_preview": (s.text or "")[:500],
                "text_truncated": len(s.text or "") > 500,
                "metadata": dict(s.metadata or {}),
            })
        return {
            "text": cresult.answer,
            "stopped_reason": cresult.stopped_reason,
            "verdict_decision": cresult.verdict.decision,
            "verdict_groundedness": cresult.verdict.groundedness,
            "citations": list(cresult.citations),
            "sources": sources_payload,
            "rounds": len(cresult.rounds),
            "pending_file_operations": list(pending_file_ops),
        }

    result = inner.run(prompt)
    return {
        "text": result.final_text,
        "stopped_reason": result.stopped_reason,
        "tool_calls": [
            {
                "name": tc.name,
                "ok": tc.ok,
                "arguments_preview": tc.arguments_text[:200],
                "result_preview": tc.result_text[:200],
            }
            for tc in result.tool_calls
        ],
        "usage": result.usage,
        "steps": result.steps,
        "pending_file_operations": list(pending_file_ops),
    }
