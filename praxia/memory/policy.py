"""Memory policy — admin-controlled defaults + per-user mode preference.

Two layers of control:

1. **Admin policy** (`MemoryAdminPolicy`) — a JSON file at
   `.praxia/admin/memory_policy.json` that pins which backend(s) are
   allowed and whether users may change their accumulation mode.
   Set / read via `praxia admin memory ...` CLI.

2. **User preference** (`MemoryUserPreference`) — per-user setting at
   `.praxia/users/<user_id>/memory_pref.json`: chosen mode (accumulate
   / read_only), chosen backend (subject to admin allow-list).

`PersonalMemory` resolves the effective configuration at construction:

    admin.enforced_backend  > user_pref.backend  > admin.default_backend > "json"
    admin.mode_locked       → admin.default_mode
    otherwise               → user_pref.mode    > admin.default_mode > "accumulate"
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

MemoryMode = Literal["accumulate", "read_only"]


@dataclass
class MemoryAdminPolicy:
    """System-wide policy. Admin writes; users observe."""

    enforced_backend: str | None = None        # if set, overrides user choice
    default_backend: str = "json"
    allowed_backends: list[str] = field(default_factory=list)  # empty = any
    default_mode: MemoryMode = "accumulate"
    mode_locked: bool = False                  # if True, users cannot override
    accumulate_locked_to: list[str] = field(default_factory=list)  # roles forced to accumulate

    @classmethod
    def load(cls, storage_dir: Path | str) -> "MemoryAdminPolicy":
        path = Path(storage_dir) / "admin" / "memory_policy.json"
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        # Filter to known fields so unknown keys don't blow up
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self, storage_dir: Path | str) -> Path:
        path = Path(storage_dir) / "admin" / "memory_policy.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        return path

    def is_backend_allowed(self, backend: str) -> bool:
        if self.enforced_backend is not None:
            return backend == self.enforced_backend
        if not self.allowed_backends:
            return True
        return backend in self.allowed_backends


@dataclass
class MemoryUserPreference:
    """Per-user preference. User writes (subject to admin policy)."""

    user_id: str
    backend: str | None = None       # None = use admin default
    mode: MemoryMode | None = None   # None = use admin default

    @classmethod
    def load(cls, storage_dir: Path | str, user_id: str) -> "MemoryUserPreference":
        path = Path(storage_dir) / "users" / user_id / "memory_pref.json"
        if not path.exists():
            return cls(user_id=user_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            user_id=user_id,
            backend=data.get("backend"),
            mode=data.get("mode"),
        )

    def save(self, storage_dir: Path | str) -> Path:
        path = Path(storage_dir) / "users" / self.user_id / "memory_pref.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"backend": self.backend, "mode": self.mode}, indent=2),
            encoding="utf-8",
        )
        return path


@dataclass
class ResolvedMemoryConfig:
    """The effective config after merging admin policy + user pref."""

    backend: str
    mode: MemoryMode
    locked_by_admin: bool
    reason: str  # human-readable trace of why these values were chosen


def resolve_memory_config(
    *,
    user_id: str,
    storage_dir: Path | str,
    user_role: str | None = None,
    requested_backend: str | None = None,
    requested_mode: MemoryMode | None = None,
) -> ResolvedMemoryConfig:
    """Merge admin policy + user pref + this-call request → final config.

    Resolution order (highest precedence first):
        1. admin.enforced_backend (always wins)
        2. requested_backend (if allowed by admin)
        3. user_pref.backend (if allowed by admin)
        4. admin.default_backend
        5. "json"

    For mode:
        1. admin.mode_locked → admin.default_mode (no override possible)
        2. user role in admin.accumulate_locked_to → "accumulate"
        3. requested_mode (if not None)
        4. user_pref.mode (if not None)
        5. admin.default_mode
    """
    admin = MemoryAdminPolicy.load(storage_dir)
    pref = MemoryUserPreference.load(storage_dir, user_id)

    # Backend resolution
    backend = "json"
    reason_parts: list[str] = []
    if admin.enforced_backend:
        backend = admin.enforced_backend
        reason_parts.append(f"admin enforced backend={backend}")
    elif requested_backend and admin.is_backend_allowed(requested_backend):
        backend = requested_backend
        reason_parts.append(f"call-site backend={backend}")
    elif pref.backend and admin.is_backend_allowed(pref.backend):
        backend = pref.backend
        reason_parts.append(f"user pref backend={backend}")
    else:
        backend = admin.default_backend
        reason_parts.append(f"admin default backend={backend}")

    # Mode resolution
    locked = False
    mode: MemoryMode = "accumulate"
    if admin.mode_locked:
        mode = admin.default_mode
        locked = True
        reason_parts.append(f"admin locked mode={mode}")
    elif user_role and user_role in admin.accumulate_locked_to:
        mode = "accumulate"
        locked = True
        reason_parts.append(f"role {user_role} locked to accumulate")
    elif requested_mode is not None:
        mode = requested_mode
        reason_parts.append(f"call-site mode={mode}")
    elif pref.mode is not None:
        mode = pref.mode
        reason_parts.append(f"user pref mode={mode}")
    else:
        mode = admin.default_mode
        reason_parts.append(f"admin default mode={mode}")

    return ResolvedMemoryConfig(
        backend=backend,
        mode=mode,
        locked_by_admin=locked,
        reason=" | ".join(reason_parts),
    )


__all__ = [
    "MemoryMode",
    "MemoryAdminPolicy",
    "MemoryUserPreference",
    "ResolvedMemoryConfig",
    "resolve_memory_config",
]
