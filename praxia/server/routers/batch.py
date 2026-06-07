"""Parallel multi-task fan-out (Phase 2-C).

POST /batches/run-agents accepts a list of prompts (each with its own
optional args) and returns a batch_id plus the list of child task_ids.
Each child is a normal TaskRecord — visible in /tasks, persisted the
same way, cancellable individually. The batch record itself only
tracks aggregate state so the UI can show a single progress bar
("3 of 7 done") instead of fanning out into N polls.

Why not loop /tasks/run-agent on the client?
  * Atomic creation — partial fan-outs on a flaky connection are
    confusing. One round-trip either fans the whole batch or nothing.
  * Concurrency cap — we throttle the worker pool here so a 50-item
    batch doesn't slam the model provider with 50 simultaneous calls.
  * Aggregate views — /batches/{id} returns one composite status.
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

from praxia.server.routers.tasks import (
    TaskRecord,
    _list_for_user as _list_tasks_for_user,
    _load as _load_task,
    _run_agent_task_threaded,
    _save as _save_task,
)

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Batch record
# ---------------------------------------------------------------------------


@dataclass
class BatchRecord:
    id: str
    user_id: str
    task_ids: list[str] = field(default_factory=list)
    created_at: float = 0.0
    label: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BatchItem(BaseModel):
    prompt: str
    args: dict[str, Any] = {}


class CreateBatchRequest(BaseModel):
    items: list[BatchItem]
    label: str | None = None
    # Max concurrent runners. The default is conservative — model
    # providers rate-limit per-account and a queue of 50 will often
    # 429. We start 4 at a time and let later items drain in as the
    # earlier ones finish.
    max_concurrency: int = 4


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


def _batches_dir(storage: Path, user_id: str) -> Path:
    p = Path(storage) / "batches" / user_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def _save(storage: Path, rec: BatchRecord) -> None:
    p = _batches_dir(storage, rec.user_id) / f"{rec.id}.json"
    tmp = p.with_suffix(".json.tmp")
    payload = json.dumps(rec.to_dict(), ensure_ascii=False)
    tmp.write_text(payload, encoding="utf-8")
    for attempt in range(8):
        try:
            tmp.replace(p)
            return
        except PermissionError:
            time.sleep(0.02 * (attempt + 1))
    p.write_text(payload, encoding="utf-8")


def _load(storage: Path, user_id: str, batch_id: str) -> BatchRecord | None:
    p = _batches_dir(storage, user_id) / f"{batch_id}.json"
    if not p.exists():
        return None
    try:
        return BatchRecord(**json.loads(p.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------------------
# Concurrency-capped fan-out
# ---------------------------------------------------------------------------


def _run_batch(storage: Path, user, tasks: list[TaskRecord], max_concurrency: int) -> None:
    """Process `tasks` with at most `max_concurrency` in flight.

    A bounded semaphore — not a thread pool executor — because each
    task body is itself synchronous and spawns no further work; we
    just need to gate how many run concurrently. The thread sleeps in
    `_run_agent_task_threaded` while waiting on the LLM, so the OS
    can schedule plenty of these in parallel.
    """
    sem = threading.Semaphore(max(1, int(max_concurrency)))

    def runner(t: TaskRecord) -> None:
        with sem:
            try:
                _run_agent_task_threaded(storage, user, t)
            except Exception:  # pragma: no cover - belt + braces
                _log.exception("batch child %s failed unexpectedly", t.id)

    for t in tasks:
        threading.Thread(
            target=runner,
            args=(t,),
            daemon=True,
            name=f"praxia-batch-{t.id[:8]}",
        ).start()


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


def build_router(*, current_user: Any, storage: Path):
    from fastapi import APIRouter, Depends, HTTPException

    router = APIRouter()

    @router.post("/batches/run-agents")
    def create_batch(req: CreateBatchRequest, user=Depends(current_user)):
        if not req.items:
            raise HTTPException(400, "items must be non-empty")
        if len(req.items) > 100:
            # Hard cap — a runaway fan-out from a misbehaving caller
            # would chew through provider quota fast. 100 is well above
            # any realistic Desktop UX flow.
            raise HTTPException(400, "Maximum 100 items per batch")

        children: list[TaskRecord] = []
        now = time.time()
        batch_id = uuid.uuid4().hex
        for item in req.items:
            if not item.prompt.strip():
                continue
            t = TaskRecord(
                id=uuid.uuid4().hex,
                user_id=user.id,
                kind="agent_run",
                args={"prompt": item.prompt, **(item.args or {}),
                      "_batch_id": batch_id},
                created_at=now,
            )
            _save_task(storage, t)
            children.append(t)

        if not children:
            raise HTTPException(400, "All items had empty prompts")

        rec = BatchRecord(
            id=batch_id,
            user_id=user.id,
            task_ids=[t.id for t in children],
            created_at=now,
            label=req.label,
        )
        _save(storage, rec)

        # Hand off to background threads. The route returns as soon as
        # the records are persisted — same UX as /tasks/run-agent.
        _run_batch(storage, user, children, req.max_concurrency)

        return {
            "batch_id": rec.id,
            "task_ids": rec.task_ids,
            "created_at": rec.created_at,
        }

    @router.get("/batches/{batch_id}")
    def get_batch(batch_id: str, user=Depends(current_user)):
        rec = _load(storage, user.id, batch_id)
        if rec is None:
            raise HTTPException(404, "Batch not found")
        # Composite view: pull each child task's current state from the
        # tasks store. This is O(N) reads per poll which is fine at
        # batch sizes ≤ 100; if we ever raise the cap we'll cache a
        # roll-up in the batch record itself.
        children = []
        counts = {"pending": 0, "running": 0, "done": 0, "error": 0, "cancelled": 0}
        for tid in rec.task_ids:
            t = _load_task(storage, user.id, tid)
            if t is None:
                continue
            children.append(t.to_dict())
            counts[t.status] = counts.get(t.status, 0) + 1
        total = len(rec.task_ids)
        terminal = counts["done"] + counts["error"] + counts["cancelled"]
        return {
            **rec.to_dict(),
            "tasks": children,
            "counts": counts,
            "total": total,
            "finished": terminal,
            "in_flight": total - terminal,
        }

    @router.get("/batches")
    def list_batches(user=Depends(current_user), limit: int = 20):
        d = _batches_dir(storage, user.id)
        # alpha23+: sort by ``created_at`` desc so the UI's Recent list
        # shows newest-first (matching Tasks tab UX). Pre-alpha23 sorted
        # by filename which is the batch id — UUID hex, so effectively
        # random — and users saw new batches appearing in the middle of
        # the list.
        rows: list[dict[str, Any]] = []
        for f in d.glob("*.json"):
            try:
                rows.append(json.loads(f.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        rows.sort(key=lambda r: r.get("created_at", 0.0), reverse=True)
        return {"batches": rows[: max(1, int(limit))]}

    @router.delete("/batches/{batch_id}")
    def delete_batch(batch_id: str, user=Depends(current_user)):
        rec = _load(storage, user.id, batch_id)
        if rec is None:
            raise HTTPException(404, "Batch not found")
        # Cancel any still-in-flight children — same best-effort semantic
        # as /tasks/{id} DELETE: we mark the record so polling stops,
        # but can't yank a running LLM call mid-flight.
        for tid in rec.task_ids:
            t = _load_task(storage, user.id, tid)
            if t is None or t.status not in {"pending", "running"}:
                continue
            t.status = "cancelled"
            t.finished_at = time.time()
            _save_task(storage, t)
        try:
            (_batches_dir(storage, user.id) / f"{batch_id}.json").unlink()
        except OSError:
            pass
        return {"deleted": True, "id": batch_id}

    return router


# Re-exported so tests can clear state without poking at private names.
__all__ = ["build_router", "BatchRecord", "_save", "_load"]
# Touch helpers so linters don't drop the import when we surface them
# in __all__ (some configurations are strict about unused names).
_ = (_list_tasks_for_user,)
