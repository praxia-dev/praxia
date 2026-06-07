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
    def test_exports_six_tools(self, tools):
        assert set(tools.keys()) == {
            "read_file", "write_file", "edit_file", "list_files",
            "delete_file", "render_document",
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


# ---------------------------------------------------------------------------
# render_document — deliverable formats (md / html / json / pptx / docx)
# ---------------------------------------------------------------------------


class TestRenderDocument:
    """The render_document tool wraps praxia.io.exporters so the LLM can
    say 'make me a 5-slide deck about X' / 'write a Word report'. Same
    workspace scoping + approval gate as the rest of file_tools.
    """

    def test_queues_in_confirmation_mode_does_not_touch_disk(self, agent, workspace):
        pending: list[dict] = []
        t = workspace_tools(workspace, pending_sink=pending)  # default confirm ON
        r = t["render_document"].handler(
            agent,
            path="slides/q3.pptx",
            format="pptx",
            source_markdown="# Q3\n\n## Revenue\n- up 12%",
        )
        assert r["pending"] is True
        assert r["op"] == "render_document"
        assert r["format"] == "pptx"
        # Nothing on disk yet
        assert not (workspace / "slides" / "q3.pptx").exists()
        assert pending and pending[0]["op"] == "render_document"

    def test_immediate_mode_writes_html(self, agent, workspace):
        t = workspace_tools(workspace, require_confirmation=False)
        r = t["render_document"].handler(
            agent,
            path="out.html",
            format="html",
            source_markdown="# Hello\n\nworld",
        )
        assert r["rendered"] is True
        assert r["format"] == "html"
        # File exists and looks like HTML
        body = (workspace / "out.html").read_bytes()
        assert body.startswith(b"<") or b"<html" in body.lower() or b"<h1" in body.lower()

    def test_immediate_mode_writes_md(self, agent, workspace):
        t = workspace_tools(workspace, require_confirmation=False)
        r = t["render_document"].handler(
            agent,
            path="note.md",
            format="md",
            source_markdown="# Note\n\nbody",
        )
        assert r["rendered"] is True
        assert (workspace / "note.md").read_text(encoding="utf-8").startswith("# Note")

    def test_rejects_unsupported_format(self, agent, workspace):
        t = workspace_tools(workspace, require_confirmation=False)
        r = t["render_document"].handler(
            agent, path="x.weird", format="xyz", source_markdown="hi"
        )
        assert "error" in r and "unsupported" in r["error"].lower()

    def test_rejects_escape_path(self, agent, workspace):
        t = workspace_tools(workspace, require_confirmation=False)
        r = t["render_document"].handler(
            agent, path="../escape.md", format="md", source_markdown="x"
        )
        assert "error" in r and "outside" in r["error"]

    def test_apply_pending_render_writes_html(self, workspace):
        from praxia.agent.file_tools import apply_pending_op
        op = {
            "op": "render_document",
            "path": "report.html",
            "format": "html",
            "source_markdown": "# Title\n\nbody",
        }
        r = apply_pending_op(workspace, op, actor_id="alice")
        assert r["applied"] is True
        assert r["format"] == "html"
        body = (workspace / "report.html").read_bytes()
        assert len(body) > 0

    def test_apply_pending_render_rejects_escape(self, workspace):
        from praxia.agent.file_tools import apply_pending_op
        r = apply_pending_op(workspace, {
            "op": "render_document",
            "path": "../sneaky.md",
            "format": "md",
            "source_markdown": "x",
        })
        assert "error" in r

    def test_tool_registered(self, tools):
        assert "render_document" in tools
        schema = tools["render_document"].to_litellm_schema()
        assert schema["function"]["name"] == "render_document"
        props = schema["function"]["parameters"]["properties"]
        assert "format" in props and "source_markdown" in props


# ---------------------------------------------------------------------------
# Unescape heuristic — LLM double-escaped \n must be undone
# ---------------------------------------------------------------------------


class TestUnescapeHeuristic:
    """Real bug from alpha10: the agent rendered a proposal where the
    Markdown source arrived with literal backslash+n pairs instead of
    actual newlines, producing a single unbroken paragraph in the
    .md file and a 1-slide .pptx. file_tools auto-detects the shape
    and undoes the double-escape."""

    def test_double_escaped_md_is_unescaped(self, agent, workspace):
        from praxia.agent.file_tools import _maybe_unescape

        # Real shape from the field: many literal "\n" tokens, zero
        # real newlines
        bad = "# Title\\n\\n## Section\\n- bullet 1\\n- bullet 2"
        fixed = _maybe_unescape(bad)
        assert "\n" in fixed
        assert fixed.startswith("# Title\n\n")
        assert "## Section" in fixed
        assert "- bullet 1\n- bullet 2" in fixed

    def test_proper_input_is_left_alone(self):
        from praxia.agent.file_tools import _maybe_unescape
        good = "# Title\n\n## Section\n- bullet\n"
        assert _maybe_unescape(good) is good or _maybe_unescape(good) == good

    def test_legitimate_literal_backslash_n_in_code(self):
        from praxia.agent.file_tools import _maybe_unescape
        # If the text has real newlines AND a literal "\n" (code
        # sample), don't mutate — the heuristic only fires on the
        # "no real newlines but lots of literal \n" pattern.
        text = "Real newline here.\nCode example: `print(\"\\n\")`."
        assert _maybe_unescape(text) == text

    def test_single_stray_literal_is_not_unescaped(self):
        """One stray "\n" in an otherwise normal string is probably
        intentional (code, regex). Threshold is 2+."""
        from praxia.agent.file_tools import _maybe_unescape
        text = "test \\n end"
        assert _maybe_unescape(text) == text

    def test_render_document_unescapes_at_call_time(self, agent, workspace):
        """End-to-end: render_document with double-escaped input writes
        properly-formatted output (real newlines + slide segmentation
        possible)."""
        t = workspace_tools(workspace, require_confirmation=False)
        bad_source = (
            "# Q3 Summary\\n\\n"
            "## Revenue\\n- up 12%\\n\\n"
            "## Outlook\\n- continued growth\\n"
        )
        r = t["render_document"].handler(
            agent, path="out.md", format="md", source_markdown=bad_source
        )
        assert r["rendered"] is True
        body = (workspace / "out.md").read_text(encoding="utf-8")
        # Real newlines made it to disk
        assert "\n" in body
        # The slide markers survive (so PPTX would segment too)
        assert "## Revenue" in body
        assert "## Outlook" in body

    def test_write_file_unescapes_at_call_time(self, agent, workspace):
        t = workspace_tools(workspace, require_confirmation=False)
        bad_content = "line one\\nline two\\nline three"
        r = t["write_file"].handler(
            agent, path="multi.txt", content=bad_content
        )
        assert r["written"] is True
        body = (workspace / "multi.txt").read_text(encoding="utf-8")
        assert body == "line one\nline two\nline three"

    def test_apply_pending_op_unescapes_too(self, workspace):
        """Defence in depth: even if a stored pending op has the
        double-escaped form (because the LLM emitted it that way),
        the apply path unescapes before writing."""
        from praxia.agent.file_tools import apply_pending_op
        op = {
            "op": "write_file",
            "path": "x.md",
            "content": "# Hi\\n\\nbody\\n",
        }
        r = apply_pending_op(workspace, op, actor_id="alice")
        assert r["applied"] is True
        body = (workspace / "x.md").read_text(encoding="utf-8")
        assert body.startswith("# Hi\n\nbody\n")
