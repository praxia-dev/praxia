"""Per-user data scope registry.

A scope is one of:
  - 'local'      : a folder under .praxia/data/<user_id>/<scope_id>/
                   that the user uploads files into via the UI.
  - 'connector'  : a registered (connector_name, connector_path) tuple
                   resolved at execution time.

Stored as JSON at .praxia/data/<user_id>/scopes.json.
"""
from __future__ import annotations

import json
import shutil
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal


@dataclass
class DataScope:
    id: str
    user_id: str
    name: str
    kind: Literal["local", "connector"]
    description: str = ""
    # local-only — absolute path on disk where uploaded files live
    path: str | None = None
    # connector-only
    connector: str | None = None
    connector_path: str | None = None
    # tree structure — parent's id, or None for top-level folders.
    # Only meaningful for kind == 'local' currently; connector folders
    # stay flat (their hierarchy lives in the external system).
    parent_id: str | None = None
    # Sharing — list of OTHER user_ids that should see this scope as
    # read-accessible. The owner (user_id field above) is always
    # implicit; shared_with NEVER contains the owner. Empty list ==
    # private to owner. The list applies to a single scope; sub-folder
    # sharing is independent (a child must explicitly opt-in).
    shared_with: list[str] = field(default_factory=list)
    # metadata
    created_at: float = field(default_factory=time.time)


class ScopeRegistry:
    """JSON-backed CRUD for per-user data scopes."""

    def __init__(self, data_dir: Path | str) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    # ---------- internals -------------------------------------------------

    def _index_path(self, user_id: str) -> Path:
        return self.data_dir / user_id / "scopes.json"

    def _load(self, user_id: str) -> list[DataScope]:
        p = self._index_path(user_id)
        if not p.exists():
            return []
        try:
            with p.open("r", encoding="utf-8") as f:
                data = json.load(f)
            # Filter unknown keys so legacy index files (pre `shared_with`)
            # don't blow up on dataclass construction.
            _fields = {f.name for f in DataScope.__dataclass_fields__.values()}
            return [
                DataScope(**{k: v for k, v in d.items() if k in _fields})
                for d in data
                if isinstance(d, dict)
            ]
        except (json.JSONDecodeError, TypeError):
            return []

    def _save(self, user_id: str, scopes: list[DataScope]) -> None:
        p = self._index_path(user_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            json.dump([asdict(s) for s in scopes], f, ensure_ascii=False, indent=2)

    def _all_owners(self) -> list[str]:
        """Return every user-id directory that has a scopes.json file."""
        if not self.data_dir.exists():
            return []
        out: list[str] = []
        for d in self.data_dir.iterdir():
            if d.is_dir() and (d / "scopes.json").exists():
                out.append(d.name)
        return out

    # ---------- public CRUD -----------------------------------------------

    def list_for_user(self, user_id: str) -> list[DataScope]:
        """Return all scopes the user can see — their own plus any
        scope where ``user_id in scope.shared_with``."""
        own = self._load(user_id)
        own_ids = {s.id for s in own}
        shared: list[DataScope] = []
        for owner in self._all_owners():
            if owner == user_id:
                continue
            for s in self._load(owner):
                if user_id in (s.shared_with or []) and s.id not in own_ids:
                    shared.append(s)
        return own + shared

    def list_owned(self, user_id: str) -> list[DataScope]:
        """Owner-scoped variant — does NOT include shared-in scopes.
        Used by the share-management UI so admins manipulate only
        their own folders."""
        return self._load(user_id)

    def get(self, user_id: str, scope_id: str) -> DataScope | None:
        # Search the user's own scopes first; fall back to scopes
        # shared in from other owners. Owner-resolution lets the
        # caller pass the *viewer's* user_id without knowing who
        # actually owns the scope.
        own = next((s for s in self._load(user_id) if s.id == scope_id), None)
        if own is not None:
            return own
        for owner in self._all_owners():
            if owner == user_id:
                continue
            cand = next((s for s in self._load(owner) if s.id == scope_id), None)
            if cand is not None and user_id in (cand.shared_with or []):
                return cand
        return None

    # ---------- sharing ---------------------------------------------------

    def share(self, owner_id: str, scope_id: str, with_user_ids: list[str]) -> bool:
        """Add ``with_user_ids`` to a scope's ``shared_with`` list.
        Owner-only operation. Returns True if any change was made.
        Does NOT validate that the target user_ids exist — the
        UserStore is the source of truth for that."""
        scopes = self._load(owner_id)
        target = next((s for s in scopes if s.id == scope_id), None)
        if target is None:
            return False
        existing = set(target.shared_with or [])
        owner_self = {owner_id}
        new = sorted((existing | set(with_user_ids)) - owner_self)
        if new == sorted(existing):
            return False
        target.shared_with = new
        self._save(owner_id, scopes)
        return True

    def unshare(self, owner_id: str, scope_id: str, user_ids: list[str]) -> bool:
        """Remove ``user_ids`` from a scope's ``shared_with`` list."""
        scopes = self._load(owner_id)
        target = next((s for s in scopes if s.id == scope_id), None)
        if target is None:
            return False
        existing = set(target.shared_with or [])
        new = sorted(existing - set(user_ids))
        if new == sorted(existing):
            return False
        target.shared_with = new
        self._save(owner_id, scopes)
        return True

    def set_shared_with(self, owner_id: str, scope_id: str, user_ids: list[str]) -> bool:
        """Replace the scope's ``shared_with`` list verbatim. Filters
        out the owner_id itself (never shares with self)."""
        scopes = self._load(owner_id)
        target = next((s for s in scopes if s.id == scope_id), None)
        if target is None:
            return False
        new = sorted(uid for uid in set(user_ids) if uid != owner_id)
        if new == sorted(target.shared_with or []):
            return False
        target.shared_with = new
        self._save(owner_id, scopes)
        return True

    def create_local(
        self,
        user_id: str,
        name: str,
        description: str = "",
        parent_id: str | None = None,
    ) -> DataScope:
        scope_id = uuid.uuid4().hex[:12]
        folder = self.data_dir / user_id / scope_id
        folder.mkdir(parents=True, exist_ok=True)
        # Validate parent_id refers to an existing local scope owned by
        # this user; otherwise demote to root.
        if parent_id is not None:
            parent = self.get(user_id, parent_id)
            if parent is None or parent.kind != "local":
                parent_id = None
        scope = DataScope(
            id=scope_id,
            user_id=user_id,
            name=name,
            kind="local",
            path=str(folder),
            description=description,
            parent_id=parent_id,
        )
        scopes = self._load(user_id)
        scopes.append(scope)
        self._save(user_id, scopes)
        return scope

    def list_children(self, user_id: str, parent_id: str | None) -> list[DataScope]:
        """Return scopes whose parent_id == parent_id (None = top-level)."""
        return [s for s in self._load(user_id) if s.parent_id == parent_id]

    def full_path(self, user_id: str, scope_id: str) -> str:
        """Return slash-joined path like 'Customers/Acme/Q3' for display.

        Walks parent_id chain up to root. Limits walk depth to avoid
        infinite loops on corrupted data.
        """
        parts: list[str] = []
        seen: set[str] = set()
        current = self.get(user_id, scope_id)
        depth = 0
        while current is not None and depth < 32 and current.id not in seen:
            seen.add(current.id)
            parts.append(current.name)
            if current.parent_id is None:
                break
            current = self.get(user_id, current.parent_id)
            depth += 1
        return "/".join(reversed(parts))

    def descendants(self, user_id: str, scope_id: str) -> list[DataScope]:
        """Return all descendants of scope_id (recursive)."""
        all_scopes = self._load(user_id)
        out: list[DataScope] = []
        frontier = [scope_id]
        seen: set[str] = set()
        while frontier:
            pid = frontier.pop()
            if pid in seen:
                continue
            seen.add(pid)
            for s in all_scopes:
                if s.parent_id == pid:
                    out.append(s)
                    frontier.append(s.id)
        return out

    def create_connector(
        self,
        user_id: str,
        name: str,
        connector: str,
        connector_path: str,
        description: str = "",
    ) -> DataScope:
        scope_id = uuid.uuid4().hex[:12]
        scope = DataScope(
            id=scope_id,
            user_id=user_id,
            name=name,
            kind="connector",
            connector=connector,
            connector_path=connector_path,
            description=description,
        )
        scopes = self._load(user_id)
        scopes.append(scope)
        self._save(user_id, scopes)
        return scope

    def delete(self, user_id: str, scope_id: str) -> bool:
        """Delete a scope. For local scopes, recursively delete all
        descendants too (sub-folders go with the parent)."""
        scopes = self._load(user_id)
        target = next((s for s in scopes if s.id == scope_id), None)
        if target is None:
            return False

        # Collect descendants if local (so sub-folders also go away)
        if target.kind == "local":
            doomed_ids = {scope_id}
            doomed_paths = [target.path] if target.path else []
            # BFS over descendants
            frontier = [scope_id]
            while frontier:
                pid = frontier.pop()
                for s in scopes:
                    if s.parent_id == pid and s.id not in doomed_ids:
                        doomed_ids.add(s.id)
                        if s.kind == "local" and s.path:
                            doomed_paths.append(s.path)
                        frontier.append(s.id)

            scopes = [s for s in scopes if s.id not in doomed_ids]
            self._save(user_id, scopes)
            for p in doomed_paths:
                try:
                    shutil.rmtree(p)
                except (FileNotFoundError, OSError):
                    pass
            return True

        # connector — single delete, no descendants
        scopes = [s for s in scopes if s.id != scope_id]
        self._save(user_id, scopes)
        return True

    # ---------- file-level helpers (local scopes) -------------------------

    def list_local_files(self, scope: DataScope) -> list[Path]:
        if scope.kind != "local" or not scope.path:
            return []
        folder = Path(scope.path)
        if not folder.exists():
            return []
        return sorted(f for f in folder.iterdir() if f.is_file())

    def save_uploaded_files(self, scope: DataScope, uploaded_files: list) -> list[str]:
        """Persist a list of Streamlit UploadedFile-like objects to a local scope.

        Each file must expose .name and either .getvalue() or .read() returning
        bytes. Returns the list of saved file names.
        """
        if scope.kind != "local" or not scope.path:
            return []
        folder = Path(scope.path)
        folder.mkdir(parents=True, exist_ok=True)
        saved: list[str] = []
        for f in uploaded_files:
            data = f.getvalue() if hasattr(f, "getvalue") else f.read()
            (folder / f.name).write_bytes(data)
            saved.append(f.name)
        return saved

    def delete_file(self, scope: DataScope, file_name: str) -> bool:
        if scope.kind != "local" or not scope.path:
            return False
        target = Path(scope.path) / file_name
        if not target.exists():
            return False
        target.unlink()
        return True


__all__ = ["DataScope", "ScopeRegistry"]
