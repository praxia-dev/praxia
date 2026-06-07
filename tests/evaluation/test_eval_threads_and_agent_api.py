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
        # Sources field must be present (may be empty for a no-memory
        # fixture) so the desktop UI can rely on its shape unconditionally.
        # The Sources panel in the desktop renders nothing when this list
        # is empty, so an empty list is fine — but the KEY must exist.
        assert "sources" in body, "verified responses must include sources field"
        assert isinstance(body["sources"], list)

    def test_verified_response_serialises_source_metadata(self, server):
        """End-to-end check that retrieved sources surface with their
        metadata (id, kind, text_preview, metadata.relative_path / score)
        in the API response. Critical for the desktop Sources panel —
        without this the user only sees [D#0] without knowing what
        document it came from."""
        client, headers, _ = server
        import json as _json
        from unittest.mock import patch

        # Stub the commander retriever to inject a synthetic local_document
        # source so the response can include something even without a
        # real Documents folder ingested. The retriever is a callable
        # the commander invokes during run() to populate cresult.sources.
        from praxia.agent.verifier import Source

        fake_sources = [
            Source(
                id="D#0",
                text="The quarterly review identified three key risks ...",
                kind="local_document",
                metadata={
                    "doc_id": "doc-abc",
                    "folder_id": "fold-xyz",
                    "relative_path": "contracts/2024/acme-msa.pdf",
                    "chunk_index": 2,
                    "score": 0.87,
                },
            ),
        ]

        verifier_reply = _json.dumps({
            "claims": [{
                "claim": "Three key risks were identified.",
                "score": 0.9,
                "supporting_ids": ["D#0"],
            }]
        })
        responses = [_mk_llm_response("Three key risks were identified."),
                     _mk_llm_response(verifier_reply)]

        with patch(
            "praxia.agent.commander.DefaultMemoryRetriever.__call__",
            return_value=fake_sources,
        ), patch(
            "praxia.core.llm.LLM.complete",
            side_effect=responses,
        ):
            r = client.post(
                "/api/v1/agent/run",
                json={
                    "prompt": "what risks were identified",
                    "verified": True,
                    "max_verify_rounds": 1,
                },
                headers=headers,
            )

        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body["sources"], list)
        assert len(body["sources"]) == 1, body["sources"]
        s = body["sources"][0]
        assert s["id"] == "D#0"
        assert s["kind"] == "local_document"
        assert s["text_preview"].startswith("The quarterly review")
        assert s["text_truncated"] is False
        assert s["metadata"]["relative_path"] == "contracts/2024/acme-msa.pdf"
        assert s["metadata"]["chunk_index"] == 2
        assert s["metadata"]["score"] == 0.87
        # The cited ID must also appear in citations so the UI can
        # cross-reference and visually distinguish cited vs uncited.
        assert "D#0" in body["citations"]


# ---------------------------------------------------------------------------
# Workspace-scoped file tools (/agent/run + workspace_root)
# ---------------------------------------------------------------------------


class TestWorkspaceFileTools:
    """When `workspace_root` is in the request, the agent must register
    the file_tools and be able to touch files only inside that path.
    These tests exercise the wiring end-to-end through the HTTP route.
    """

    def test_workspace_tools_register_when_root_supplied(self, server, tmp_path: Path):
        """A run with workspace_root should make the inner agent's tools
        include read_file / write_file / etc. We assert via a tool_call
        the LLM emits — the route serialises matching tool calls back to
        the response body."""
        client, headers, _ = server
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / "hello.txt").write_text("hi from workspace", encoding="utf-8")

        from unittest.mock import patch
        from praxia.core.llm import LLMResponse

        # Round 1: the LLM "decides" to call read_file. Round 2: it
        # produces a final_answer with the content it just read.
        tool_call = {
            "id": "call_1",
            "name": "read_file",
            "arguments": '{"path": "hello.txt"}',
        }
        final_call = {
            "id": "call_2",
            "name": "final_answer",
            "arguments": '{"answer": "the file says: hi from workspace"}',
        }
        responses = [
            LLMResponse(text="", model="stub", usage={}, raw={}, tool_calls=[tool_call]),
            LLMResponse(text="", model="stub", usage={}, raw={}, tool_calls=[final_call]),
        ]
        with patch("praxia.core.llm.LLM.complete", side_effect=responses):
            r = client.post(
                "/api/v1/agent/run",
                json={
                    "prompt": "read hello.txt",
                    "workspace_root": str(ws),
                },
                headers=headers,
            )
        assert r.status_code == 200, r.text
        body = r.json()
        tool_names = [tc["name"] for tc in body["tool_calls"]]
        assert "read_file" in tool_names
        assert "hi from workspace" in body["text"]

    def test_no_workspace_root_no_file_tools(self, server):
        """Without workspace_root, the file tools must NOT be registered
        — calling read_file should error from the agent's "unknown tool"
        branch."""
        client, headers, _ = server

        from unittest.mock import patch
        from praxia.core.llm import LLMResponse

        bad_call = {
            "id": "call_1",
            "name": "read_file",
            "arguments": '{"path": "hello.txt"}',
        }
        final_call = {
            "id": "call_2",
            "name": "final_answer",
            "arguments": '{"answer": "tried"}',
        }
        responses = [
            LLMResponse(text="", model="stub", usage={}, raw={}, tool_calls=[bad_call]),
            LLMResponse(text="", model="stub", usage={}, raw={}, tool_calls=[final_call]),
        ]
        with patch("praxia.core.llm.LLM.complete", side_effect=responses):
            r = client.post(
                "/api/v1/agent/run",
                json={"prompt": "read"},
                headers=headers,
            )
        assert r.status_code == 200, r.text
        body = r.json()
        # The agent recorded the tool call but it failed (ok=False).
        rf = next((tc for tc in body["tool_calls"] if tc["name"] == "read_file"), None)
        assert rf is not None
        assert rf["ok"] is False  # unknown tool when workspace_root is absent

    def test_bad_workspace_root_returns_400(self, server, tmp_path: Path):
        """workspace_root pointing at a file (not a directory) is a
        client bug — surface 400 instead of letting the agent loop blow
        up later."""
        client, headers, _ = server
        f = tmp_path / "not-a-dir.txt"
        f.write_text("nope")
        r = client.post(
            "/api/v1/agent/run",
            json={"prompt": "hi", "workspace_root": str(f)},
            headers=headers,
        )
        assert r.status_code == 400

    def test_write_queues_pending_does_not_touch_disk(self, server, tmp_path: Path):
        """End-to-end safety check: when the LLM asks to write a file,
        the file must NOT exist on disk yet — the op should sit in the
        pending_file_operations array waiting for the user."""
        client, headers, _ = server
        ws = tmp_path / "ws"
        ws.mkdir()

        from unittest.mock import patch
        from praxia.core.llm import LLMResponse

        write_call = {
            "id": "call_1",
            "name": "write_file",
            "arguments": '{"path": "new.py", "content": "print(\\"hi\\")"}',
        }
        final_call = {
            "id": "call_2",
            "name": "final_answer",
            "arguments": '{"answer": "Queued write of new.py for your approval."}',
        }
        responses = [
            LLMResponse(text="", model="stub", usage={}, raw={}, tool_calls=[write_call]),
            LLMResponse(text="", model="stub", usage={}, raw={}, tool_calls=[final_call]),
        ]
        with patch("praxia.core.llm.LLM.complete", side_effect=responses):
            r = client.post(
                "/api/v1/agent/run",
                json={"prompt": "create new.py", "workspace_root": str(ws)},
                headers=headers,
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert not (ws / "new.py").exists()  # ← critical: NOT written yet
        assert body["pending_file_operations"]
        op = body["pending_file_operations"][0]
        assert op["op"] == "write_file"
        assert op["path"] == "new.py"
        assert op["content"] == 'print("hi")'

    def test_apply_endpoint_writes_approved_op(self, server, tmp_path: Path):
        """After the user approves an op, /workspace/apply executes it."""
        client, headers, _ = server
        ws = tmp_path / "ws"
        ws.mkdir()

        r = client.post(
            "/api/v1/workspace/apply",
            json={
                "workspace_root": str(ws),
                "op": {"op": "write_file", "path": "ok.txt", "content": "approved"},
            },
            headers=headers,
        )
        assert r.status_code == 200, r.text
        assert (ws / "ok.txt").read_text() == "approved"

    def test_apply_endpoint_rejects_escape(self, server, tmp_path: Path):
        """If the frontend tries to apply a path that escapes the
        workspace, the server must refuse — defence in depth."""
        client, headers, _ = server
        ws = tmp_path / "ws"
        ws.mkdir()
        r = client.post(
            "/api/v1/workspace/apply",
            json={
                "workspace_root": str(ws),
                "op": {"op": "write_file", "path": "../sneaky.txt", "content": "x"},
            },
            headers=headers,
        )
        assert r.status_code == 400
        assert not (ws.parent / "sneaky.txt").exists()
