"""Tests for the /api/v1/tasks/* background queue.

The shape we care about:

1. **Fire-and-forget**: POST /tasks/run-agent returns immediately with
   a task_id and pending status; the agent run happens off the
   request/response cycle.
2. **Polling**: GET /tasks/{id} reflects the lifecycle
   (pending → running → done) and exposes the agent result when done.
3. **Per-user isolation**: Alice's tasks aren't visible to Bob.
4. **Crash recovery**: tasks left in "running" across a restart are
   marked errored so polling clients don't hang forever.
5. **Cancel / cleanup**: DELETE removes the record.
"""
from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from praxia.auth.manager import AuthManager  # noqa: E402
from praxia.core.llm import LLMResponse  # noqa: E402
from praxia.server.app import create_app  # noqa: E402


@pytest.fixture
def server(tmp_path: Path):
    storage = tmp_path / "praxia"
    auth = AuthManager(storage_dir=storage / "auth")
    user, api_key = auth.users.create(username="alice", role="member", password=None)
    app = create_app(storage_dir=storage)
    client = TestClient(app)
    return client, {"X-API-Key": api_key}, user, storage


def _stub_llm_response(text: str) -> LLMResponse:
    final_call = {
        "id": "c1",
        "name": "final_answer",
        "arguments": '{"answer": "' + text.replace('"', '\\"') + '"}',
    }
    return LLMResponse(text="", model="stub", usage={}, raw={}, tool_calls=[final_call])


def _wait_until(predicate, *, timeout: float = 5.0, interval: float = 0.05):
    """Poll a predicate until it returns truthy or the timeout fires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(interval)
    return predicate()


class TestCreateAndPoll:
    def test_create_returns_task_id_immediately(self, server):
        client, hdr, _, _ = server
        with patch("praxia.core.llm.LLM.complete", return_value=_stub_llm_response("hi")):
            r = client.post(
                "/api/v1/tasks/run-agent",
                json={"prompt": "say hi"},
                headers=hdr,
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "task_id" in body
        assert body["status"] in ("pending", "running", "done")

    def test_task_completes_and_result_is_readable(self, server):
        client, hdr, _, _ = server
        # Keep the patch ALIVE across the polling loop — the background
        # worker fires asyncio.create_task() and runs later, so the
        # mock must still be active when LLM.complete is actually called.
        with patch("praxia.core.llm.LLM.complete", return_value=_stub_llm_response("hello world")):
            tid = client.post(
                "/api/v1/tasks/run-agent",
                json={"prompt": "say hi"},
                headers=hdr,
            ).json()["task_id"]

            def _poll():
                rec = client.get(f"/api/v1/tasks/{tid}", headers=hdr).json()
                return rec if rec["status"] in ("done", "error") else None
            final = _wait_until(_poll, timeout=10.0)

        assert final is not None, "task never reached terminal state"
        assert final["status"] == "done", final
        assert final["result"]["text"] == "hello world"

    def test_404_for_unknown_task(self, server):
        client, hdr, _, _ = server
        r = client.get("/api/v1/tasks/doesnotexist", headers=hdr)
        assert r.status_code == 404

    def test_400_on_empty_prompt(self, server):
        client, hdr, _, _ = server
        r = client.post(
            "/api/v1/tasks/run-agent",
            json={"prompt": "   "},
            headers=hdr,
        )
        assert r.status_code == 400


class TestListing:
    def test_list_returns_recent_tasks(self, server):
        client, hdr, _, _ = server
        with patch("praxia.core.llm.LLM.complete", return_value=_stub_llm_response("ok")):
            for _ in range(3):
                client.post(
                    "/api/v1/tasks/run-agent",
                    json={"prompt": "ping"},
                    headers=hdr,
                )
            # Brief wait for them to land on disk
            time.sleep(0.3)
        listing = client.get("/api/v1/tasks", headers=hdr).json()
        assert len(listing["tasks"]) >= 3

    def test_tasks_isolated_by_user(self, server, tmp_path: Path):
        client, hdr_alice, _, storage = server
        auth = AuthManager(storage_dir=storage / "auth")
        bob, bob_key = auth.users.create(username="bob", role="member", password=None)
        hdr_bob = {"X-API-Key": bob_key}

        with patch("praxia.core.llm.LLM.complete", return_value=_stub_llm_response("a")):
            tid_alice = client.post(
                "/api/v1/tasks/run-agent",
                json={"prompt": "alice prompt"},
                headers=hdr_alice,
            ).json()["task_id"]
            time.sleep(0.3)

        # Bob can't see Alice's task
        r = client.get(f"/api/v1/tasks/{tid_alice}", headers=hdr_bob)
        assert r.status_code == 404
        # And Bob's task list is empty
        bob_listing = client.get("/api/v1/tasks", headers=hdr_bob).json()
        assert bob_listing["tasks"] == []


class TestDelete:
    def test_delete_removes_record(self, server):
        client, hdr, _, _ = server
        with patch("praxia.core.llm.LLM.complete", return_value=_stub_llm_response("ok")):
            tid = client.post(
                "/api/v1/tasks/run-agent",
                json={"prompt": "ping"},
                headers=hdr,
            ).json()["task_id"]
            time.sleep(0.3)
        r = client.delete(f"/api/v1/tasks/{tid}", headers=hdr)
        assert r.status_code == 200
        assert client.get(f"/api/v1/tasks/{tid}", headers=hdr).status_code == 404


class TestCrashRecovery:
    def test_reap_marks_in_flight_tasks_as_error(self, tmp_path: Path):
        """Simulate a server crash: write a 'running' record by hand,
        then boot a fresh server — the reaper should rewrite the
        record as errored so clients polling for it get a clean
        answer instead of hanging forever."""
        storage = tmp_path / "praxia"
        auth = AuthManager(storage_dir=storage / "auth")
        user, key = auth.users.create(username="alice", role="member", password=None)

        # Pre-stage a fake "running" record on disk
        from praxia.server.routers.tasks import TaskRecord, _save
        rec = TaskRecord(
            id="ghost",
            user_id=user.id,
            kind="agent_run",
            args={"prompt": "lost"},
            status="running",
            created_at=time.time() - 100,
            started_at=time.time() - 90,
        )
        _save(storage, rec)

        # New server starts → reaper fires in tasks_router.build_router
        app = create_app(storage_dir=storage)
        client = TestClient(app)
        out = client.get(
            "/api/v1/tasks/ghost", headers={"X-API-Key": key}
        ).json()
        assert out["status"] == "error"
        assert "restart" in out["error"].lower()
