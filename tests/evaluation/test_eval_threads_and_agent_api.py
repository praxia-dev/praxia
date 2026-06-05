"""Integration tests for the new /threads/* and /agent/run endpoints.

Uses FastAPI's TestClient + a temporary storage dir per test. Agent runs
are exercised against a stubbed LLM so the tests don't reach any
external API.
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

# Skip the whole module if FastAPI isn't installed (mirrors how the
# server itself imports FastAPI lazily).
fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from praxia.auth.manager import AuthManager  # noqa: E402
from praxia.core.llm import LLMResponse  # noqa: E402
from praxia.server.app import create_app  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def server(tmp_path: Path):
    """Build a fresh Praxia server + auth headers for a test user."""
    # Ensure the auth manager bootstraps under tmp_path
    storage = tmp_path / "praxia"
    auth = AuthManager(storage_dir=storage / "auth")

    # Create a test user with a known API key
    user, api_key = auth.users.create(
        username="alice",
        role="member",
        password=None,
    )

    app = create_app(storage_dir=storage)
    client = TestClient(app)
    headers = {"X-API-Key": api_key}
    return client, headers, user


# ---------------------------------------------------------------------------
# Thread CRUD
# ---------------------------------------------------------------------------


class TestThreadsCrud:
    def test_create_then_list(self, server):
        client, headers, _user = server
        r = client.post("/api/v1/threads", json={"title": "Q4 planning"}, headers=headers)
        assert r.status_code == 200, r.text
        tid = r.json()["id"]
        assert tid

        r = client.get("/api/v1/threads", headers=headers)
        assert r.status_code == 200
        listing = r.json()
        assert len(listing) == 1
        assert listing[0]["id"] == tid
        assert listing[0]["title"] == "Q4 planning"
        assert listing[0]["message_count"] == 0

    def test_get_thread_returns_messages(self, server):
        client, headers, _ = server
        tid = client.post("/api/v1/threads", json={"title": ""}, headers=headers).json()["id"]
        client.post(
            f"/api/v1/threads/{tid}/messages",
            json={"role": "user", "content": "hello"},
            headers=headers,
        )
        r = client.get(f"/api/v1/threads/{tid}", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == tid
        assert len(data["messages"]) == 1
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][0]["content"] == "hello"

    def test_append_message_sets_title_when_empty(self, server):
        client, headers, _ = server
        tid = client.post("/api/v1/threads", json={"title": ""}, headers=headers).json()["id"]
        client.post(
            f"/api/v1/threads/{tid}/messages",
            json={"role": "user", "content": "What's our SOP for fault E-204?"},
            headers=headers,
        )
        listing = client.get("/api/v1/threads", headers=headers).json()
        # Title is auto-derived from the first user message
        assert listing[0]["title"].startswith("What's our SOP")

    def test_append_rejects_unknown_role(self, server):
        client, headers, _ = server
        tid = client.post("/api/v1/threads", json={"title": ""}, headers=headers).json()["id"]
        r = client.post(
            f"/api/v1/threads/{tid}/messages",
            json={"role": "ghost", "content": "x"},
            headers=headers,
        )
        assert r.status_code == 400

    def test_get_unknown_thread_404(self, server):
        client, headers, _ = server
        r = client.get("/api/v1/threads/does-not-exist", headers=headers)
        assert r.status_code == 404

    def test_delete_thread(self, server):
        client, headers, _ = server
        tid = client.post("/api/v1/threads", json={"title": ""}, headers=headers).json()["id"]
        r = client.delete(f"/api/v1/threads/{tid}", headers=headers)
        assert r.status_code == 200
        # Subsequent GET is 404
        r = client.get(f"/api/v1/threads/{tid}", headers=headers)
        assert r.status_code == 404

    def test_threads_are_user_scoped(self, server, tmp_path: Path):
        """Two different users see different thread lists."""
        client, headers_alice, _alice = server
        # Create a thread for alice
        client.post("/api/v1/threads", json={"title": "alice-only"}, headers=headers_alice)

        # Now create a second user and confirm they see nothing
        auth = AuthManager(storage_dir=tmp_path / "praxia" / "auth")
        bob, bob_key = auth.users.create(username="bob", role="member", password=None)
        headers_bob = {"X-API-Key": bob_key}

        r = client.get("/api/v1/threads", headers=headers_bob)
        assert r.status_code == 200
        assert r.json() == []

    def test_unauthenticated_request_is_rejected(self, server):
        client, _, _ = server
        r = client.get("/api/v1/threads")  # no header
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Agent run
# ---------------------------------------------------------------------------


def _mk_llm_response(text: str) -> LLMResponse:
    return LLMResponse(
        text=text,
        model="test-stub",
        usage={"prompt_tokens": 10, "completion_tokens": 8},
        raw={},
        tool_calls=[],
    )


class TestAgentRun:
    def test_run_without_thread_returns_text(self, server):
        client, headers, _ = server
        with patch("praxia.core.llm.LLM.complete", return_value=_mk_llm_response("hello world")):
            r = client.post(
                "/api/v1/agent/run",
                json={"prompt": "say hi"},
                headers=headers,
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["text"] == "hello world"
        assert body["stopped_reason"] == "completed"
        assert body["user_message_id"] is None
        assert body["assistant_message_id"] is None

    def test_run_empty_prompt_400(self, server):
        client, headers, _ = server
        r = client.post("/api/v1/agent/run", json={"prompt": ""}, headers=headers)
        assert r.status_code == 400

    def test_run_with_thread_appends_user_and_assistant(self, server):
        client, headers, _ = server
        tid = client.post("/api/v1/threads", json={"title": ""}, headers=headers).json()["id"]

        with patch("praxia.core.llm.LLM.complete", return_value=_mk_llm_response("done")):
            r = client.post(
                "/api/v1/agent/run",
                json={"prompt": "summarize", "thread_id": tid},
                headers=headers,
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["text"] == "done"
        assert body["user_message_id"]
        assert body["assistant_message_id"]
        assert body["user_message_id"] != body["assistant_message_id"]

        # Thread now has 2 messages, in order
        thread = client.get(f"/api/v1/threads/{tid}", headers=headers).json()
        assert len(thread["messages"]) == 2
        assert thread["messages"][0]["role"] == "user"
        assert thread["messages"][0]["content"] == "summarize"
        assert thread["messages"][1]["role"] == "assistant"
        assert thread["messages"][1]["content"] == "done"
        # Assistant metadata reflects the call
        assert thread["messages"][1]["metadata"]["model"] == "claude"
        assert thread["messages"][1]["metadata"]["verified"] is False

    def test_run_with_thread_missing_thread_404(self, server):
        client, headers, _ = server
        with patch("praxia.core.llm.LLM.complete", return_value=_mk_llm_response("x")):
            r = client.post(
                "/api/v1/agent/run",
                json={"prompt": "x", "thread_id": "phantom"},
                headers=headers,
            )
        # The user-message append fails with 404 before agent runs
        assert r.status_code == 404

    def test_verified_path_invokes_commander(self, server):
        client, headers, _ = server
        tid = client.post("/api/v1/threads", json={"title": ""}, headers=headers).json()["id"]

        # CommandedAgent does inner.run() for the draft + verifier.verify()
        # for grounding. The mock makes both the draft and the verifier's
        # JSON come from the same patched LLM.complete call.
        import json as _json
        verifier_reply = _json.dumps({
            "claims": [{"claim": "x", "score": 0.9, "supporting_ids": []}]
        })

        # Sequence: 1) inner draft, 2) verifier JSON
        responses = [_mk_llm_response("verified draft"), _mk_llm_response(verifier_reply)]
        with patch(
            "praxia.core.llm.LLM.complete",
            side_effect=responses,
        ):
            r = client.post(
                "/api/v1/agent/run",
                json={
                    "prompt": "what is x",
                    "thread_id": tid,
                    "verified": True,
                    "max_verify_rounds": 1,
                },
                headers=headers,
            )
        # With empty sources (no memory yet), commander should abstain ─
        # the underlying retriever finds nothing. That's still a valid
        # 200 response (it's a successful agent run, just with a
        # different stopped_reason).
        assert r.status_code == 200, r.text
        body = r.json()
        # When commander is invoked, verdict fields populate
        assert body["verdict_decision"] in {"accept", "redraft", "abstain"}
        assert body["rounds"] is not None
