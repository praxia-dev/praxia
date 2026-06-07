"""Integration tests for /documents/* endpoints + retriever wiring.

Covers:
- folder CRUD
- multipart upload of plain text / json files (no optional parser deps needed)
- duplicate-content short-circuit (status="unchanged")
- search ranking + per-user scoping
- chunk_text() pure-function behaviour
- DefaultMemoryRetriever picking up documents through the search callable
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

# Skip the whole module if FastAPI isn't installed
fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from praxia.auth.manager import AuthManager  # noqa: E402
from praxia.server.app import create_app  # noqa: E402
from praxia.server.routers.documents import (  # noqa: E402
    chunk_text,
    score_chunk,
    search_for_user,
    _tokenize,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def server(tmp_path: Path):
    storage = tmp_path / "praxia"
    auth = AuthManager(storage_dir=storage / "auth")
    user, api_key = auth.users.create(username="alice", role="member", password=None)
    app = create_app(storage_dir=storage)
    client = TestClient(app)
    return client, {"X-API-Key": api_key}, user, storage


# ---------------------------------------------------------------------------
# chunk_text() — pure logic, no server needed
# ---------------------------------------------------------------------------


class TestChunkText:
    def test_short_text_one_chunk(self):
        text = "Hello, this is a short paragraph."
        chunks = chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0].text == text
        assert chunks[0].index == 0

    def test_empty_text_returns_empty(self):
        assert chunk_text("") == []
        assert chunk_text("   \n  ") == []

    def test_short_paragraphs_merge(self):
        text = "Para one is short.\n\nPara two is also short.\n\nThird tiny one."
        chunks = chunk_text(text)
        # Three small paragraphs fit comfortably under target → one chunk
        assert len(chunks) == 1
        assert "Para one" in chunks[0].text
        assert "Third tiny" in chunks[0].text

    def test_long_paragraph_splits_by_sentence(self):
        # 50 sentences × ~40 chars each = ~2000 chars, well above target
        sentences = [f"Sentence number {i} is sufficiently long to count." for i in range(50)]
        text = " ".join(sentences)
        chunks = chunk_text(text)
        assert len(chunks) >= 2, "Long paragraph should split"
        # All sentences should appear somewhere
        joined = " ".join(c.text for c in chunks)
        assert "Sentence number 0" in joined
        assert "Sentence number 49" in joined
        # Each chunk should have a reasonable, not absurd, size
        for c in chunks:
            assert len(c.text) <= 2500

    def test_chunks_get_sequential_indices(self):
        text = " ".join([f"Sentence {i}." for i in range(80)]) * 3
        chunks = chunk_text(text)
        assert [c.index for c in chunks] == list(range(len(chunks)))


# ---------------------------------------------------------------------------
# scoring helpers
# ---------------------------------------------------------------------------


class TestScoring:
    def test_no_query_tokens_zero_score(self):
        assert score_chunk([], "anything", ["anything"]) == 0.0

    def test_score_higher_for_exact_match(self):
        q = ["compliance"]
        short = "Compliance is critical."
        # Long chunk that mentions "compliance" exactly once, buried in
        # lots of unrelated tokens → length penalty should dominate
        filler = " ".join(f"unrelated_word_{i}" for i in range(400))
        long_ = f"{filler} compliance {filler}"
        s_short = score_chunk(q, short.lower(), _tokenize(short))
        s_long = score_chunk(q, long_.lower(), _tokenize(long_))
        assert s_short > 0 and s_long > 0
        # Same occurrence count, but the short chunk wins on length penalty
        assert s_short > s_long

    def test_partial_query_coverage_scored_lower(self):
        # "audit log" has 2 tokens; full coverage > partial
        q = ["audit", "log"]
        full = "The audit log records every action."
        partial = "The audit was thorough."  # missing "log"
        s_full = score_chunk(q, full.lower(), _tokenize(full))
        s_partial = score_chunk(q, partial.lower(), _tokenize(partial))
        assert s_full > s_partial > 0


# ---------------------------------------------------------------------------
# Folder CRUD
# ---------------------------------------------------------------------------


class TestFolderCrud:
    def test_create_folder_returns_id(self, server):
        client, hdr, _u, _ = server
        r = client.post("/api/v1/documents/folder",
                        json={"path": "/home/alice/Docs", "title": "Docs"}, headers=hdr)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["id"]
        assert b["title"] == "Docs"
        assert b["path"] == "/home/alice/Docs"
        assert b["doc_count"] == 0
        assert b["enabled"] is True

    def test_create_folder_idempotent_on_path(self, server):
        """Re-registering the same path returns the same folder."""
        client, hdr, _u, _ = server
        r1 = client.post("/api/v1/documents/folder",
                         json={"path": "/x/y", "title": "first"}, headers=hdr)
        r2 = client.post("/api/v1/documents/folder",
                         json={"path": "/x/y", "title": "different"}, headers=hdr)
        assert r1.json()["id"] == r2.json()["id"]
        # Title from the first registration wins (idempotent)
        assert r1.json()["title"] == "first"

    def test_create_requires_path(self, server):
        client, hdr, _u, _ = server
        r = client.post("/api/v1/documents/folder",
                        json={"path": "  "}, headers=hdr)
        assert r.status_code == 400

    def test_list_folders_returns_user_only(self, server, tmp_path: Path):
        client, hdr_alice, _alice, storage = server
        client.post("/api/v1/documents/folder",
                    json={"path": "/x"}, headers=hdr_alice)

        # Make a second user
        auth = AuthManager(storage_dir=storage / "auth")
        bob, bob_key = auth.users.create(username="bob", role="member", password=None)
        hdr_bob = {"X-API-Key": bob_key}

        r = client.get("/api/v1/documents/folders", headers=hdr_bob)
        assert r.status_code == 200
        assert r.json() == []

    def test_delete_folder_removes_index(self, server):
        client, hdr, _u, _ = server
        fid = client.post("/api/v1/documents/folder",
                          json={"path": "/x"}, headers=hdr).json()["id"]
        r = client.delete(f"/api/v1/documents/folder/{fid}", headers=hdr)
        assert r.status_code == 200
        # Subsequent GET is 404
        assert client.get(f"/api/v1/documents/folder/{fid}", headers=hdr).status_code == 404

    def test_unknown_folder_get_404(self, server):
        client, hdr, _u, _ = server
        assert client.get("/api/v1/documents/folder/no-such", headers=hdr).status_code == 404


# ---------------------------------------------------------------------------
# Upload + dedup
# ---------------------------------------------------------------------------


class TestUpload:
    @staticmethod
    def _upload(client, hdr, fid, text: str, rel_path: str = "notes.txt"):
        return client.post(
            f"/api/v1/documents/folder/{fid}/upload",
            headers=hdr,
            files={"file": (rel_path.split("/")[-1], io.BytesIO(text.encode("utf-8")), "text/plain")},
            data={"relative_path": rel_path, "mtime": 0.0},
        )

    def test_upload_text_file_creates_doc(self, server):
        client, hdr, _u, _ = server
        fid = client.post("/api/v1/documents/folder", json={"path": "/x"}, headers=hdr).json()["id"]
        r = self._upload(client, hdr, fid, "Hello world, this is a small note.", "notes.txt")
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["status"] == "indexed"
        assert b["chunks"] >= 1
        assert b["doc_id"]

    def test_unchanged_short_circuit(self, server):
        client, hdr, _u, _ = server
        fid = client.post("/api/v1/documents/folder", json={"path": "/x"}, headers=hdr).json()["id"]
        first = self._upload(client, hdr, fid, "Same content", "a.txt").json()
        second = self._upload(client, hdr, fid, "Same content", "a.txt").json()
        assert first["doc_id"] == second["doc_id"]
        assert second["status"] == "unchanged"

    def test_delete_file_by_path_removes_doc(self, server):
        # Phase 2-D: companion to upload — folder watcher uses this to
        # drop docs whose source files have vanished from disk.
        client, hdr, _u, _ = server
        fid = client.post("/api/v1/documents/folder", json={"path": "/x"}, headers=hdr).json()["id"]
        up = self._upload(client, hdr, fid, "About to vanish", "vanish.txt").json()
        assert up["status"] == "indexed"
        # File exists in the listing.
        before = client.get(f"/api/v1/documents/folder/{fid}", headers=hdr).json()
        assert any(d["relative_path"] == "vanish.txt" for d in before.get("documents", []))

        r = client.delete(
            f"/api/v1/documents/folder/{fid}/file?relative_path=vanish.txt",
            headers=hdr,
        )
        assert r.status_code == 200 and r.json()["deleted"] is True
        after = client.get(f"/api/v1/documents/folder/{fid}", headers=hdr).json()
        assert not any(d["relative_path"] == "vanish.txt" for d in after.get("documents", []))

        # Idempotent — second delete returns deleted=false, not 404.
        r2 = client.delete(
            f"/api/v1/documents/folder/{fid}/file?relative_path=vanish.txt",
            headers=hdr,
        )
        assert r2.status_code == 200 and r2.json()["deleted"] is False

    def test_changed_content_replaces_indexing(self, server):
        client, hdr, _u, _ = server
        fid = client.post("/api/v1/documents/folder", json={"path": "/x"}, headers=hdr).json()["id"]
        first = self._upload(client, hdr, fid, "Old content here.", "a.txt").json()
        second = self._upload(client, hdr, fid, "New content with more words here.", "a.txt").json()
        # Same doc_id (same relative_path) but re-indexed
        assert first["doc_id"] == second["doc_id"]
        assert second["status"] == "indexed"

    def test_empty_file_skipped(self, server):
        client, hdr, _u, _ = server
        fid = client.post("/api/v1/documents/folder", json={"path": "/x"}, headers=hdr).json()["id"]
        r = self._upload(client, hdr, fid, "", "empty.txt").json()
        assert r["status"] == "skipped"
        assert "empty" in r["reason"].lower()

    def test_unsupported_extension_skipped(self, server):
        client, hdr, _u, _ = server
        fid = client.post("/api/v1/documents/folder", json={"path": "/x"}, headers=hdr).json()["id"]
        r = self._upload(client, hdr, fid, "binary garbage", "binary.exe").json()
        assert r["status"] == "skipped"
        assert "parser" in r["reason"].lower()

    def test_folder_doc_count_increments(self, server):
        client, hdr, _u, _ = server
        fid = client.post("/api/v1/documents/folder", json={"path": "/x"}, headers=hdr).json()["id"]
        self._upload(client, hdr, fid, "Doc A content.", "a.txt")
        self._upload(client, hdr, fid, "Doc B content.", "b.txt")
        r = client.get(f"/api/v1/documents/folder/{fid}", headers=hdr).json()
        assert r["doc_count"] == 2
        assert len(r["documents"]) == 2

    def test_json_file_parsed(self, server):
        client, hdr, _u, _ = server
        fid = client.post("/api/v1/documents/folder", json={"path": "/x"}, headers=hdr).json()["id"]
        payload = json.dumps({"customer": "Acme", "topic": "Q3 review"})
        r = self._upload(client, hdr, fid, payload, "report.json").json()
        assert r["status"] == "indexed"
        assert r["chunks"] >= 1


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class TestSearch:
    def _seed(self, client, hdr):
        fid = client.post("/api/v1/documents/folder", json={"path": "/x"}, headers=hdr).json()["id"]
        client.post(
            f"/api/v1/documents/folder/{fid}/upload",
            headers=hdr,
            files={"file": ("comp.txt", io.BytesIO(
                b"This document covers SOC2 compliance, audit logs, and access control."
            ), "text/plain")},
            data={"relative_path": "comp.txt"},
        )
        client.post(
            f"/api/v1/documents/folder/{fid}/upload",
            headers=hdr,
            files={"file": ("sales.txt", io.BytesIO(
                b"Q3 sales pipeline: Acme decided ROI is top priority for procurement."
            ), "text/plain")},
            data={"relative_path": "sales.txt"},
        )
        return fid

    def test_query_returns_matching_chunks(self, server):
        client, hdr, _u, _ = server
        self._seed(client, hdr)
        r = client.post("/api/v1/documents/search",
                        json={"query": "audit compliance", "limit": 5},
                        headers=hdr)
        assert r.status_code == 200, r.text
        hits = r.json()
        assert len(hits) >= 1
        assert any("compliance" in h["text"].lower() for h in hits)
        # Top hit should be the comp.txt chunk
        assert hits[0]["relative_path"] == "comp.txt"

    def test_empty_query_returns_empty(self, server):
        client, hdr, _u, _ = server
        self._seed(client, hdr)
        r = client.post("/api/v1/documents/search",
                        json={"query": ""}, headers=hdr)
        assert r.status_code == 200
        assert r.json() == []

    def test_no_match_returns_empty(self, server):
        client, hdr, _u, _ = server
        self._seed(client, hdr)
        r = client.post("/api/v1/documents/search",
                        json={"query": "kubernetes orchestration etcd raft"},
                        headers=hdr)
        assert r.status_code == 200
        assert r.json() == []

    def test_user_scoped_search(self, server, tmp_path: Path):
        client, hdr_alice, _alice, storage = server
        self._seed(client, hdr_alice)

        # bob shouldn't see alice's docs
        auth = AuthManager(storage_dir=storage / "auth")
        bob, bob_key = auth.users.create(username="bob", role="member", password=None)
        hdr_bob = {"X-API-Key": bob_key}
        r = client.post("/api/v1/documents/search",
                        json={"query": "audit compliance"}, headers=hdr_bob)
        assert r.status_code == 200
        assert r.json() == []

    def test_folder_filter_narrows_search(self, server):
        client, hdr, _u, _ = server
        fid = self._seed(client, hdr)
        other = client.post("/api/v1/documents/folder",
                            json={"path": "/y"}, headers=hdr).json()["id"]
        # Filter to "other" — no docs there, expect 0 hits
        r = client.post("/api/v1/documents/search",
                        json={"query": "audit", "folder_ids": [other]}, headers=hdr).json()
        assert r == []
        # Filter to "fid" — gets the original hits back
        r = client.post("/api/v1/documents/search",
                        json={"query": "audit", "folder_ids": [fid]}, headers=hdr).json()
        assert any("audit" in h["text"].lower() for h in r)


# ---------------------------------------------------------------------------
# search_for_user() helper — module-level, used by the retriever
# ---------------------------------------------------------------------------


class TestSearchForUser:
    def test_search_for_user_returns_dicts(self, server):
        client, hdr, user, storage = server
        fid = client.post("/api/v1/documents/folder",
                          json={"path": "/x"}, headers=hdr).json()["id"]
        client.post(
            f"/api/v1/documents/folder/{fid}/upload",
            headers=hdr,
            files={"file": ("a.txt", io.BytesIO(b"Compliance is a key concern."), "text/plain")},
            data={"relative_path": "a.txt"},
        )
        hits = search_for_user(storage, user.id, "compliance", limit=5)
        assert len(hits) >= 1
        assert "text" in hits[0]
        assert "doc_id" in hits[0]
        assert "relative_path" in hits[0]
        assert "score" in hits[0]

    def test_search_for_user_empty_when_no_folders(self, server):
        _client, _hdr, user, storage = server
        assert search_for_user(storage, user.id, "anything", limit=5) == []

    def test_search_for_user_respects_disabled_folder(self, server, tmp_path: Path):
        """A folder with enabled=False should be skipped by default."""
        client, hdr, user, storage = server
        fid = client.post("/api/v1/documents/folder",
                          json={"path": "/x"}, headers=hdr).json()["id"]
        client.post(
            f"/api/v1/documents/folder/{fid}/upload",
            headers=hdr,
            files={"file": ("a.txt", io.BytesIO(b"Audit topic"), "text/plain")},
            data={"relative_path": "a.txt"},
        )
        # Directly flip enabled=False on the persisted folder file
        from praxia.server.routers.documents import _folders_file, load_user_folders
        folders = load_user_folders(storage, user.id)
        folders[0].enabled = False
        _folders_file(storage, user.id).write_text(
            json.dumps([f.model_dump() for f in folders], ensure_ascii=False),
            encoding="utf-8",
        )
        # Default search (no folder_ids) → skipped
        assert search_for_user(storage, user.id, "audit") == []
        # Explicit folder_ids → returned anyway (admin / debug path)
        hits = search_for_user(storage, user.id, "audit", folder_ids=[fid])
        assert len(hits) >= 1


# ---------------------------------------------------------------------------
# Retriever wiring — documents surface to CommandedAgent
# ---------------------------------------------------------------------------


class TestRetrieverIntegration:
    def test_default_retriever_picks_up_docs(self, server):
        from praxia.agent.commander import DefaultMemoryRetriever
        from praxia.server.routers.documents import search_for_user as _sfu

        client, hdr, user, storage = server
        fid = client.post("/api/v1/documents/folder",
                          json={"path": "/x"}, headers=hdr).json()["id"]
        client.post(
            f"/api/v1/documents/folder/{fid}/upload",
            headers=hdr,
            files={"file": ("a.txt", io.BytesIO(
                b"The SOC2 audit log retention policy must be at least 7 years."
            ), "text/plain")},
            data={"relative_path": "policies/audit.txt"},
        )

        # Build a retriever wired only to the documents store
        retriever = DefaultMemoryRetriever(
            personal=None, shared=None, frozen=None,
            documents_search=lambda q: _sfu(storage, user.id, q, limit=5),
        )
        sources = retriever("audit retention policy")
        assert len(sources) >= 1, "documents should surface as Sources"
        # IDs use the D# prefix
        assert sources[0].id.startswith("D#")
        # Kind is local_document
        assert sources[0].kind == "local_document"
        # Metadata carries the path
        assert sources[0].metadata.get("relative_path") == "policies/audit.txt"


# ---------------------------------------------------------------------------
# search_documents tool — bare AutonomousAgent reach into documents
# ---------------------------------------------------------------------------


class TestSearchDocumentsTool:
    """The bare AutonomousAgent (no CommandedAgent verifier wrap) needs
    direct access to user-ingested documents via a tool. Without this,
    the Documents tab "works" (folder is ingested, search endpoint
    returns hits) but a normal chat never reaches into them.
    """

    def test_tool_is_registered_by_default(self):
        from praxia.agent.tools import builtin_tools
        tools = builtin_tools()
        assert "search_documents" in tools
        sd = tools["search_documents"]
        # Schema is litellm-callable
        s = sd.to_litellm_schema()
        assert s["function"]["name"] == "search_documents"
        assert "query" in s["function"]["parameters"]["properties"]

    def test_tool_returns_hits_from_user_documents(self, server):
        """End-to-end: upload a doc → call search_documents handler →
        it should find the chunk just uploaded."""
        from praxia.agent.tools import builtin_tools

        client, hdr, user, storage = server
        fid = client.post("/api/v1/documents/folder",
                          json={"path": "/x"}, headers=hdr).json()["id"]
        client.post(
            f"/api/v1/documents/folder/{fid}/upload",
            headers=hdr,
            files={"file": ("note.txt", io.BytesIO(
                b"Customer renewal terms require 30 day written notice."
            ), "text/plain")},
            data={"relative_path": "note.txt"},
        )

        # Minimal agent stub — search_documents only needs user_id +
        # memory_dir off the agent.
        from dataclasses import dataclass

        @dataclass
        class _StubAgent:
            user_id: str
            memory_dir: str

        agent = _StubAgent(user_id=user.id, memory_dir=str(storage))
        handler = builtin_tools()["search_documents"].handler
        result = handler(agent, query="customer renewal", limit=5)
        assert result["count"] >= 1
        first = result["hits"][0]
        assert "renewal" in first["text"].lower()
        assert first["relative_path"] == "note.txt"

    def test_path_prefix_filter(self, server):
        """When the user says 'search the contracts/2024 folder',
        the agent calls search_documents with path_prefix and only
        gets hits whose relative_path starts with that prefix."""
        from praxia.agent.tools import builtin_tools
        from dataclasses import dataclass

        client, hdr, user, storage = server
        fid = client.post("/api/v1/documents/folder",
                          json={"path": "/x"}, headers=hdr).json()["id"]
        # Two files in different subfolders, both with the keyword.
        for sub in ("contracts/2024/q1.txt", "policies/security.txt"):
            client.post(
                f"/api/v1/documents/folder/{fid}/upload",
                headers=hdr,
                files={"file": (sub.split("/")[-1], io.BytesIO(
                    b"audit retention is 7 years"
                ), "text/plain")},
                data={"relative_path": sub},
            )

        @dataclass
        class _StubAgent:
            user_id: str
            memory_dir: str

        agent = _StubAgent(user_id=user.id, memory_dir=str(storage))
        handler = builtin_tools()["search_documents"].handler

        # Without prefix: both files match
        all_hits = handler(agent, query="audit retention")
        paths = {h["relative_path"] for h in all_hits["hits"]}
        assert "contracts/2024/q1.txt" in paths
        assert "policies/security.txt" in paths

        # With prefix: only contracts/2024/ matches
        narrowed = handler(agent, query="audit retention", path_prefix="contracts/2024")
        paths = {h["relative_path"] for h in narrowed["hits"]}
        assert "contracts/2024/q1.txt" in paths
        assert "policies/security.txt" not in paths

    def test_list_document_folders_tool(self, server):
        from praxia.agent.tools import builtin_tools
        from dataclasses import dataclass

        client, hdr, user, storage = server
        client.post("/api/v1/documents/folder",
                    json={"path": "/home/alice/contracts", "title": "Contracts"},
                    headers=hdr)
        client.post("/api/v1/documents/folder",
                    json={"path": "/home/alice/notes", "title": "Notes"},
                    headers=hdr)

        @dataclass
        class _StubAgent:
            user_id: str
            memory_dir: str

        agent = _StubAgent(user_id=user.id, memory_dir=str(storage))
        r = builtin_tools()["list_document_folders"].handler(agent)
        assert r["count"] == 2
        titles = {f["title"] for f in r["folders"]}
        assert titles == {"Contracts", "Notes"}

    def test_tool_isolates_by_user(self, server, tmp_path):
        """search_documents must scope to agent.user_id — Bob can't
        see Alice's docs even though they share the same storage."""
        from praxia.agent.tools import builtin_tools
        from dataclasses import dataclass

        client, hdr_alice, alice, storage = server
        fid = client.post("/api/v1/documents/folder",
                          json={"path": "/x"}, headers=hdr_alice).json()["id"]
        client.post(
            f"/api/v1/documents/folder/{fid}/upload",
            headers=hdr_alice,
            files={"file": ("a.txt", io.BytesIO(b"alice private notes"), "text/plain")},
            data={"relative_path": "a.txt"},
        )

        auth = AuthManager(storage_dir=storage / "auth")
        bob, _ = auth.users.create(username="bob", role="member", password=None)

        @dataclass
        class _StubAgent:
            user_id: str
            memory_dir: str

        handler = builtin_tools()["search_documents"].handler
        bob_result = handler(
            _StubAgent(user_id=bob.id, memory_dir=str(storage)),
            query="private notes",
        )
        assert bob_result["count"] == 0
