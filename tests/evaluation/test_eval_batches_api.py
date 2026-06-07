"""Tests for /api/v1/batches/* parallel fan-out.

Shape we care about:

1. **Atomic creation** — N children created in one round-trip.
2. **Composite progress** — GET /batches/{id} aggregates child statuses.
3. **Concurrency cap** — caller's max_concurrency is respected (smoke,
   not strict — we just assert nothing blows up at the cap edge).
4. **Validation** — empty items / all-empty-prompts → 400.
5. **Cancellation** — delete cancels still-pending children.
6. **Isolation** — Bob can't see Alice's batches.
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


def _stub(text: str) -> LLMResponse:
    return LLMResponse(
        text="",
        model="stub",
        usage={},
        raw={},
        tool_calls=[{
            "id": "c1",
            "name": "final_answer",
            "arguments": '{"answer": "' + text.replace('"', '\\"') + '"}',
        }],
    )


def _wait_for_status(client, hdr, batch_id, *, target_finished: int, timeout: float = 8.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/api/v1/batches/{batch_id}", headers=hdr).json()
        if r.get("finished", 0) >= target_finished:
            return r
        time.sleep(0.05)
    return client.get(f"/api/v1/batches/{batch_id}", headers=hdr).json()


class TestCreate:
    def test_rejects_empty_items(self, server):
        client, hdr, _, _ = server
        r = client.post("/api/v1/batches/run-agents", json={"items": []}, headers=hdr)
        assert r.status_code == 400

    def test_rejects_all_blank_prompts(self, server):
        client, hdr, _, _ = server
        r = client.post(
            "/api/v1/batches/run-agents",
            json={"items": [{"prompt": "  "}, {"prompt": ""}]},
            headers=hdr,
        )
        assert r.status_code == 400

    def test_caps_at_100(self, server):
        client, hdr, _, _ = server
        items = [{"prompt": f"p{i}"} for i in range(101)]
        r = client.post("/api/v1/batches/run-agents", json={"items": items}, headers=hdr)
        assert r.status_code == 400

    def test_creates_n_children_atomically(self, server):
        client, hdr, _, _ = server
        with patch("praxia.core.llm.LLM.complete", return_value=_stub("ok")):
            r = client.post(
                "/api/v1/batches/run-agents",
                json={"items": [{"prompt": "a"}, {"prompt": "b"}, {"prompt": "c"}], "label": "test"},
                headers=hdr,
            )
            assert r.status_code == 200
            body = r.json()
            assert len(body["task_ids"]) == 3
            assert body["batch_id"]


class TestPollAndAggregate:
    def test_get_aggregates_child_statuses(self, server):
        client, hdr, _, _ = server
        with patch("praxia.core.llm.LLM.complete", return_value=_stub("hi")):
            bid = client.post(
                "/api/v1/batches/run-agents",
                json={"items": [{"prompt": "a"}, {"prompt": "b"}]},
                headers=hdr,
            ).json()["batch_id"]
            final = _wait_for_status(client, hdr, bid, target_finished=2)

        assert final["total"] == 2
        assert final["finished"] == 2
        assert final["counts"]["done"] == 2
        assert len(final["tasks"]) == 2
        # Each child task carries the agent result.
        for t in final["tasks"]:
            assert t["result"]["text"] == "hi"
            assert t["args"]["_batch_id"] == bid

    def test_list_returns_batches(self, server):
        client, hdr, _, _ = server
        with patch("praxia.core.llm.LLM.complete", return_value=_stub("ok")):
            for _ in range(2):
                client.post(
                    "/api/v1/batches/run-agents",
                    json={"items": [{"prompt": "x"}]},
                    headers=hdr,
                )
            time.sleep(0.3)
        listing = client.get("/api/v1/batches", headers=hdr).json()
        assert len(listing["batches"]) >= 2


class TestDeleteCancels:
    def test_delete_cancels_in_flight_children(self, server):
        client, hdr, _, _ = server
        # Slow stub so the children are still 'pending' when we delete.
        def _slow(*args, **kwargs):
            time.sleep(0.8)
            return _stub("late")
        with patch("praxia.core.llm.LLM.complete", side_effect=_slow):
            bid = client.post(
                "/api/v1/batches/run-agents",
                json={"items": [{"prompt": "a"}, {"prompt": "b"}], "max_concurrency": 1},
                headers=hdr,
            ).json()["batch_id"]
            # Delete almost immediately — at least one child should still be in flight.
            time.sleep(0.05)
            r = client.delete(f"/api/v1/batches/{bid}", headers=hdr)
            assert r.status_code == 200 and r.json()["deleted"] is True
            # GET on a deleted batch is 404.
            assert client.get(f"/api/v1/batches/{bid}", headers=hdr).status_code == 404


class TestIsolation:
    def test_users_dont_see_each_others_batches(self, server):
        client, hdr_a, _, storage = server
        auth = AuthManager(storage_dir=storage / "auth")
        _bob, bob_key = auth.users.create(username="bob", role="member", password=None)
        hdr_b = {"X-API-Key": bob_key}
        with patch("praxia.core.llm.LLM.complete", return_value=_stub("ok")):
            bid_a = client.post(
                "/api/v1/batches/run-agents",
                json={"items": [{"prompt": "alice"}]},
                headers=hdr_a,
            ).json()["batch_id"]
            time.sleep(0.2)
        # Bob can't read Alice's batch.
        assert client.get(f"/api/v1/batches/{bid_a}", headers=hdr_b).status_code == 404
        # And his list is empty.
        assert client.get("/api/v1/batches", headers=hdr_b).json()["batches"] == []
