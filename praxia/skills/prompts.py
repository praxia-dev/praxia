"""Custom prompt store — user-scoped + org-scoped + admin-distributed.

Mirrors `SkillRegistry` for prompts (which are simpler: just a body of text
with a label). Three scopes:

    personal/<user_id>/<prompt_name>.md  — owned and edited by the user
    org/<prompt_name>.md                  — promoted (curated) prompts
    distributed/<role|user_id>/<name>.md  — admin pushes to specific targets

This lets administrators fan-out a curated prompt to all `member`s, or to a
specific user — without overwriting their personal prompts.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Prompt:
    name: str
    body: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    owner: str = ""  # user_id of the owner (or "admin" for distributed)
    scope: str = "personal"  # "personal" | "org" | "distributed"
    target: str = ""  # role name or user_id when scope=distributed
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class PromptStore:
    """File-based prompt catalog with personal / org / distributed scopes."""

    def __init__(self, storage_dir: Path | str = ".praxia/prompts") -> None:
        self.root = Path(storage_dir)
        for sub in ("personal", "org", "distributed"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    # --- Personal scope ----------------------------------------------------

    def save_personal(
        self,
        user_id: str,
        *,
        name: str,
        body: str,
        description: str = "",
        tags: list[str] | None = None,
    ) -> Prompt:
        p = Prompt(
            name=name,
            body=body,
            description=description,
            tags=tags or [],
            owner=user_id,
            scope="personal",
        )
        path = self._path("personal", user_id, name)
        self._write(path, p)
        return p

    def get_personal(self, user_id: str, name: str) -> Prompt | None:
        return self._read(self._path("personal", user_id, name))

    def list_personal(self, user_id: str) -> list[Prompt]:
        base = self.root / "personal" / user_id
        if not base.exists():
            return []
        return [p for p in (self._read(f) for f in base.glob("*.json")) if p]

    def delete_personal(self, user_id: str, name: str) -> bool:
        path = self._path("personal", user_id, name)
        if path.exists():
            path.unlink()
            return True
        return False

    # --- Org scope (promoted) ---------------------------------------------

    def promote(self, user_id: str, name: str) -> Prompt | None:
        """Copy a personal prompt to org scope."""
        src = self.get_personal(user_id, name)
        if not src:
            return None
        dst = Prompt(
            name=name,
            body=src.body,
            description=src.description,
            tags=src.tags,
            owner="admin",
            scope="org",
            created_at=src.created_at,
        )
        self._write(self._path("org", "", name), dst)
        return dst

    def list_org(self) -> list[Prompt]:
        return [p for p in (self._read(f) for f in (self.root / "org").glob("*.json")) if p]

    def get_org(self, name: str) -> Prompt | None:
        return self._read(self._path("org", "", name))

    # --- Distributed scope (admin push) -----------------------------------

    def distribute(
        self,
        *,
        name: str,
        body: str,
        description: str = "",
        tags: list[str] | None = None,
        target_users: list[str] | None = None,
        target_roles: list[str] | None = None,
    ) -> list[Prompt]:
        """Push a prompt to specific users or roles. Returns the saved copies."""
        if not target_users and not target_roles:
            raise ValueError("Must specify target_users or target_roles")
        out: list[Prompt] = []
        for target in (target_users or []) + (target_roles or []):
            p = Prompt(
                name=name,
                body=body,
                description=description,
                tags=tags or [],
                owner="admin",
                scope="distributed",
                target=target,
            )
            self._write(self._path("distributed", target, name), p)
            out.append(p)
        return out

    def list_distributed_for(self, *, user_id: str, role: str) -> list[Prompt]:
        """Return all distributed prompts targeted at this user_id or role."""
        out: list[Prompt] = []
        for target in (user_id, role):
            base = self.root / "distributed" / target
            if not base.exists():
                continue
            out.extend(p for p in (self._read(f) for f in base.glob("*.json")) if p)
        return out

    # --- Effective view ----------------------------------------------------

    def list_for_user(self, *, user_id: str, role: str) -> list[Prompt]:
        """Merged view: personal + org + distributed-to-user-or-role."""
        seen: dict[str, Prompt] = {}
        # Distributed has precedence over org; personal has precedence over both
        for p in self.list_org():
            seen[p.name] = p
        for p in self.list_distributed_for(user_id=user_id, role=role):
            seen[p.name] = p
        for p in self.list_personal(user_id):
            seen[p.name] = p
        return list(seen.values())

    # --- Internals ---------------------------------------------------------

    def _path(self, scope: str, target: str, name: str) -> Path:
        if scope == "org":
            return self.root / "org" / f"{name}.json"
        sub = self.root / scope / target
        sub.mkdir(parents=True, exist_ok=True)
        return sub / f"{name}.json"

    @staticmethod
    def _write(path: Path, p: Prompt) -> None:
        p.updated_at = time.time()
        with path.open("w", encoding="utf-8") as f:
            json.dump(asdict(p), f, ensure_ascii=False, indent=2)

    @staticmethod
    def _read(path: Path) -> Prompt | None:
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as f:
                return Prompt(**json.load(f))
        except (json.JSONDecodeError, TypeError):
            return None
