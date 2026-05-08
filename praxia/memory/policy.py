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
    """System-wide policy. Admin writes; users observe.

    The policy now describes the **single backend strategy** every user
    is locked into — there is no per-user override path through the UI
    anymore. The `backend_strategy` discriminator decides how the Layer-1
    backend is built:

    - ``single``    — one backend for everyone (the default and simplest)
    - ``composite`` — fan out reads to several backends and fuse via
                       Reciprocal Rank Fusion / union / intersection /
                       weighted / llm_rerank. Writes go to a single
                       chosen target.
    - ``routed``    — pick a backend per query via a router (rule-based
                       regex matcher or LLM-driven). Writes go to a
                       single chosen target.

    Composite + routed mirror the SDK constructs in
    ``praxia.memory.composite`` and ``praxia.memory.router``, exposed
    here so the multi-backend story is admin-configurable from the UI.
    """

    # ---- backend strategy --------------------------------------------------
    backend_strategy: Literal["single", "composite", "routed"] = "single"
    # 'single' mode: the one backend used for everyone.
    backend: str = "json"

    # 'composite' mode
    composite_backends: list[str] = field(default_factory=list)
    composite_fusion: Literal[
        "rrf", "union", "intersection", "weighted", "llm_rerank"
    ] = "rrf"
    composite_write_to: str = ""

    # 'routed' mode
    routed_backends: list[str] = field(default_factory=list)
    routed_router: Literal["rule", "llm"] = "rule"
    routed_write_to: str = ""

    # ---- memory accumulation mode -----------------------------------------
    default_mode: MemoryMode = "accumulate"

    # ---- legacy fields (kept so old policy.json files still load) ---------
    # Treat these as deprecated; the post-init migrates them into the
    # canonical fields above. Don't read them from new code.
    enforced_backend: str | None = None
    default_backend: str = "json"
    allowed_backends: list[str] = field(default_factory=list)
    mode_locked: bool = False
    accumulate_locked_to: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Migrate from old schema. Old policies set enforced_backend or
        # default_backend; if the new `backend` field is still at the
        # bare default, prefer enforced > default from the legacy fields.
        if self.backend == "json" and self.backend_strategy == "single":
            if self.enforced_backend:
                self.backend = self.enforced_backend
            elif self.default_backend and self.default_backend != "json":
                self.backend = self.default_backend

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
        # Retained for backwards compat with code/tests that still call
        # this. New code paths route everything through `backend_strategy`.
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


def build_personal_backend(
    storage_dir: Path | str,
    *,
    user_id: str,
):
    """Build the Layer-1 backend object for a user according to the
    current MemoryAdminPolicy.

    Returns either:
      - a string ("json", "mem0", ...) — caller should pass it to
        ``PersonalMemory(backend=name, ...)`` or ``load_backend(name)``
      - a fully-instantiated MemoryBackend object (CompositeBackend
        or RoutedBackend) — caller should pass it directly.

    The orchestrator already accepts both shapes via PersonalMemory's
    ``backend`` arg, so the caller doesn't need to branch on the return
    type.

    Why returning a union: simple ``single`` policies get the cheap
    string path (lazy import of optional deps inside load_backend);
    composite/routed need a constructed object because there's no
    1:1 backend name for them.
    """
    storage_dir = Path(storage_dir)
    admin = MemoryAdminPolicy.load(storage_dir)
    if admin.backend_strategy == "single":
        name = admin.backend or "json"
        if name == "json":
            return name
        # Probe non-json backends before committing the orchestrator
        # to one. If it can't init (missing API key, missing optional
        # package), fall back to json with a warning rather than
        # crashing Praxia start-up. The admin can fix the keys in
        # Settings and the next restart will re-attempt.
        from praxia.memory.backends import load_backend
        try:
            load_backend(name)
            return name
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "Memory policy backend %r failed to initialize (%s). "
                "Falling back to 'json'. Configure the backend's API "
                "keys in Admin → Settings → LLM providers to enable it.",
                name, exc,
            )
            return "json"

    # Composite / Routed need actual backend instances.
    from praxia.memory.backends import load_backend
    if admin.backend_strategy == "composite":
        from praxia.memory.composite import CompositeBackend, WeightedBackend
        names = admin.composite_backends or []
        if not names:
            return "json"  # misconfigured; fall back rather than crash
        wrapped: list[WeightedBackend] = []
        for n in names:
            kwargs = {"storage_dir": storage_dir / "personal"} if n == "json" else {}
            try:
                wrapped.append(WeightedBackend(name=n, backend=load_backend(n, **kwargs)))
            except Exception:
                # Skip backends that fail to init (e.g. missing API key)
                # rather than blowing up the whole stack.
                continue
        if not wrapped:
            return "json"
        return CompositeBackend(
            backends=wrapped,
            fusion=admin.composite_fusion,  # type: ignore[arg-type]
            write_to=admin.composite_write_to or wrapped[0].name,
        )

    if admin.backend_strategy == "routed":
        from praxia.memory.router import RoutedBackend, RuleRouter, LLMRouter
        names = admin.routed_backends or []
        if not names:
            return "json"
        backends_dict = {}
        for n in names:
            kwargs = {"storage_dir": storage_dir / "personal"} if n == "json" else {}
            try:
                backends_dict[n] = load_backend(n, **kwargs)
            except Exception:
                continue
        if not backends_dict:
            return "json"
        write_to = admin.routed_write_to or next(iter(backends_dict))
        if write_to not in backends_dict:
            write_to = next(iter(backends_dict))
        router = LLMRouter() if admin.routed_router == "llm" else RuleRouter()
        return RoutedBackend(
            backends=backends_dict,
            router=router,
            write_to=write_to,
        )

    return "json"


__all__ = [
    "MemoryMode",
    "MemoryAdminPolicy",
    "MemoryUserPreference",
    "ResolvedMemoryConfig",
    "resolve_memory_config",
    "build_personal_backend",
]
