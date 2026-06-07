"""Cron-style schedules for recurring agent runs (Phase 2-B).

A schedule is a saved (cron-expression, prompt, args) tuple. A
background thread per Praxia process ticks every minute and fires
any schedules whose next run-time has arrived; the firing creates a
task via the same machinery as /tasks/run-agent so results show up
in the Tasks tab + audit log alongside one-shot tasks.

The cron parser is intentionally minimal: 5-field POSIX-style with
``*``, ``*/N``, comma lists, and ranges. We avoid pulling in
``croniter`` to keep the dependency tree small for the embedded
sidecar build.

State lives in <storage>/schedules/<user_id>/<schedule_id>.json
exactly like tasks — single-file-per-record so a crash on save
leaves either the new or old version, never a half-written record.
"""
from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schedule record
# ---------------------------------------------------------------------------


@dataclass
class ScheduleRecord:
    id: str
    user_id: str
    cron: str                                     # 5-field POSIX cron
    prompt: str
    args: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    created_at: float = 0.0
    last_run_at: float | None = None
    last_task_id: str | None = None
    next_run_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CreateScheduleRequest(BaseModel):
    cron: str
    prompt: str
    args: dict[str, Any] = {}
    enabled: bool = True


class UpdateScheduleRequest(BaseModel):
    cron: str | None = None
    prompt: str | None = None
    args: dict[str, Any] | None = None
    enabled: bool | None = None


# ---------------------------------------------------------------------------
# Cron parser — minimal 5-field
# ---------------------------------------------------------------------------


def _parse_field(spec: str, lo: int, hi: int) -> set[int]:
    """Return the set of integers in [lo, hi] that match `spec`.

    Accepts: ``*``, ``N``, ``N-M``, ``N,M,K``, ``*/N``, ``N-M/K``.
    Anything else raises ValueError so the caller surfaces a 400.
    """
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        step = 1
        if "/" in part:
            base, step_s = part.split("/", 1)
            step = int(step_s)
            if step <= 0:
                raise ValueError(f"invalid step in {spec!r}")
            part = base
        if part == "*" or part == "":
            r = range(lo, hi + 1, step)
        elif "-" in part:
            a, b = part.split("-", 1)
            r = range(int(a), int(b) + 1, step)
        else:
            n = int(part)
            r = range(n, n + 1)
        for v in r:
            if v < lo or v > hi:
                raise ValueError(f"value {v} out of range [{lo},{hi}] in {spec!r}")
            out.add(v)
    if not out:
        raise ValueError(f"empty field spec {spec!r}")
    return out


def parse_cron(expr: str) -> tuple[set[int], set[int], set[int], set[int], set[int]]:
    """5-field cron: minute hour dom month dow.

    Raises ValueError on malformed input. dow accepts 0 (Sun) or 7
    (also Sun) per POSIX cron convention; we normalise 7 -> 0.
    """
    fields = expr.split()
    if len(fields) != 5:
        raise ValueError(
            f"cron must have 5 fields (minute hour dom month dow), got {len(fields)}"
        )
    minute = _parse_field(fields[0], 0, 59)
    hour = _parse_field(fields[1], 0, 23)
    dom = _parse_field(fields[2], 1, 31)
    month = _parse_field(fields[3], 1, 12)
    dow = _parse_field(fields[4], 0, 7)
    if 7 in dow:
        dow.discard(7); dow.add(0)
    return minute, hour, dom, month, dow


def next_run(expr: str, after: datetime, *, max_minutes: int = 60 * 24 * 366) -> datetime | None:
    """Return the next datetime after `after` that matches `expr`.

    Brute-force minute-by-minute scan, capped at ~1 year. Fine for
    desktop use; an enterprise deployment would swap in a proper
    cron iterator.
    """
    minute, hour, dom, month, dow = parse_cron(expr)
    t = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(max_minutes):
        # Python weekday: Mon=0..Sun=6 → cron Sun=0..Sat=6
        cron_dow = (t.weekday() + 1) % 7
        if (
            t.minute in minute
            and t.hour in hour
            and t.day in dom
            and t.month in month
            and cron_dow in dow
        ):
            return t
        t += timedelta(minutes=1)
    return None


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


def _schedules_dir(storage: Path, user_id: str) -> Path:
    p = Path(storage) / "schedules" / user_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def _save(storage: Path, rec: ScheduleRecord) -> None:
    p = _schedules_dir(storage, rec.user_id) / f"{rec.id}.json"
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


def _load_all_for_user(storage: Path, user_id: str) -> list[ScheduleRecord]:
    out: list[ScheduleRecord] = []
    for f in sorted(_schedules_dir(storage, user_id).glob("*.json")):
        try:
            out.append(ScheduleRecord(**json.loads(f.read_text(encoding="utf-8"))))
        except (OSError, json.JSONDecodeError):
            continue
    return out


def _load_all_global(storage: Path) -> list[ScheduleRecord]:
    """Cross-user iteration for the ticker. Cheap because the desktop
    deployment is single-user; an org deployment with many users
    might want a SQLite index instead."""
    root = Path(storage) / "schedules"
    if not root.exists():
        return []
    out: list[ScheduleRecord] = []
    for user_dir in root.iterdir():
        if not user_dir.is_dir():
            continue
        for f in user_dir.glob("*.json"):
            try:
                out.append(ScheduleRecord(**json.loads(f.read_text(encoding="utf-8"))))
            except (OSError, json.JSONDecodeError):
                continue
    return out


# ---------------------------------------------------------------------------
# Background ticker — one per process
# ---------------------------------------------------------------------------


_TICKER_STARTED = False
_TICKER_LOCK = threading.Lock()


def _start_ticker(storage: Path) -> None:
    """Spawn (once) a daemon thread that wakes every 60 s, scans all
    enabled schedules, and fires any whose next_run_at is due. Tasks
    are created via the in-process API by directly calling the
    threaded worker that backs /tasks/run-agent.
    """
    global _TICKER_STARTED
    with _TICKER_LOCK:
        if _TICKER_STARTED:
            return
        _TICKER_STARTED = True

    def _loop() -> None:
        # Compute initial next_run_at for any schedules missing it.
        while True:
            try:
                _tick_once(storage)
            except Exception:  # pragma: no cover
                _log.exception("schedule ticker iteration failed")
            time.sleep(60)

    threading.Thread(target=_loop, daemon=True, name="praxia-schedules").start()


def _tick_once(storage: Path) -> None:
    """One pass: fire every due schedule + update next_run_at."""
    from praxia.auth.manager import AuthManager
    from praxia.server.routers.tasks import TaskRecord, _save as _save_task, _run_agent_task_threaded

    now = datetime.now()
    now_ts = now.timestamp()

    for rec in _load_all_global(storage):
        if not rec.enabled:
            continue
        if rec.next_run_at is None:
            try:
                nr = next_run(rec.cron, now)
                rec.next_run_at = nr.timestamp() if nr else None
                _save(storage, rec)
            except ValueError:
                continue
            continue
        if rec.next_run_at > now_ts:
            continue

        # Fire — create a Task with the schedule's prompt + args.
        task = TaskRecord(
            id=uuid.uuid4().hex,
            user_id=rec.user_id,
            kind="agent_run",
            args={"prompt": rec.prompt, **(rec.args or {}),
                  "_schedule_id": rec.id},
            created_at=now_ts,
        )
        _save_task(storage, task)
        # Look up the user — needed because the agent run wants
        # user.id / user.role. AuthManager loads from disk.
        try:
            auth = AuthManager(storage_dir=Path(storage) / "auth")
            user = auth.users.get_by_id(rec.user_id)
        except Exception:  # pragma: no cover
            user = None
        if user is None:
            _log.warning("schedule %s targets missing user %s; skipping", rec.id, rec.user_id)
            rec.next_run_at = None
            _save(storage, rec)
            continue
        threading.Thread(
            target=_run_agent_task_threaded,
            args=(storage, user, task),
            daemon=True,
            name=f"praxia-sched-{rec.id[:8]}",
        ).start()

        rec.last_run_at = now_ts
        rec.last_task_id = task.id
        try:
            nr = next_run(rec.cron, now)
            rec.next_run_at = nr.timestamp() if nr else None
        except ValueError:
            rec.next_run_at = None
        _save(storage, rec)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


def build_router(*, current_user: Any, storage: Path):
    from fastapi import APIRouter, Depends, HTTPException

    _start_ticker(storage)
    router = APIRouter()

    @router.post("/schedules")
    def create_schedule(req: CreateScheduleRequest, user=Depends(current_user)):
        if not req.prompt.strip():
            raise HTTPException(400, "Empty prompt")
        try:
            parse_cron(req.cron)  # validate
        except ValueError as e:
            raise HTTPException(400, f"Invalid cron: {e}")
        rec = ScheduleRecord(
            id=uuid.uuid4().hex,
            user_id=user.id,
            cron=req.cron,
            prompt=req.prompt,
            args=req.args or {},
            enabled=req.enabled,
            created_at=time.time(),
        )
        nr = next_run(req.cron, datetime.now())
        rec.next_run_at = nr.timestamp() if nr else None
        _save(storage, rec)
        return rec.to_dict()

    @router.get("/schedules")
    def list_schedules(user=Depends(current_user)):
        return {"schedules": [r.to_dict() for r in _load_all_for_user(storage, user.id)]}

    @router.patch("/schedules/{sched_id}")
    def update_schedule(sched_id: str, req: UpdateScheduleRequest, user=Depends(current_user)):
        p = _schedules_dir(storage, user.id) / f"{sched_id}.json"
        if not p.exists():
            raise HTTPException(404, "Schedule not found")
        rec = ScheduleRecord(**json.loads(p.read_text(encoding="utf-8")))
        if req.cron is not None:
            try:
                parse_cron(req.cron)
            except ValueError as e:
                raise HTTPException(400, f"Invalid cron: {e}")
            rec.cron = req.cron
            nr = next_run(req.cron, datetime.now())
            rec.next_run_at = nr.timestamp() if nr else None
        if req.prompt is not None: rec.prompt = req.prompt
        if req.args is not None: rec.args = req.args
        if req.enabled is not None: rec.enabled = req.enabled
        _save(storage, rec)
        return rec.to_dict()

    @router.delete("/schedules/{sched_id}")
    def delete_schedule(sched_id: str, user=Depends(current_user)):
        p = _schedules_dir(storage, user.id) / f"{sched_id}.json"
        if not p.exists():
            raise HTTPException(404, "Schedule not found")
        try:
            p.unlink()
        except OSError:
            pass
        return {"deleted": True, "id": sched_id}

    return router
