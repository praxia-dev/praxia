"""Dynamic memory routing — pick the right backend(s) per query.

Different LTMs are good at different things:

    Mem0       — entity linking, hybrid semantic search
    Zep        — temporal knowledge graph (time-axis queries)
    HindSight  — generic vector search
    LangMem    — namespaced semantic memory
    Letta      — shared blocks (read_only policies)
    JSON       — append-only audit trail (exact recall)

A `MemoryRouter` inspects the incoming query and decides:

    1. Which backend(s) to consult
    2. Whether to fuse results (composite mode) or pick one (single mode)

Two routing strategies are built in:

    - **RuleRouter** — static keyword/regex rules (fast, deterministic,
                       transparent — recommended default)
    - **LLMRouter**  — LLM classifies the query intent and picks a route
                       (most accurate, costs an extra LLM call)

Both produce a `RouteDecision` describing the chosen plan; the caller
hands that to a `CompositeBackend` (fan-out) or a single backend
(direct).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from praxia.memory.backends import MemoryBackend


@dataclass
class RouteDecision:
    """The router's plan for one query."""

    backends: list[str]                    # backend names to consult
    fusion: Literal["rrf", "union", "intersection", "weighted", "llm_rerank"]
    reason: str                            # human-readable trace
    confidence: float = 1.0                # 0..1


class MemoryRouter(Protocol):
    """Anything with a `route(query) -> RouteDecision` method."""

    def route(self, query: str, *, available_backends: list[str]) -> RouteDecision: ...


# --- Rule-based router (fast, deterministic) --------------------------------

# Sensible defaults — override via constructor.
#
# Each rule pairs an ASCII fragment (uses \b word boundaries) with a CJK
# fragment (no \b — Python's \b is between word/non-word chars, so it never
# fires between two adjacent CJK characters). We test them as alternations.
DEFAULT_RULES: list[tuple[re.Pattern, list[str], str]] = [
    # Audit / change history → JSON for exact-recall (ordered first so audit
    # queries like "show me last week's audit log" prefer JSON over Zep).
    (
        re.compile(
            r"(\b(audit|change ?log|changelog|history)\b|履歴|変更履歴|監査|変更ログ)",
            re.IGNORECASE,
        ),
        ["json", "mem0"],
        "audit query → JSON backend prioritized",
    ),
    # Temporal queries → time-aware backends first
    (
        re.compile(
            r"(\b(yesterday|last (week|month|quarter|year)|since|after|before)\b"
            r"|先月|先週|先期|先年|昨日|今月|過去|以降|以前|時系列)",
            re.IGNORECASE,
        ),
        ["zep", "mem0", "hindsight"],
        "temporal keywords → KG-backed backend prioritized",
    ),
    # Entity / proper-noun queries → entity-linking-aware
    (
        re.compile(
            r"(\b(who|what is|tell me about)\b|について|誰|何)",
            re.IGNORECASE,
        ),
        ["mem0", "hindsight", "json"],
        "entity question → entity-linked backend prioritized",
    ),
    # Semantic / similarity / "find similar"
    (
        re.compile(
            r"(\b(similar|like|same as)\b|類似|似た)",
            re.IGNORECASE,
        ),
        ["hindsight", "mem0", "letta"],
        "similarity query → vector backend prioritized",
    ),
]


class RuleRouter:
    """Pattern-match the query against `rules` (in order, first match wins).

    `rules` is a list of (regex, ordered_backend_preferences, reason).
    If no rule matches, fall back to the default ensemble.
    """

    def __init__(
        self,
        rules: list[tuple[re.Pattern, list[str], str]] | None = None,
        *,
        default_backends: list[str] | None = None,
        default_fusion: str = "rrf",
    ) -> None:
        self.rules = rules or DEFAULT_RULES
        self.default_backends = default_backends or ["mem0", "hindsight", "json"]
        self.default_fusion = default_fusion

    def route(
        self, query: str, *, available_backends: list[str]
    ) -> RouteDecision:
        for pattern, preferred, reason in self.rules:
            if pattern.search(query):
                # Filter to actually available backends, preserving rule order
                chosen = [b for b in preferred if b in available_backends]
                if chosen:
                    return RouteDecision(
                        backends=chosen,
                        fusion=self.default_fusion,  # type: ignore[arg-type]
                        reason=reason,
                        confidence=0.85,
                    )
        # Fallback
        chosen_default = [b for b in self.default_backends if b in available_backends]
        if not chosen_default:
            chosen_default = available_backends[:3]
        return RouteDecision(
            backends=chosen_default,
            fusion=self.default_fusion,  # type: ignore[arg-type]
            reason="no specific rule matched — using default ensemble",
            confidence=0.5,
        )


# --- LLM-based router (most accurate, costs one LLM call) -------------------

class LLMRouter:
    """Use the LLM to classify the query and pick a route.

    Args:
        llm:          a praxia.LLM instance to use for classification
        candidate_backends: list of backend names available to choose from
        default_fusion:     fusion mode (passed through unmodified)
    """

    def __init__(
        self,
        llm: Any,
        *,
        default_fusion: str = "rrf",
    ) -> None:
        self.llm = llm
        self.default_fusion = default_fusion

    def route(
        self, query: str, *, available_backends: list[str]
    ) -> RouteDecision:
        import json as _json

        prompt = (
            "You are a memory-system query router. Given a user query and a "
            "list of available memory backends, choose 1–3 backends most likely "
            "to contain the answer. Reply ONLY with JSON.\n\n"
            f"AVAILABLE BACKENDS: {', '.join(available_backends)}\n\n"
            "BACKEND SPECIALTIES:\n"
            "  mem0      — entity linking, hybrid semantic search\n"
            "  zep       — temporal knowledge graph (time-axis queries)\n"
            "  hindsight — generic vector search\n"
            "  langmem   — namespaced semantic memory\n"
            "  letta     — shared blocks\n"
            "  json      — append-only audit trail (exact recall)\n\n"
            f"USER QUERY: {query}\n\n"
            'OUTPUT JSON: {"backends": [...], "reason": "..."}'
        )
        try:
            response = self.llm.complete(
                [{"role": "user", "content": prompt}],
                response_format="json",
            )
            data = _json.loads(response.text)
            chosen = [b for b in data.get("backends", []) if b in available_backends]
            if not chosen:
                chosen = available_backends[:2]
            return RouteDecision(
                backends=chosen,
                fusion=self.default_fusion,  # type: ignore[arg-type]
                reason="LLM-routed: " + data.get("reason", ""),
                confidence=0.9,
            )
        except Exception as e:
            return RouteDecision(
                backends=available_backends[:2],
                fusion=self.default_fusion,  # type: ignore[arg-type]
                reason=f"LLM routing failed ({e}); fallback to first 2 backends",
                confidence=0.4,
            )


# --- Hybrid backend that uses a router internally ---------------------------

class RoutedBackend:
    """A `MemoryBackend` that consults a router on each search.

    Wraps a dict of `name -> backend` and a `MemoryRouter`. Reads dispatch
    via the router. Writes go to the configured write_target.

    Example:
        from praxia.memory.router import RoutedBackend, RuleRouter
        from praxia.memory.backends import load_backend

        rb = RoutedBackend(
            backends={
                "mem0": load_backend("mem0"),
                "zep": load_backend("zep"),
                "json": load_backend("json"),
            },
            router=RuleRouter(),
            write_to="mem0",
        )
        pm = PersonalMemory(user_id="alice", backend=rb)
    """

    def __init__(
        self,
        backends: dict[str, MemoryBackend],
        *,
        router: MemoryRouter,
        write_to: str,
    ) -> None:
        if write_to not in backends:
            raise ValueError(f"write_to {write_to!r} not in backends {list(backends)}")
        self._backends = backends
        self._router = router
        self._write_to = write_to

    @property
    def name(self) -> str:
        return f"routed[{','.join(self._backends)}]"

    def search(self, *, user_id: str, query: str, limit: int):
        decision = self._router.route(query, available_backends=list(self._backends))
        # If only one backend chosen, run it directly. Otherwise fuse via composite.
        if len(decision.backends) == 1:
            return self._backends[decision.backends[0]].search(
                user_id=user_id, query=query, limit=limit
            )
        # Fan out + RRF fuse via CompositeBackend
        from praxia.memory.composite import CompositeBackend, WeightedBackend

        composite = CompositeBackend(
            backends=[
                WeightedBackend(name=name, backend=self._backends[name])
                for name in decision.backends
            ],
            fusion=decision.fusion,  # type: ignore[arg-type]
        )
        return composite.search(user_id=user_id, query=query, limit=limit)

    def add(self, *, user_id, text, kind, metadata):
        return self._backends[self._write_to].add(
            user_id=user_id, text=text, kind=kind, metadata=metadata
        )

    def all(self, *, user_id=None):
        # Union of all
        seen = {}
        for b in self._backends.values():
            try:
                for rec in b.all(user_id=user_id):
                    if rec.id not in seen:
                        seen[rec.id] = rec
            except Exception:
                continue
        return list(seen.values())

    def clear(self, *, user_id=None):
        for b in self._backends.values():
            try:
                b.clear(user_id=user_id)
            except Exception:
                continue


__all__ = ["RouteDecision", "MemoryRouter", "RuleRouter", "LLMRouter", "RoutedBackend"]
