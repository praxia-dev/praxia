"""Tests for praxia.agent.file_tools — Codex-style file IO scoped to a
workspace directory.

The shape we care about:

1. **Safety**: paths that escape the workspace (absolute, ``..``,
   symlinks) MUST be rejected — they're the entire reason this
   module exists.
2. **Atomicity**: write_file goes through tmp + rename, so an
   interrupted call leaves either the old file or the new one, never
   a half-written turd.
3. **Edit clarity**: edit_file with ambiguous matches fails closed —
   if we let the agent silently replace one of N matches, the wrong
   one would land too often.
4. **Audit**: every write / edit / delete must show up on
   agent.auth.audit so org admins can see what the agent touched.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from praxia.agent.file_tools import workspace_tools


# ---------------------------------------------------------------------------
# Minimal agent stub — file_tools only need agent.user_id + agent.auth.audit
# ---------------------------------------------------------------------------


class _AuditSpy:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def record(self, **kw: Any) -> None:
        self.records.append(kw)


@dataclass
class _FakeAuth:
    audit: _AuditSpy = field(default_factory=_AuditSpy)


@dataclass
class _FakeAgent:
    user_id: str = "alice"
    auth: _FakeAuth = field(default_factory=_FakeAuth)


@pytest.fixture
def agent() -> _FakeAgent:
    return _FakeAgent()


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    return ws


@pytest.fixture
def tools(workspace: Path):
    """Default tool set with confirmation disabled — preserves the
    original immediate-execution behaviour so the existing tests stay
    a single line each. The confirmation-required path has its own
    dedicated test class below."""
    return workspace_tools(workspace, require_confirmation=False)


# ---------------------------------------------------------------------------
# read_file
# ---------------------------------------------------------------------------


class TestReadFile:
    def test_reads_utf8_text(self, agent, workspace, tools):
        (workspace / "hello.txt").write_text("こんにちは", encoding="utf-8")
        r = tools["read_file"].handler(agent, path="hello.txt")
        assert r["content"] == "こんにちは"
        assert r["truncated"] is False

    def test_missing_file(self, agent, tools):
        r = tools["read_file"].handler(agent, path="no.txt")
        assert "error" in r and "not found" in r["error"]

    def test_directory_is_not_a_file(self, agent, workspace, tools):
        (workspace / "sub").mkdir()
        r = tools["read_file"].handler(agent, path="sub")
        assert "error" in r and "not a regular file" in r["error"]

    def test_rejects_dotdot_escape(self, agent, workspace, tools):
        (workspace.parent / "secret.txt").write_text("private", encoding="utf-8")
        r = tools["read_file"].handler(agent, path="../secret.txt")
        assert "error" in r and "outside" in r["error"]

    def test_rejects_absolute_path(self, agent, tools):
        # Use a path that's almost certainly outside the workspace
        r = tools["read_file"].handler(agent, path="/etc/passwd")
        assert "error" in r and "outside" in r["error"]

    def test_rejects_binary(self, agent, workspace, tools):
        (workspace / "img.bin").write_bytes(b"\xff\xfe\x00\x01\x02BIN")
        r = tools["read_file"].handler(agent, path="img.bin")
        assert "error" in r and "not valid UTF-8" in r["error"]

    def test_offset_and_max(self, agent, workspace, tools):
        (workspace / "data.txt").write_text("HelloWorld", encoding="utf-8")
        r = tools["read_file"].handler(agent, path="data.txt", offset_bytes=5)
        assert r["content"] == "World"
        r2 = tools["read_file"].handler(agent, path="data.txt", max_bytes=4)
        assert r2["content"] == "Hell"
        assert r2["truncated"] is True


# ---------------------------------------------------------------------------
# write_file
# ---------------------------------------------------------------------------


class TestWriteFile:
    def test_creates_new_file(self, agent, workspace, tools):
        r = tools["write_file"].handler(agent, path="new.txt", content="hello")
        assert r["written"] is True
        assert r["created"] is True
        assert (workspace / "new.txt").read_text(encoding="utf-8") == "hello"

    def test_creates_parent_dirs(self, agent, workspace, tools):
        r = tools["write_file"].handler(
            agent, path="deep/nested/note.md", content="# hi"
        )
        assert r["written"] is True
        assert (workspace / "deep" / "nested" / "note.md").read_text() == "# hi"

    def test_overwrite_marks_created_false(self, agent, workspace, tools):
        (workspace / "exists.txt").write_text("old", encoding="utf-8")
        r = tools["write_file"].handler(agent, path="exists.txt", content="new")
        assert r["written"] is True
        assert r["created"] is False
        assert (workspace / "exists.txt").read_text() == "new"

    def test_atomic_no_tmp_left_behind(self, agent, workspace, tools):
        tools["write_file"].handler(agent, path="a.txt", content="x")
        # The tmp file we use ends with .praxia-tmp — none should remain
        leftovers = list(workspace.glob("*.praxia-tmp"))
        assert leftovers == []

    def test_rejects_dotdot_write(self, agent, workspace, tools):
        r = tools["write_file"].handler(agent, path="../escape.txt", content="x")
        assert "error" in r and "outside" in r["error"]
        assert not (workspace.parent / "escape.txt").exists()

    def test_rejects_oversize(self, agent, tools):
        # 5 MiB + 1 byte
        big = "x" * (5 * 1024 * 1024 + 1)
        r = tools["write_file"].handler(agent, path="big.txt", content=big)
        assert "error" in r and "exceeds" in r["error"]

    def test_audit_records_write(self, agent, workspace, tools):
        tools["write_file"].handler(agent, path="auditme.txt", content="hi")
        recs = agent.auth.audit.records
        assert any(r.get("action") == "file_tools.write" for r in recs)
        write = next(r for r in recs if r.get("action") == "file_tools.write")
        assert write["actor"] == "user:alice"
        assert "auditme.txt" in write["metadata"]["path"]


# ---------------------------------------------------------------------------
# edit_file
# ---------------------------------------------------------------------------


class TestEditFile:
    def test_replaces_one_occurrence(self, agent, workspace, tools):
        (workspace / "code.py").write_text("def foo():\n    return 1\n")
        r = tools["edit_file"].handler(
            agent, path="code.py", old="return 1", new="return 42"
        )
        assert r.get("replacements") == 1
        assert "return 42" in (workspace / "code.py").read_text()

    def test_fails_on_zero_matches(self, agent, workspace, tools):
        (workspace / "f.txt").write_text("hello")
        r = tools["edit_file"].handler(agent, path="f.txt", old="goodbye", new="hi")
        assert "error" in r
        assert r["occurrences"] == 0

    def test_fails_closed_on_ambiguous_match(self, agent, workspace, tools):
        (workspace / "f.txt").write_text("foo foo foo")
        r = tools["edit_file"].handler(agent, path="f.txt", old="foo", new="bar")
        # Default count=1 but file has 3 — should refuse to write
        assert "error" in r
        assert r["occurrences"] == 3
        assert (workspace / "f.txt").read_text() == "foo foo foo"  # untouched

    def test_replace_all_with_count_zero(self, agent, workspace, tools):
        (workspace / "f.txt").write_text("foo foo foo")
        r = tools["edit_file"].handler(
            agent, path="f.txt", old="foo", new="bar", count=0
        )
        assert r["replacements"] == 3
        assert (workspace / "f.txt").read_text() == "bar bar bar"

    def test_rejects_empty_old(self, agent, workspace, tools):
        (workspace / "f.txt").write_text("x")
        r = tools["edit_file"].handler(agent, path="f.txt", old="", new="y")
        assert "error" in r

    def test_audit_records_edit(self, agent, workspace, tools):
        (workspace / "f.txt").write_text("a")
        tools["edit_file"].handler(agent, path="f.txt", old="a", new="b")
        assert any(r.get("action") == "file_tools.edit" for r in agent.auth.audit.records)


# ---------------------------------------------------------------------------
# list_files
# ---------------------------------------------------------------------------


class TestListFiles:
    def test_lists_top_level(self, agent, workspace, tools):
        (workspace / "a.txt").write_text("a")
        (workspace / "b.txt").write_text("b")
        r = tools["list_files"].handler(agent)
        names = [e["path"] for e in r["entries"]]
        assert "a.txt" in names and "b.txt" in names

    def test_glob_pattern(self, agent, workspace, tools):
        (workspace / "doc.md").write_text("m")
        (workspace / "code.py").write_text("p")
        r = tools["list_files"].handler(agent, pattern="*.md")
        assert {e["path"] for e in r["entries"]} == {"doc.md"}

    def test_recursive(self, agent, workspace, tools):
        (workspace / "sub").mkdir()
        (workspace / "sub" / "nested.txt").write_text("n")
        r = tools["list_files"].handler(agent, pattern="*.txt", recursive=True)
        names = {e["path"].replace("\\", "/") for e in r["entries"]}
        assert "sub/nested.txt" in names

    def test_truncation_cap(self, agent, workspace, tools):
        for i in range(550):
            (workspace / f"f{i:04d}.txt").write_text("x")
        r = tools["list_files"].handler(agent)
        assert r["truncated"] is True
        assert r["count"] == 500

    def test_rejects_dotdot(self, agent, tools):
        r = tools["list_files"].handler(agent, path="..")
        assert "error" in r and "outside" in r["error"]


# ---------------------------------------------------------------------------
# delete_file
# ---------------------------------------------------------------------------


class TestDeleteFile:
    def test_deletes_a_file(self, agent, workspace, tools):
        (workspace / "x.txt").write_text("x")
        r = tools["delete_file"].handler(agent, path="x.txt")
        assert r["deleted"] is True
        assert not (workspace / "x.txt").exists()

    def test_missing_file_returns_deleted_false(self, agent, tools):
        r = tools["delete_file"].handler(agent, path="ghost.txt")
        assert r["deleted"] is False

    def test_refuses_to_delete_directory(self, agent, workspace, tools):
        (workspace / "sub").mkdir()
        r = tools["delete_file"].handler(agent, path="sub")
        assert "error" in r and "directory" in r["error"]

    def test_audit_records_delete(self, agent, workspace, tools):
        (workspace / "x.txt").write_text("x")
        tools["delete_file"].handler(agent, path="x.txt")
        assert any(r.get("action") == "file_tools.delete" for r in agent.auth.audit.records)


# ---------------------------------------------------------------------------
# Tool registry shape
# ---------------------------------------------------------------------------


class TestToolRegistry:
    def test_exports_five_tools(self, tools):
        assert set(tools.keys()) == {
            "read_file", "write_file", "edit_file", "list_files", "delete_file",
        }

    def test_tools_are_litellm_serializable(self, tools):
        for name, t in tools.items():
            s = t.to_litellm_schema()
            assert s["type"] == "function"
            assert s["function"]["name"] == name
            assert "parameters" in s["function"]

    def test_rejects_non_directory_workspace(self, tmp_path):
        (tmp_path / "f.txt").write_text("x")
        with pytest.raises(ValueError):
            workspace_tools(tmp_path / "f.txt")


# ---------------------------------------------------------------------------
# Confirmation mode — the default: never touch disk without approval
# ---------------------------------------------------------------------------


class TestConfirmationModeDefault:
    """When workspace_tools is built without `require_confirmation=False`
    (i.e. the default), mutating tools MUST NOT touch the disk. They
    queue a pending op record and return `{"pending": True, ...}` so
    the LLM knows to tell the user, and the host can show a confirm
    dialog before applying.
    """

    def test_write_queues_does_not_touch_disk(self, agent, workspace):
        pending: list[dict] = []
        t = workspace_tools(workspace, pending_sink=pending)  # default: confirm ON
        r = t["write_file"].handler(agent, path="new.txt", content="hi")
        assert r["pending"] is True
        assert r["op"] == "write_file"
        assert r["path"] == "new.txt"
        assert r["created"] is True
        assert not (workspace / "new.txt").exists()  # ← key assertion
        assert pending == [
            {"op": "write_file", "path": "new.txt", "bytes": 2, "created": True,
             "content": "hi", "content_preview": "hi", "content_truncated": False}
        ]

    def test_edit_queues_does_not_touch_disk(self, agent, workspace):
        (workspace / "f.txt").write_text("hello")
        pending: list[dict] = []
        t = workspace_tools(workspace, pending_sink=pending)
        r = t["edit_file"].handler(agent, path="f.txt", old="hello", new="bye")
        assert r["pending"] is True
        assert r["op"] == "edit_file"
        # File on disk is unchanged
        assert (workspace / "f.txt").read_text() == "hello"
        assert len(pending) == 1 and pending[0]["op"] == "edit_file"

    def test_delete_queues_does_not_touch_disk(self, agent, workspace):
        (workspace / "x.txt").write_text("doomed")
        pending: list[dict] = []
        t = workspace_tools(workspace, pending_sink=pending)
        r = t["delete_file"].handler(agent, path="x.txt")
        assert r["pending"] is True
        assert r["op"] == "delete_file"
        # Still on disk after the "delete" call
        assert (workspace / "x.txt").exists()
        assert pending == [{"op": "delete_file", "path": "x.txt", "size": 6}]

    def test_reads_still_execute_in_confirmation_mode(self, agent, workspace):
        """read_file / list_files have no side effects — they should
        always run, even in confirmation mode."""
        (workspace / "r.txt").write_text("read me")
        t = workspace_tools(workspace)  # default confirm ON
        r = t["read_file"].handler(agent, path="r.txt")
        assert r["content"] == "read me"
        ls = t["list_files"].handler(agent)
        assert any(e["path"] == "r.txt" for e in ls["entries"])

    def test_escape_check_runs_even_in_confirm_mode(self, agent, workspace):
        """Path escapes are rejected before the op gets queued — we
        don't want a pending op record with an out-of-scope path
        sitting around for a UI to accidentally apply."""
        pending: list[dict] = []
        t = workspace_tools(workspace, pending_sink=pending)
        r = t["write_file"].handler(agent, path="../escape.txt", content="x")
        assert "error" in r and "outside" in r["error"]
        assert pending == []  # nothing queued


# ---------------------------------------------------------------------------
# apply_pending_op — what runs after the user approves
# ---------------------------------------------------------------------------


class TestApplyPendingOp:
    def test_apply_write(self, workspace):
        from praxia.agent.file_tools import apply_pending_op
        op = {"op": "write_file", "path": "new.py", "content": "print('hi')\n"}
        r = apply_pending_op(workspace, op, actor_id="alice")
        assert r["applied"] is True
        assert r["created"] is True
        assert (workspace / "new.py").read_text() == "print('hi')\n"

    def test_apply_edit(self, workspace):
        from praxia.agent.file_tools import apply_pending_op
        (workspace / "code.py").write_text("def foo(): return 1\n")
        op = {
            "op": "edit_file", "path": "code.py",
            "old": "return 1", "new": "return 42", "count": 1,
        }
        r = apply_pending_op(workspace, op)
        assert r["applied"] is True
        assert "return 42" in (workspace / "code.py").read_text()

    def test_apply_edit_fails_if_file_changed(self, workspace):
        """Between the proposal and the apply, someone (the user, an
        external editor, anything) modified the file. The apply must
        notice and bail rather than corrupt the file."""
        from praxia.agent.file_tools import apply_pending_op
        (workspace / "code.py").write_text("def foo(): return 1\n")
        # File mutates externally
        (workspace / "code.py").write_text("def foo(): return 2\n")
        op = {
            "op": "edit_file", "path": "code.py",
            "old": "return 1", "new": "return 42", "count": 1,
        }
        r = apply_pending_op(workspace, op)
        assert "error" in r
        # File is still the externally-mutated version
        assert "return 2" in (workspace / "code.py").read_text()

    def test_apply_delete(self, workspace):
        from praxia.agent.file_tools import apply_pending_op
        (workspace / "x.txt").write_text("bye")
        op = {"op": "delete_file", "path": "x.txt"}
        r = apply_pending_op(workspace, op)
        assert r["applied"] is True
        assert not (workspace / "x.txt").exists()

    def test_apply_rejects_escape_path(self, workspace):
        """Defence in depth: even if a frontend mangled an op record,
        apply_pending_op re-runs the workspace-scope check."""
        from praxia.agent.file_tools import apply_pending_op
        op = {"op": "write_file", "path": "../escape.txt", "content": "x"}
        r = apply_pending_op(workspace, op)
        assert "error" in r and "outside" in r["error"]
        assert not (workspace.parent / "escape.txt").exists()

    def test_apply_unknown_op(self, workspace):
        from praxia.agent.file_tools import apply_pending_op
        r = apply_pending_op(workspace, {"op": "rm_rf", "path": "."})
        assert "error" in r and "unknown op" in r["error"]

    def test_apply_audits_via_record_callable(self, workspace):
        from praxia.agent.file_tools import apply_pending_op
        spy = _AuditSpy()
        op = {"op": "write_file", "path": "a.txt", "content": "x"}
        apply_pending_op(workspace, op, actor_id="alice", audit_record=spy)
        assert any(r.get("action") == "file_tools.apply.write" for r in spy.records)
        rec = next(r for r in spy.records if "action" in r)
        assert rec["actor"] == "user:alice"
