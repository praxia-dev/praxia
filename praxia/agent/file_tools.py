"""Codex-style file-write tools, scoped to a workspace root.

When an agent host wants to let the LLM read / write / edit files on
disk — code generation, document drafting, log inspection — these
tools are the building blocks.

Every handler is closed over a ``workspace_root`` :class:`pathlib.Path`
configured at construction time. Every path the LLM supplies is then
joined onto that root and resolved; anything that resolves *outside*
the workspace (``../../etc/passwd``, an absolute path, a symlink
pointing out) is rejected with a structured error rather than acted on.
There is no escape hatch — the LLM cannot widen its own scope.

Typical use::

    from praxia.agent import AutonomousAgent
    from praxia.agent.file_tools import workspace_tools

    extra = list(workspace_tools(Path("/home/alice/projects/api")).values())
    agent = AutonomousAgent(..., extra_tools=extra)

The desktop app's Workspace tab is the intended primary caller — it
asks the user to pick a folder, hands that path here, and Praxia gains
the ability to author code / docs scoped to that one folder.

Audit + safety:

- Reads cap at ``MAX_READ_BYTES`` (5 MiB) and never expose binary
  files as text — non-decodable content returns an error rather than
  garbled UTF-8.
- Writes cap at ``MAX_WRITE_BYTES`` (5 MiB) and go through an atomic
  ``tmp.replace(target)`` so a crash mid-write can't leave a half-
  written file behind.
- ``edit_file`` (string replacement) requires the literal old string
  to be present exactly once by default — failing closed if the
  search would be ambiguous.
- Every write / edit / delete is recorded through the agent's
  ``auth.audit`` channel so the action shows up in the same log as
  every other tool call.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from praxia.agent.tools import AgentTool

if TYPE_CHECKING:
    from praxia.agent.autonomous import AutonomousAgent

_log = logging.getLogger(__name__)


MAX_READ_BYTES = 5 * 1024 * 1024   # 5 MiB
MAX_WRITE_BYTES = 5 * 1024 * 1024  # 5 MiB
MAX_LIST_ENTRIES = 500             # cap list_files results


# ---------------------------------------------------------------------------
# Path-scope guard
# ---------------------------------------------------------------------------


class _OutsideWorkspaceError(Exception):
    """Raised when a tool argument resolves outside the configured root."""


def apply_pending_op(
    workspace_root: Path | str,
    op: dict[str, Any],
    *,
    actor_id: str | None = None,
    audit_record: Any = None,
) -> dict[str, Any]:
    """Execute a previously-queued file operation.

    The host (server + frontend) gathered an op from
    ``workspace_tools(..., require_confirmation=True)`` during an agent
    run, showed it to the user, and the user clicked "Apply". This
    function is what actually writes / deletes after that approval.

    Path-traversal checks run again here — never trust the agent (or
    the frontend) blindly, even after a UI confirmation.

    Args:
        workspace_root: same root the op was queued against.
        op: a record as appended to ``pending_sink``. Must carry
            ``op`` (``write_file`` / ``edit_file`` / ``delete_file``)
            and the operation-specific fields.
        actor_id: user id to attribute the action to in the audit log.
            Defaults to ``"unknown"`` if not supplied.
        audit_record: a callable with a ``record(**kw)`` interface —
            usually ``agent.auth.audit``. Optional; when present, the
            action is logged.
    """
    root = Path(workspace_root).expanduser().resolve(strict=False)
    if not root.is_dir():
        return {"error": f"workspace_root must be a directory: {root}"}

    op_kind = op.get("op")
    path = op.get("path")
    if not isinstance(path, str):
        return {"error": "op.path is required"}
    try:
        abs_path = _resolve_in(root, path)
    except _OutsideWorkspaceError as e:
        return {"error": str(e)}

    actor = f"user:{actor_id or 'unknown'}"

    def _audit(action: str, **fields: Any) -> None:
        if audit_record is None:
            return
        try:
            audit_record.record(
                actor=actor,
                action=action,
                metadata={k: str(v) for k, v in fields.items()},
            )
        except Exception:  # pragma: no cover
            _log.debug("audit failed for %s", action, exc_info=True)

    if op_kind == "write_file":
        content = op.get("content")
        if not isinstance(content, str):
            return {"error": "op.content is required for write_file"}
        encoded = content.encode("utf-8")
        if len(encoded) > MAX_WRITE_BYTES:
            return {"error": f"content exceeds {MAX_WRITE_BYTES} bytes"}
        created = not abs_path.exists()
        try:
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = abs_path.with_suffix(abs_path.suffix + ".praxia-tmp")
            tmp.write_bytes(encoded)
            os.replace(tmp, abs_path)
        except OSError as e:
            return {"error": f"write failed: {e}"}
        _audit(
            "file_tools.apply.write",
            path=abs_path.relative_to(root),
            bytes=len(encoded),
            created=created,
        )
        return {"applied": True, "path": str(abs_path.relative_to(root)), "bytes": len(encoded), "created": created}

    if op_kind == "edit_file":
        old = op.get("old")
        new = op.get("new")
        count = int(op.get("count", 1))
        if not isinstance(old, str) or not isinstance(new, str) or not old:
            return {"error": "op.old and op.new (non-empty strings) are required"}
        if not abs_path.is_file():
            return {"error": f"not a file: {path}"}
        try:
            text = abs_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            return {"error": f"read failed: {e}"}
        occurrences = text.count(old)
        if occurrences == 0:
            return {"error": "old string not found (file changed since the proposal?)"}
        if count > 0 and occurrences != count:
            return {
                "error": (
                    f"file changed since the proposal — expected {count} occurrence(s), "
                    f"found {occurrences}; re-run the request and re-approve"
                )
            }
        new_text = text.replace(old, new) if count == 0 else text.replace(old, new, count)
        encoded = new_text.encode("utf-8")
        if len(encoded) > MAX_WRITE_BYTES:
            return {"error": f"result exceeds {MAX_WRITE_BYTES} bytes"}
        try:
            tmp = abs_path.with_suffix(abs_path.suffix + ".praxia-tmp")
            tmp.write_bytes(encoded)
            os.replace(tmp, abs_path)
        except OSError as e:
            return {"error": f"write failed: {e}"}
        _audit(
            "file_tools.apply.edit",
            path=abs_path.relative_to(root),
            replacements=occurrences if count == 0 else count,
        )
        return {
            "applied": True,
            "path": str(abs_path.relative_to(root)),
            "replacements": occurrences if count == 0 else count,
        }

    if op_kind == "delete_file":
        if not abs_path.exists():
            return {"applied": False, "reason": "already gone"}
        if abs_path.is_dir():
            return {"error": "refusing to delete a directory"}
        try:
            abs_path.unlink()
        except OSError as e:
            return {"error": f"delete failed: {e}"}
        _audit("file_tools.apply.delete", path=abs_path.relative_to(root))
        return {"applied": True, "deleted": True, "path": str(abs_path.relative_to(root))}

    return {"error": f"unknown op: {op_kind!r}"}


def _resolve_in(workspace_root: Path, user_path: str) -> Path:
    """Join ``user_path`` onto ``workspace_root`` and confirm the result
    is inside the workspace.

    Catches three escape attempts:
    - absolute paths (``/etc/passwd``, ``C:\\Windows``) — joining a
      Path with an absolute path returns the absolute path; the
      ``is_relative_to`` check below rejects it.
    - parent-traversal (``../../secret``) — ``.resolve()`` collapses
      it; if the result is outside, reject.
    - symlinks pointing out — ``.resolve(strict=False)`` follows the
      chain, so a symlink to ``/etc/passwd`` resolves to that target
      and gets rejected.
    """
    if not isinstance(user_path, str) or not user_path.strip():
        raise _OutsideWorkspaceError("path must be a non-empty string")
    p = (workspace_root / user_path).resolve(strict=False)
    try:
        p.relative_to(workspace_root)
    except ValueError as e:
        raise _OutsideWorkspaceError(
            f"path {user_path!r} resolves outside the workspace"
        ) from e
    return p


def _audit(agent: "AutonomousAgent", action: str, **fields: Any) -> None:
    """Best-effort write to the agent's audit log. Never raises —
    audit failure must not break a successful tool call."""
    try:
        if agent.auth is not None and getattr(agent.auth, "audit", None) is not None:
            agent.auth.audit.record(
                actor=f"user:{agent.user_id}",
                action=action,
                metadata={k: str(v) for k, v in fields.items()},
            )
    except Exception:  # pragma: no cover
        _log.debug("audit log write failed for %s", action, exc_info=True)


# ---------------------------------------------------------------------------
# Tool implementations (closed over workspace_root)
# ---------------------------------------------------------------------------


def workspace_tools(
    workspace_root: Path | str,
    *,
    require_confirmation: bool = True,
    pending_sink: list[dict[str, Any]] | None = None,
) -> dict[str, AgentTool]:
    """Return a dict of file-IO :class:`AgentTool` s scoped to
    ``workspace_root``.

    The handlers close over the resolved root, so even if the caller
    later mutates the ``Path`` object the tools keep their original
    scope. This makes the tool set safe to attach to a long-lived
    agent without worrying about the workspace pointer changing under
    its feet.

    Args:
        workspace_root: directory the file tools are pinned to. Path
            traversal escapes are rejected, see :func:`_resolve_in`.
        require_confirmation: when ``True`` (default), mutating tools
            (``write_file`` / ``edit_file`` / ``delete_file``)
            **don't touch the disk**. They append a structured
            operation record to ``pending_sink`` and return a
            ``{"pending": True, "op": ...}`` payload so the LLM knows
            the write was queued, not executed. The host (server +
            desktop UI) then shows the operations to the user and
            calls :func:`apply_pending_op` after explicit approval.
            When ``False``, mutating tools execute immediately —
            useful for non-interactive SDK use, tests, and one-shot
            batch flows where the caller has already arranged consent.
        pending_sink: when ``require_confirmation`` is True, queued
            operations are appended here. The caller passes a list and
            reads it after the agent run finishes. Ignored when
            ``require_confirmation`` is False.

    Read-only tools (``read_file`` / ``list_files``) execute in both
    modes — they have no side effects.
    """
    root = Path(workspace_root).expanduser().resolve(strict=False)
    if not root.exists():
        # Be lenient — the directory may be created by a later
        # write_file call. Just warn.
        _log.info("workspace root %s does not yet exist", root)
    elif not root.is_dir():
        raise ValueError(f"workspace_root must be a directory: {root}")

    # The pending_sink default is None — without a sink, queued ops
    # are recorded only on the return value, not collected for the
    # host. Hosts that want to enumerate pending ops MUST pass a list.
    sink: list[dict[str, Any]] = pending_sink if pending_sink is not None else []

    def _queue(op_kind: str, **fields: Any) -> dict[str, Any]:
        """Record a pending op + return the LLM-facing payload."""
        record = {"op": op_kind, **fields}
        sink.append(record)
        return {
            "pending": True,
            **record,
            "note": (
                "This file operation was QUEUED for user approval, not "
                "executed. Tell the user what you'd like to do and let "
                "them confirm before declaring success."
            ),
        }

    # --- read ----------------------------------------------------------------

    def _read_file(
        agent: "AutonomousAgent",
        *,
        path: str,
        offset_bytes: int = 0,
        max_bytes: int = MAX_READ_BYTES,
    ) -> dict[str, Any]:
        try:
            abs_path = _resolve_in(root, path)
        except _OutsideWorkspaceError as e:
            return {"error": str(e)}
        if not abs_path.exists():
            return {"error": f"file not found: {path}"}
        if not abs_path.is_file():
            return {"error": f"not a regular file: {path}"}
        size = abs_path.stat().st_size
        if size > MAX_READ_BYTES and (max_bytes is None or max_bytes > MAX_READ_BYTES):
            max_bytes = MAX_READ_BYTES
        try:
            with abs_path.open("rb") as fp:
                fp.seek(max(0, int(offset_bytes)))
                data = fp.read(int(max_bytes) if max_bytes else MAX_READ_BYTES)
        except OSError as e:
            return {"error": f"read failed: {e}"}
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return {"error": "file is not valid UTF-8 (binary?)"}
        return {
            "path": str(abs_path.relative_to(root)),
            "size": size,
            "offset_bytes": int(offset_bytes),
            "bytes_returned": len(data),
            "truncated": size > (int(offset_bytes) + len(data)),
            "content": text,
        }

    # --- write (atomic, with audit) -----------------------------------------

    def _write_file(
        agent: "AutonomousAgent",
        *,
        path: str,
        content: str,
    ) -> dict[str, Any]:
        if not isinstance(content, str):
            return {"error": "content must be a string"}
        encoded = content.encode("utf-8")
        if len(encoded) > MAX_WRITE_BYTES:
            return {"error": f"content exceeds {MAX_WRITE_BYTES} bytes"}
        try:
            abs_path = _resolve_in(root, path)
        except _OutsideWorkspaceError as e:
            return {"error": str(e)}
        created = not abs_path.exists()

        if require_confirmation:
            # Generate a small preview for the UI's diff dialog (cap
            # at 4 KiB so we don't ship megabytes back in the response).
            preview = content[:4096]
            return _queue(
                "write_file",
                path=str(abs_path.relative_to(root)),
                bytes=len(encoded),
                created=created,
                content=content,
                content_preview=preview,
                content_truncated=len(content) > 4096,
            )

        try:
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = abs_path.with_suffix(abs_path.suffix + ".praxia-tmp")
            tmp.write_bytes(encoded)
            os.replace(tmp, abs_path)
        except OSError as e:
            return {"error": f"write failed: {e}"}
        _audit(
            agent,
            "file_tools.write",
            path=abs_path.relative_to(root),
            bytes=len(encoded),
            created=created,
        )
        return {
            "path": str(abs_path.relative_to(root)),
            "bytes": len(encoded),
            "created": created,
            "written": True,
        }

    # --- edit (literal string replacement) ----------------------------------

    def _edit_file(
        agent: "AutonomousAgent",
        *,
        path: str,
        old: str,
        new: str,
        count: int = 1,
    ) -> dict[str, Any]:
        if not isinstance(old, str) or not isinstance(new, str):
            return {"error": "old and new must be strings"}
        if old == "":
            return {"error": "old must be non-empty"}
        try:
            abs_path = _resolve_in(root, path)
        except _OutsideWorkspaceError as e:
            return {"error": str(e)}
        if not abs_path.is_file():
            return {"error": f"not a file: {path}"}
        try:
            text = abs_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            return {"error": f"read failed: {e}"}
        occurrences = text.count(old)
        if occurrences == 0:
            return {"error": "old string not found in file", "occurrences": 0}
        if count > 0 and occurrences != count:
            # Fail closed: ambiguous edits are a top cause of bot-
            # generated diffs going wrong. Require the caller to give
            # us a count that matches the file, or a unique old string.
            return {
                "error": (
                    f"expected exactly {count} occurrence(s) of old, "
                    f"found {occurrences}; refine `old` to be unique "
                    "or pass count=0 for replace-all"
                ),
                "occurrences": occurrences,
            }
        new_text = text.replace(old, new) if count == 0 else text.replace(old, new, count)
        encoded = new_text.encode("utf-8")
        if len(encoded) > MAX_WRITE_BYTES:
            return {"error": f"result exceeds {MAX_WRITE_BYTES} bytes"}

        if require_confirmation:
            return _queue(
                "edit_file",
                path=str(abs_path.relative_to(root)),
                old=old,
                new=new,
                count=count,
                replacements=occurrences if count == 0 else count,
                # Send back enough context for the UI to render a diff:
                # the before/after of the regions that changed.
                before_preview=text[:4096],
                after_preview=new_text[:4096],
                preview_truncated=len(new_text) > 4096,
            )

        try:
            tmp = abs_path.with_suffix(abs_path.suffix + ".praxia-tmp")
            tmp.write_bytes(encoded)
            os.replace(tmp, abs_path)
        except OSError as e:
            return {"error": f"write failed: {e}"}
        _audit(
            agent,
            "file_tools.edit",
            path=abs_path.relative_to(root),
            replacements=occurrences if count == 0 else count,
        )
        return {
            "path": str(abs_path.relative_to(root)),
            "replacements": occurrences if count == 0 else count,
            "bytes": len(encoded),
        }

    # --- list ---------------------------------------------------------------

    def _list_files(
        agent: "AutonomousAgent",
        *,
        path: str = ".",
        pattern: str = "*",
        recursive: bool = False,
    ) -> dict[str, Any]:
        try:
            abs_path = _resolve_in(root, path)
        except _OutsideWorkspaceError as e:
            return {"error": str(e)}
        if not abs_path.exists() or not abs_path.is_dir():
            return {"error": f"not a directory: {path}"}
        iterator = abs_path.rglob(pattern) if recursive else abs_path.glob(pattern)
        entries: list[dict[str, Any]] = []
        truncated = False
        for p in iterator:
            try:
                p.relative_to(root)
            except ValueError:
                continue  # symlink escape
            if len(entries) >= MAX_LIST_ENTRIES:
                truncated = True
                break
            try:
                st = p.stat()
            except OSError:
                continue
            entries.append({
                "path": str(p.relative_to(root)),
                "is_dir": p.is_dir(),
                "size": st.st_size,
            })
        entries.sort(key=lambda e: e["path"])
        return {"entries": entries, "count": len(entries), "truncated": truncated}

    # --- delete (audit, opt-in via caller wiring) ---------------------------

    def _delete_file(agent: "AutonomousAgent", *, path: str) -> dict[str, Any]:
        try:
            abs_path = _resolve_in(root, path)
        except _OutsideWorkspaceError as e:
            return {"error": str(e)}
        if not abs_path.exists():
            return {"deleted": False, "reason": "not found"}
        if abs_path.is_dir():
            return {"error": "refusing to delete a directory"}

        if require_confirmation:
            return _queue(
                "delete_file",
                path=str(abs_path.relative_to(root)),
                size=abs_path.stat().st_size,
            )

        try:
            abs_path.unlink()
        except OSError as e:
            return {"error": f"delete failed: {e}"}
        _audit(agent, "file_tools.delete", path=abs_path.relative_to(root))
        return {"deleted": True, "path": str(abs_path.relative_to(root))}

    # --- AgentTool wrappers --------------------------------------------------

    return {t.name: t for t in [
        AgentTool(
            name="read_file",
            description=(
                "Read a UTF-8 text file inside the agent's workspace. "
                "Paths are relative to the workspace root; absolute paths "
                "and `..` traversal are refused. Large files are truncated; "
                "use offset_bytes + max_bytes to page through them."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "offset_bytes": {"type": "integer", "minimum": 0, "default": 0},
                    "max_bytes": {"type": "integer", "minimum": 1, "default": MAX_READ_BYTES},
                },
                "required": ["path"],
            },
            handler=_read_file,
        ),
        AgentTool(
            name="write_file",
            description=(
                "Create or overwrite a UTF-8 text file inside the workspace. "
                "Parent directories are created as needed. Writes are atomic "
                "(tmp + rename) and audit-logged. The 5 MiB hard limit applies."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
            handler=_write_file,
        ),
        AgentTool(
            name="edit_file",
            description=(
                "Replace an exact string in a workspace file. Requires the "
                "literal `old` text to appear exactly `count` times in the "
                "file (default 1) — pass count=0 to replace every occurrence. "
                "Fails without writing when the count does not match, so the "
                "caller can refine `old` to be unique."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old": {"type": "string", "description": "literal text to find"},
                    "new": {"type": "string", "description": "literal replacement"},
                    "count": {
                        "type": "integer",
                        "minimum": 0,
                        "default": 1,
                        "description": "expected occurrences (0 = replace all)",
                    },
                },
                "required": ["path", "old", "new"],
            },
            handler=_edit_file,
        ),
        AgentTool(
            name="list_files",
            description=(
                "List files / directories under a workspace path. Glob "
                "pattern via `pattern` (default `*`). Pass `recursive=true` "
                "to walk the subtree. Capped at 500 entries; symlinks "
                "pointing outside the workspace are silently excluded."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "default": "."},
                    "pattern": {"type": "string", "default": "*"},
                    "recursive": {"type": "boolean", "default": False},
                },
            },
            handler=_list_files,
        ),
        AgentTool(
            name="delete_file",
            description=(
                "Delete a single file inside the workspace. Refuses to delete "
                "directories. Audit-logged. Use sparingly — the agent should "
                "usually `edit_file` instead of deleting."
            ),
            parameters_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
            handler=_delete_file,
        ),
    ]}
