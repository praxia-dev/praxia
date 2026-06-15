"""Coverage for the alpha34 batch/task/schedule lookup tools.

The motivating bug: agent fanned out 8 batch children, user asked
"8件分のアクションアイテムを一覧にまとめて", agent said "I can't
access the results, paste them here". The actual results were on
disk the whole time — the agent just had no tool to read them.

Same gap existed for Tasks and Schedules: after creating, no read.
This file pins the new tools:
  - get_batch_results — per-child outputs by batch_id
  - list_recent_batches — sidebar-style summaries
  - get_task_result — single task by id
  - list_recent_tasks — newest-first with status filter
  - list_my_schedules — cron + next_run_at + last_run_at
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from praxia.agent.tools import (
    _get_batch_results,
    _get_task_result,
    _list_my_schedules,
    _list_recent_batches,
    _list_recent_tasks,
    builtin_tools,
)


def _agent(tmp_path: Path, user_id: str = "alice") -> MagicMock:
    a = MagicMock()
    a.user_id = user_id
    a.memory_dir = str(tmp_path)
    return a


def _write_task(
    tmp_path: Path, user_id: str, *,
    task_id: str | None = None,
    prompt: str = "summarise X.pdf",
    status: str = "done",
    result_text: str = "RESULT BODY",
    batch_id: str | None = None,
    schedule_id: str | None = None,
    created_at: float | None = None,
) -> str:
    from praxia.server.routers.tasks import TaskRecord, _save as _save_task
    tid = task_id or uuid.uuid4().hex
    args: dict = {"prompt": prompt}
    if batch_id:
        args["_batch_id"] = batch_id
    if schedule_id:
        args["_schedule_id"] = schedule_id
    rec = TaskRecord(
        id=tid,
        user_id=user_id,
        kind="agent_run",
        args=args,
        status=status,
        created_at=created_at if created_at is not None else time.time(),
        finished_at=time.time() if status == "done" else None,
        result={"text": result_text} if status == "done" else None,
    )
    _save_task(tmp_path, rec)
    return tid


def _write_batch(
    tmp_path: Path, user_id: str, *,
    label: str | None = None,
    task_ids: list[str] | None = None,
) -> str:
    from praxia.server.routers.batch import BatchRecord, _save as _save_batch
    bid = uuid.uuid4().hex
    rec = BatchRecord(
        id=bid,
        user_id=user_id,
        task_ids=task_ids or [],
        created_at=time.time(),
        label=label or "test batch",
    )
    _save_batch(tmp_path, rec)
    return bid


# ─── Registration ────────────────────────────────────────────────────


class TestRegistration:
    def test_all_lookup_tools_registered(self) -> None:
        tools = builtin_tools()
        for name in (
            "get_batch_results",
            "list_recent_batches",
            "get_task_result",
            "list_recent_tasks",
            "list_my_schedules",
        ):
            assert name in tools, f"{name} not registered"


# ─── get_batch_results ───────────────────────────────────────────────


class TestGetBatchResults:
    def test_aggregates_completed_children(self, tmp_path: Path) -> None:
        bid = _write_batch(tmp_path, "alice", label="Q3 retro")
        t1 = _write_task(tmp_path, "alice", prompt="summarise A.pdf",
                         result_text="Action items from A.pdf", batch_id=bid)
        t2 = _write_task(tmp_path, "alice", prompt="summarise B.pdf",
                         result_text="Action items from B.pdf", batch_id=bid)
        # Patch the batch record's task_ids to point at our written tasks.
        from praxia.server.routers.batch import _load as _lb, _save as _sb
        rec = _lb(tmp_path, "alice", bid)
        rec.task_ids = [t1, t2]
        _sb(tmp_path, rec)

        res = _get_batch_results(_agent(tmp_path), batch_id=bid,
                                 wait_for_completion=False)
        assert res["found"] is True
        assert res["total"] == 2
        assert res["counts"]["done"] == 2
        ids = [c["task_id"] for c in res["children"]]
        assert set(ids) == {t1, t2}
        for c in res["children"]:
            assert "Action items" in c["result_text"]

    def test_missing_batch_returns_error(self, tmp_path: Path) -> None:
        res = _get_batch_results(_agent(tmp_path), batch_id="bogus",
                                 wait_for_completion=False)
        assert res["found"] is False
        assert "not found" in res["error"]


# ─── get_task_result ─────────────────────────────────────────────────


class TestGetTaskResult:
    def test_returns_done_task_body(self, tmp_path: Path) -> None:
        tid = _write_task(tmp_path, "alice", result_text="hello world body")
        res = _get_task_result(_agent(tmp_path), task_id=tid,
                               wait_for_completion=False)
        assert res["found"] is True
        assert res["status"] == "done"
        assert "hello world" in res["result_text"]

    def test_truncates_long_result(self, tmp_path: Path) -> None:
        tid = _write_task(tmp_path, "alice", result_text="X" * 20_000)
        res = _get_task_result(_agent(tmp_path), task_id=tid,
                               wait_for_completion=False, max_chars=500)
        assert res["result_truncated"] is True
        assert len(res["result_text"]) == 500


# ─── list_recent_tasks ───────────────────────────────────────────────


class TestListRecentTasks:
    def test_newest_first(self, tmp_path: Path) -> None:
        old = _write_task(tmp_path, "alice", prompt="old one", created_at=100.0)
        new = _write_task(tmp_path, "alice", prompt="new one", created_at=2000.0)
        res = _list_recent_tasks(_agent(tmp_path))
        ids = [t["task_id"] for t in res["tasks"]]
        assert ids[0] == new
        assert ids[1] == old

    def test_status_filter(self, tmp_path: Path) -> None:
        _write_task(tmp_path, "alice", status="done", prompt="x")
        _write_task(tmp_path, "alice", status="error", prompt="y")
        res = _list_recent_tasks(_agent(tmp_path), status="error")
        assert res["count"] == 1
        assert res["tasks"][0]["prompt"] == "y"


# ─── list_recent_batches ─────────────────────────────────────────────


class TestListRecentBatches:
    def test_lists_with_labels_and_task_count(self, tmp_path: Path) -> None:
        bid_a = _write_batch(tmp_path, "alice", label="alpha",
                             task_ids=["t1", "t2", "t3"])
        bid_b = _write_batch(tmp_path, "alice", label="beta",
                             task_ids=["t4"])
        res = _list_recent_batches(_agent(tmp_path))
        labels = {b["label"] for b in res["batches"]}
        assert labels == {"alpha", "beta"}
        counts = {b["batch_id"]: b["task_count"] for b in res["batches"]}
        assert counts[bid_a] == 3
        assert counts[bid_b] == 1


# ─── list_my_schedules ───────────────────────────────────────────────


class TestListSchedules:
    def test_lists_enabled_schedules_sorted_by_next_run(self, tmp_path: Path) -> None:
        from praxia.server.routers.schedules import ScheduleRecord, _save
        rec_a = ScheduleRecord(
            id="a", user_id="alice", cron="0 9 * * 1",
            prompt="JA prompt", enabled=True,
            created_at=time.time(), next_run_at=3000.0,
        )
        rec_b = ScheduleRecord(
            id="b", user_id="alice", cron="*/30 * * * *",
            prompt="other", enabled=True,
            created_at=time.time(), next_run_at=1000.0,  # sooner
        )
        rec_c = ScheduleRecord(
            id="c", user_id="alice", cron="0 0 1 * *",
            prompt="disabled", enabled=False,
            created_at=time.time(), next_run_at=500.0,
        )
        for r in (rec_a, rec_b, rec_c):
            _save(tmp_path, r)

        res = _list_my_schedules(_agent(tmp_path))
        ids = [s["schedule_id"] for s in res["schedules"]]
        # Sorted by next_run_at asc; disabled one excluded by default.
        assert ids == ["b", "a"]
        assert res["count"] == 2

    def test_include_disabled(self, tmp_path: Path) -> None:
        from praxia.server.routers.schedules import ScheduleRecord, _save
        _save(tmp_path, ScheduleRecord(
            id="x", user_id="alice", cron="0 9 * * 1",
            prompt="P", enabled=False, created_at=time.time(),
        ))
        res = _list_my_schedules(_agent(tmp_path), include_disabled=True)
        assert res["count"] == 1
        assert res["schedules"][0]["enabled"] is False
