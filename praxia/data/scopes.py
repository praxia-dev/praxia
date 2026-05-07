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
            return [DataScope(**d) for d in data]
        except (json.JSONDecodeError, TypeError):
            return []

    def _save(self, user_id: str, scopes: list[DataScope]) -> None:
        p = self._index_path(user_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            json.dump([asdict(s) for s in scopes], f, ensure_ascii=False, indent=2)

    # ---------- public CRUD -----------------------------------------------

    def list_for_user(self, user_id: str) -> list[DataScope]:
        return self._load(user_id)

    def get(self, user_id: str, scope_id: str) -> DataScope | None:
        return next((s for s in self._load(user_id) if s.id == scope_id), None)

    def create_local(
        self,
        user_id: str,
        name: str,
        description: str = "",
    ) -> DataScope:
        scope_id = uuid.uuid4().hex[:12]
        folder = self.data_dir / user_id / scope_id
        folder.mkdir(parents=True, exist_ok=True)
        scope = DataScope(
            id=scope_id,
            user_id=user_id,
            name=name,
            kind="local",
            path=str(folder),
            description=description,
        )
        scopes = self._load(user_id)
        scopes.append(scope)
        self._save(user_id, scopes)
        return scope

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
        scopes = self._load(user_id)
        target = next((s for s in scopes if s.id == scope_id), None)
        if target is None:
            return False
        scopes = [s for s in scopes if s.id != scope_id]
        self._save(user_id, scopes)
        if target.kind == "local" and target.path:
            try:
                shutil.rmtree(target.path)
            except FileNotFoundError:
                pass
            except OSError:
                # leave the folder if removal fails — registry is consistent.
                pass
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
