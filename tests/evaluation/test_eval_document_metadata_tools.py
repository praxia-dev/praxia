"""Coverage for the alpha28 metadata + full-read tools.

The motivating bug: a user asked "show me the latest proposal" and
the agent kept asking clarifying questions because:
  - list_files_in_folder didn't expose mtime, so the LLM had no way
    to identify "latest"
  - there was no tool to fetch a document's full text once identified

This file pins down the fix:
  - list_files_in_folder reports mtime + mtime_iso
  - sort_by='mtime_desc' + limit=1 yields the newest file
  - across-all-folders mode (no folder id/title)
  - read_document returns full concatenated chunks given a doc_id
  - read_document truncates at max_chars and flags it
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from praxia.agent.tools import _list_files_in_folder, _read_document


def _make_folder_and_docs(tmp_path: Path, user_id: str, folder_title: str,
                         files: list[tuple[str, float, str]]) -> str:
    """Build the on-disk layout the document router uses.

    `files` is a list of (relative_path, mtime, body_text) tuples. Each
    becomes a Document with one Chunk so a downstream read_document
    call returns the body verbatim. Returns the folder_id used.
    """
    from praxia.server.routers.documents import (
        Chunk, Document, Folder, _folder_dir, _folders_file,
    )

    folder_id = uuid.uuid4().hex
    _folders_file(tmp_path, user_id).parent.mkdir(parents=True, exist_ok=True)
    with _folders_file(tmp_path, user_id).open("w", encoding="utf-8") as f:
        json.dump([Folder(
            id=folder_id,
            user_id=user_id,
            title=folder_title,
            path=str(tmp_path / folder_title),
            doc_count=len(files),
            enabled=True,
        ).model_dump()], f)

    doc_dir = _folder_dir(tmp_path, user_id, folder_id)
    doc_dir.mkdir(parents=True, exist_ok=True)
    for rel, mt, body in files:
        doc_id = uuid.uuid4().hex
        doc = Document(
            id=doc_id,
            folder_id=folder_id,
            relative_path=rel,
            filename=rel.split("/")[-1],
            size=len(body.encode("utf-8")),
            mtime=mt,
            content_hash="0" * 64,
            indexed_at=mt,
            parser=(rel.rsplit(".", 1)[1] if "." in rel else "txt"),
            chunks=[Chunk(index=0, text=body, start=0, end=len(body))],
        )
        (doc_dir / f"{doc_id}.json").write_text(
            json.dumps(doc.model_dump()), encoding="utf-8",
        )
    return folder_id


def _agent(tmp_path: Path, user_id: str = "alice") -> MagicMock:
    a = MagicMock()
    a.user_id = user_id
    a.role = "member"
    a.memory_dir = str(tmp_path)
    return a


# ─── list_files_in_folder ──────────────────────────────────────────


class TestListFilesEnhanced:
    def test_mtime_and_iso_in_response(self, tmp_path: Path):
        _make_folder_and_docs(tmp_path, "alice", "pdfs", [
            ("a.pdf", 1735689600.0, "alpha"),   # 2025-01-01
            ("b.pdf", 1735776000.0, "beta"),    # 2025-01-02
        ])
        res = _list_files_in_folder(_agent(tmp_path), folder_title="pdfs")
        assert res["count"] == 2
        for f in res["files"]:
            assert "mtime" in f
            assert "mtime_iso" in f
            # ISO string ends with "Z" so it's unambiguous UTC.
            assert f["mtime_iso"].endswith("Z")

    def test_sort_by_mtime_desc(self, tmp_path: Path):
        _make_folder_and_docs(tmp_path, "alice", "pdfs", [
            ("old.pdf", 100.0, "old body"),
            ("new.pdf", 999.0, "new body"),
            ("mid.pdf", 500.0, "mid body"),
        ])
        res = _list_files_in_folder(
            _agent(tmp_path), folder_title="pdfs",
            sort_by="mtime_desc",
        )
        order = [f["relative_path"] for f in res["files"]]
        assert order == ["new.pdf", "mid.pdf", "old.pdf"]

    def test_latest_one_via_sort_and_limit(self, tmp_path: Path):
        """The headline alpha28 use case: 'find the single latest doc'."""
        _make_folder_and_docs(tmp_path, "alice", "pdfs", [
            ("proposal_v1.pdf", 1000.0, "v1"),
            ("proposal_v2.pdf", 2000.0, "v2"),
            ("proposal_v3.pdf", 3000.0, "v3"),  # newest
        ])
        res = _list_files_in_folder(
            _agent(tmp_path), folder_title="pdfs",
            sort_by="mtime_desc", limit=1,
        )
        assert res["count"] == 1
        assert res["files"][0]["relative_path"] == "proposal_v3.pdf"

    def test_across_all_folders_mode(self, tmp_path: Path):
        """No folder_id and no folder_title → scan every enabled folder."""
        from praxia.server.routers.documents import (
            Chunk, Document, Folder, _folder_dir, _folders_file,
        )
        user_id = "alice"
        # Create TWO folders by hand (the helper only does one).
        fa, fb = uuid.uuid4().hex, uuid.uuid4().hex
        _folders_file(tmp_path, user_id).parent.mkdir(parents=True, exist_ok=True)
        with _folders_file(tmp_path, user_id).open("w", encoding="utf-8") as f:
            json.dump([
                Folder(id=fa, user_id=user_id, title="alpha",
                       path=str(tmp_path / "alpha"), doc_count=1,
                       enabled=True).model_dump(),
                Folder(id=fb, user_id=user_id, title="bravo",
                       path=str(tmp_path / "bravo"), doc_count=1,
                       enabled=True).model_dump(),
            ], f)
        for fid in (fa, fb):
            d = _folder_dir(tmp_path, user_id, fid)
            d.mkdir(parents=True, exist_ok=True)
            doc_id = uuid.uuid4().hex
            doc = Document(
                id=doc_id, folder_id=fid,
                relative_path=f"{fid[:3]}.pdf", filename=f"{fid[:3]}.pdf",
                size=4, mtime=1.0, content_hash="0" * 64,
                indexed_at=1.0, parser="pdf",
                chunks=[Chunk(index=0, text="body", start=0, end=4)],
            )
            (d / f"{doc_id}.json").write_text(
                json.dumps(doc.model_dump()), encoding="utf-8",
            )

        res = _list_files_in_folder(_agent(tmp_path))  # no folder args
        assert res["count"] == 2
        assert res["scope"] == "all_enabled_folders"
        titles = sorted(set(f["folder_title"] for f in res["files"]))
        assert titles == ["alpha", "bravo"]

    def test_unknown_folder_returns_note(self, tmp_path: Path):
        _make_folder_and_docs(tmp_path, "alice", "pdfs", [
            ("a.pdf", 1.0, "x"),
        ])
        res = _list_files_in_folder(
            _agent(tmp_path), folder_title="nonexistent",
        )
        assert res["count"] == 0
        assert "note" in res
        assert "list_document_folders" in res["note"]


# ─── read_document ──────────────────────────────────────────────────


class TestReadDocument:
    def test_read_by_doc_id(self, tmp_path: Path):
        _make_folder_and_docs(tmp_path, "alice", "pdfs", [
            ("proposal.pdf", 1000.0, "Proposal body — version 1."),
        ])
        # Discover the doc_id via the listing tool, then read.
        listing = _list_files_in_folder(_agent(tmp_path), folder_title="pdfs")
        doc_id = listing["files"][0]["doc_id"]

        res = _read_document(_agent(tmp_path), doc_id=doc_id)
        assert res["found"] is True
        assert res["text"] == "Proposal body — version 1."
        assert res["truncated"] is False
        assert res["mtime"] == 1000.0
        assert res["mtime_iso"].endswith("Z")

    def test_read_by_relative_path_across_folders(self, tmp_path: Path):
        """When the LLM kept only the relative_path string (no folder
        scope), the tool should scan enabled folders and find a match."""
        _make_folder_and_docs(tmp_path, "alice", "pdfs", [
            ("contract.pdf", 1.0, "contract body"),
        ])
        res = _read_document(
            _agent(tmp_path), relative_path="contract.pdf",
        )
        assert res["found"] is True
        assert res["text"] == "contract body"

    def test_truncation_flag(self, tmp_path: Path):
        _make_folder_and_docs(tmp_path, "alice", "pdfs", [
            ("big.pdf", 1.0, "x" * 50_000),
        ])
        listing = _list_files_in_folder(_agent(tmp_path), folder_title="pdfs")
        doc_id = listing["files"][0]["doc_id"]
        res = _read_document(_agent(tmp_path), doc_id=doc_id, max_chars=1000)
        assert res["truncated"] is True
        assert res["char_count"] == 1000

    def test_missing_doc_returns_note(self, tmp_path: Path):
        _make_folder_and_docs(tmp_path, "alice", "pdfs", [
            ("a.pdf", 1.0, "x"),
        ])
        res = _read_document(_agent(tmp_path), doc_id="bogus-id")
        assert res["found"] is False
        assert "note" in res
