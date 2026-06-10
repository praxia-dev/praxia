"""Coverage for the alpha27 LLM-driven query expansion fallback.

When ``embedding`` is unavailable (most commonly: Anthropic-only user
with no OpenAI/Ollama/Azure/Gemini key), Documents search has to
bridge the cross-language / synonym gap without a vector model.
``praxia.io.query_expansion.expand_query`` does this by asking the
active LLM to rewrite the query into 3-5 alternative phrasings; the
search router then scores each chunk against the max-scoring
variant.

These tests pin down four behaviours:
  * Variant dedupe + cap at _MAX_VARIANTS.
  * LRU cache hit skips the second LLM call entirely.
  * Empty / malformed LLM payload returns [] (caller falls back to
    the original query alone — no crash).
  * Integration: search_for_user with a non-embedding env + an llm
    finds an EN chunk from a JA query when expansion supplies the
    EN variant.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from praxia.io import query_expansion as qe


def _make_llm(response_text: str):
    """LLM stub that returns the given text from .complete()."""
    llm = MagicMock()
    llm.config = MagicMock()
    llm.config.model = "stub/test-model"
    resp = MagicMock()
    resp.text = response_text
    llm.complete = MagicMock(return_value=resp)
    return llm


@pytest.fixture(autouse=True)
def reset_cache():
    """Each test starts with an empty cache so order dependence isn't
    a thing. Without this, a test that warms the cache could mask a
    later test's mock-counting assertions."""
    qe._CACHE = qe._LRU(max_entries=1024)
    yield


class TestExpansionShape:
    def test_returns_dedup_capped_variants(self):
        llm = _make_llm(json.dumps({
            "variants": [
                "action items",
                "Action Items",          # case-dup → drop
                "TODOs",
                "次のアクション",
                "todos",                 # dup → drop
                "アクション",
                "next steps",
                "milestones",            # would be 6th → cap
            ],
        }))
        out = qe.expand_query("アクションアイテム", llm=llm)
        # Caps at 5, drops case-insensitive duplicates.
        assert len(out) <= 5
        assert "Action Items" not in out  # the dup form should be gone
        assert "action items" in out
        assert "次のアクション" in out

    def test_empty_payload_returns_empty(self):
        llm = _make_llm("")
        assert qe.expand_query("x", llm=llm) == []

    def test_malformed_payload_returns_empty(self):
        llm = _make_llm("not json at all")
        assert qe.expand_query("x", llm=llm) == []

    def test_empty_query_short_circuits_without_llm_call(self):
        llm = _make_llm(json.dumps({"variants": ["foo"]}))
        out = qe.expand_query("   ", llm=llm)
        assert out == []
        llm.complete.assert_not_called()


class TestLRUCache:
    def test_repeat_query_uses_cache(self):
        llm = _make_llm(json.dumps({"variants": ["alpha", "beta"]}))
        first = qe.expand_query("same query", llm=llm)
        second = qe.expand_query("same query", llm=llm)
        # Same result, but only one LLM call.
        assert first == second == ["alpha", "beta"]
        assert llm.complete.call_count == 1

    def test_different_model_is_a_different_cache_key(self):
        llm_a = _make_llm(json.dumps({"variants": ["a1"]}))
        llm_a.config.model = "claude-opus-4-7"
        llm_b = _make_llm(json.dumps({"variants": ["b1"]}))
        llm_b.config.model = "openai/gpt-5"
        out_a = qe.expand_query("same query", llm=llm_a)
        out_b = qe.expand_query("same query", llm=llm_b)
        # Each model gets its own cache entry — Claude's expansion
        # shouldn't be served to a GPT call and vice versa.
        assert out_a == ["a1"]
        assert out_b == ["b1"]


class TestLLMErrorPath:
    def test_llm_exception_returns_empty(self):
        llm = MagicMock()
        llm.config = MagicMock()
        llm.config.model = "stub/test"
        llm.complete = MagicMock(side_effect=RuntimeError("rate limit"))
        # Should NOT raise — search would otherwise crash mid-query.
        assert qe.expand_query("foo", llm=llm) == []


class TestSearchIntegration:
    """End-to-end: search_for_user with no embedding + an LLM should
    pick up an EN chunk via the JA query when the LLM supplies the
    EN translation as a variant."""

    def test_no_embedding_jp_query_finds_en_chunk(self, tmp_path: Path, monkeypatch):
        # Force the embeddings module to report unavailable so we
        # exercise the keyword-with-expansion path, not the cosine
        # path.
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("AZURE_API_KEY", raising=False)
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
        monkeypatch.delenv("HF_TOKEN", raising=False)
        monkeypatch.delenv("HUGGINGFACE_API_KEY", raising=False)
        monkeypatch.delenv("PRAXIA_EMBEDDING_MODEL", raising=False)

        # Stand up the minimum scaffold a search needs: a folder + a doc.
        from praxia.server.routers.documents import (
            Chunk, Document, Folder, _folder_dir, _folders_file,
            _docs_root, search_for_user,
        )
        import json as _json
        import uuid

        user_id = "alice"
        folder_id = uuid.uuid4().hex

        # Folder registration.
        _folders_file(tmp_path, user_id).parent.mkdir(parents=True, exist_ok=True)
        with _folders_file(tmp_path, user_id).open("w", encoding="utf-8") as f:
            _json.dump([Folder(
                id=folder_id,
                user_id=user_id,
                title="pdfs",
                path=str(tmp_path / "pdfs"),
                doc_count=1,
                enabled=True,
            ).model_dump()], f)

        # English-content chunk that should match a JA query
        # "アクションアイテム" via the LLM variant "action items".
        doc_dir = _folder_dir(tmp_path, user_id, folder_id)
        doc_dir.mkdir(parents=True, exist_ok=True)
        doc_id = uuid.uuid4().hex
        doc = Document(
            id=doc_id,
            folder_id=folder_id,
            relative_path="q3-notes.pdf",
            filename="q3-notes.pdf",
            size=60,
            mtime=0.0,
            content_hash="0" * 64,
            indexed_at=0.0,
            parser="pdf",
            chunks=[Chunk(
                index=0,
                text="Action items: ship feature X by Friday. Owner: Alex.",
                start=0,
                end=60,
            )],
        )
        (doc_dir / f"{doc_id}.json").write_text(
            _json.dumps(doc.model_dump()), encoding="utf-8",
        )

        # Inject an LLM that returns "action items" as a JA→EN
        # variant. The original query "アクションアイテム" alone would
        # never match the EN chunk via keyword scoring.
        llm = _make_llm(_json.dumps({
            "variants": ["action items", "TODOs", "next steps"],
        }))

        hits = search_for_user(
            tmp_path, user_id, "アクションアイテム",
            limit=5, llm=llm,
        )
        assert len(hits) == 1
        assert hits[0]["doc_id"] == doc_id
        assert "Action items" in hits[0]["text"]
        # And confirm the LLM was actually called (i.e. the expansion
        # path triggered, not some other fluke).
        llm.complete.assert_called_once()

    def test_no_embedding_no_llm_falls_back_to_keyword_only(
        self, tmp_path: Path, monkeypatch,
    ):
        """Backwards compat: without an LLM AND without embeddings, we
        should still behave the same as alpha22-26 (pure keyword)."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("AZURE_API_KEY", raising=False)
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
        monkeypatch.delenv("HF_TOKEN", raising=False)
        monkeypatch.delenv("HUGGINGFACE_API_KEY", raising=False)
        monkeypatch.delenv("PRAXIA_EMBEDDING_MODEL", raising=False)

        from praxia.server.routers.documents import (
            Chunk, Document, Folder, _folder_dir, _folders_file,
            search_for_user,
        )
        import json as _json
        import uuid

        user_id = "bob"
        folder_id = uuid.uuid4().hex
        _folders_file(tmp_path, user_id).parent.mkdir(parents=True, exist_ok=True)
        with _folders_file(tmp_path, user_id).open("w", encoding="utf-8") as f:
            _json.dump([Folder(
                id=folder_id,
                user_id=user_id,
                title="x",
                path=str(tmp_path / "x"),
                doc_count=1,
                enabled=True,
            ).model_dump()], f)

        doc_dir = _folder_dir(tmp_path, user_id, folder_id)
        doc_dir.mkdir(parents=True, exist_ok=True)
        doc_id = uuid.uuid4().hex
        doc = Document(
            id=doc_id,
            folder_id=folder_id,
            relative_path="a.txt",
            filename="a.txt",
            size=11,
            mtime=0.0,
            content_hash="0" * 64,
            indexed_at=0.0,
            parser="txt",
            chunks=[Chunk(
                index=0,
                text="hello world",
                start=0,
                end=11,
            )],
        )
        (doc_dir / f"{doc_id}.json").write_text(
            _json.dumps(doc.model_dump()), encoding="utf-8",
        )

        # No llm passed — must still find the chunk via the literal
        # keyword match.
        hits = search_for_user(tmp_path, user_id, "hello", limit=5)
        assert len(hits) == 1
