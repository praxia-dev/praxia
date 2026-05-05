"""Multi-backend composite memory — query several LTMs in parallel and
fuse the results.

The intuition: each backend has different strengths (Mem0 for entity
linking, Zep for temporal KG, JSON for audit trail, HindSight for vector
search). Querying them in parallel and merging recalls more relevant
results than any single one would.

Fusion strategies:

    - "rrf"           — Reciprocal Rank Fusion (default, robust, no
                         score normalization needed)
    - "union"         — concatenate all results, deduplicate by id, keep
                         the rank from the backend that found it earliest
    - "intersection"  — keep only items that appear in N backends (N >= min_agreement)
    - "weighted"      — weighted sum of normalized scores (requires per-
                         backend weights)
    - "llm_rerank"    — query the LLM to rerank a candidate pool (most
                         accurate, slowest)

References:
    Cormack et al. (2009) "Reciprocal Rank Fusion outperforms Condorcet
    and individual Rank Learning Methods" — SIGIR. RRF is the simple,
    score-agnostic baseline that beats many learned methods.
"""
from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable, Literal

from praxia.memory.backends import MemoryBackend, MemoryRecord

FusionStrategy = Literal["rrf", "union", "intersection", "weighted", "llm_rerank"]


@dataclass
class WeightedBackend:
    """A backend with a configurable weight for fusion."""
    name: str
    backend: MemoryBackend
    weight: float = 1.0


class CompositeBackend:
    """A `MemoryBackend` that delegates to several backends in parallel.

    Reads (`search`, `all`) fan out to all backends and merge results.
    Writes (`add`) go to the **first** backend by default (write-through);
    pass `write_to=` to choose differently.

    Example:
        from praxia.memory.composite import CompositeBackend, WeightedBackend
        from praxia.memory.backends import load_backend

        composite = CompositeBackend(
            backends=[
                WeightedBackend("mem0", load_backend("mem0"), weight=1.5),
                WeightedBackend("zep", load_backend("zep"), weight=1.0),
                WeightedBackend("json", load_backend("json"), weight=0.5),
            ],
            fusion="rrf",
        )

        pm = PersonalMemory(user_id="alice", backend=composite)
    """

    def __init__(
        self,
        backends: list[WeightedBackend | MemoryBackend],
        *,
        fusion: FusionStrategy = "rrf",
        write_to: str | None = None,
        min_agreement: int = 2,
        rrf_k: int = 60,
        max_workers: int = 6,
        rerank_fn: Callable[[str, list[MemoryRecord]], list[MemoryRecord]] | None = None,
    ) -> None:
        # Normalize input — accept bare backends or WeightedBackend instances
        self.weighted: list[WeightedBackend] = []
        for i, b in enumerate(backends):
            if isinstance(b, WeightedBackend):
                self.weighted.append(b)
            else:
                self.weighted.append(WeightedBackend(name=f"backend_{i}", backend=b, weight=1.0))
        self.fusion = fusion
        self.write_to = write_to
        self.min_agreement = min_agreement
        self.rrf_k = rrf_k
        self.max_workers = max_workers
        self._rerank_fn = rerank_fn

    @property
    def name(self) -> str:
        return "composite[" + ",".join(wb.name for wb in self.weighted) + "]"

    # --- Reads (fan-out + fuse) -------------------------------------------

    def search(
        self,
        *,
        user_id: str,
        query: str,
        limit: int,
    ) -> list[MemoryRecord]:
        # Run all backends in parallel
        per_backend: dict[str, list[MemoryRecord]] = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as exec_pool:
            futures = {
                exec_pool.submit(
                    wb.backend.search, user_id=user_id, query=query, limit=limit
                ): wb
                for wb in self.weighted
            }
            for fut in as_completed(futures):
                wb = futures[fut]
                try:
                    per_backend[wb.name] = fut.result()
                except Exception:
                    # One backend failing shouldn't break the query
                    per_backend[wb.name] = []
        return self._fuse(per_backend, query=query, limit=limit)

    def all(self, *, user_id: str | None = None) -> list[MemoryRecord]:
        # Concatenate all entries; dedupe by id
        seen: dict[str, MemoryRecord] = {}
        for wb in self.weighted:
            try:
                for rec in wb.backend.all(user_id=user_id):
                    if rec.id not in seen:
                        seen[rec.id] = rec
            except Exception:
                continue
        return list(seen.values())

    # --- Writes (single backend, write-through) ----------------------------

    def add(
        self,
        *,
        user_id: str,
        text: str,
        kind: str,
        metadata: dict[str, Any],
    ) -> MemoryRecord:
        target = self._write_target()
        return target.backend.add(
            user_id=user_id, text=text, kind=kind, metadata=metadata
        )

    def clear(self, *, user_id: str | None = None) -> None:
        # Clear ALL backends — destructive but symmetric with the model
        for wb in self.weighted:
            try:
                wb.backend.clear(user_id=user_id)
            except Exception:
                continue

    def _write_target(self) -> WeightedBackend:
        if self.write_to:
            for wb in self.weighted:
                if wb.name == self.write_to:
                    return wb
            raise ValueError(f"Write target {self.write_to!r} not in composite backends")
        return self.weighted[0]

    # --- Fusion -----------------------------------------------------------

    def _fuse(
        self,
        per_backend: dict[str, list[MemoryRecord]],
        *,
        query: str,
        limit: int,
    ) -> list[MemoryRecord]:
        strategy = self.fusion
        if strategy == "union":
            return self._fuse_union(per_backend, limit)
        if strategy == "intersection":
            return self._fuse_intersection(per_backend, limit)
        if strategy == "weighted":
            return self._fuse_weighted(per_backend, limit)
        if strategy == "llm_rerank":
            return self._fuse_llm_rerank(per_backend, query, limit)
        # default
        return self._fuse_rrf(per_backend, limit)

    def _fuse_rrf(
        self,
        per_backend: dict[str, list[MemoryRecord]],
        limit: int,
    ) -> list[MemoryRecord]:
        """Reciprocal Rank Fusion — robust default.

        score(d) = Σ_b weight_b / (k + rank_b(d))
        """
        weight_by_name = {wb.name: wb.weight for wb in self.weighted}
        scores: dict[str, float] = defaultdict(float)
        first_seen: dict[str, MemoryRecord] = {}
        for backend_name, results in per_backend.items():
            w = weight_by_name.get(backend_name, 1.0)
            for rank, rec in enumerate(results, start=1):
                scores[rec.id] += w / (self.rrf_k + rank)
                first_seen.setdefault(rec.id, rec)
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [first_seen[rec_id] for rec_id, _ in ranked[:limit]]

    def _fuse_union(
        self,
        per_backend: dict[str, list[MemoryRecord]],
        limit: int,
    ) -> list[MemoryRecord]:
        """Concatenate; dedupe by id; keep first-seen order."""
        seen: dict[str, MemoryRecord] = {}
        for results in per_backend.values():
            for rec in results:
                if rec.id not in seen:
                    seen[rec.id] = rec
                    if len(seen) >= limit:
                        return list(seen.values())
        return list(seen.values())

    def _fuse_intersection(
        self,
        per_backend: dict[str, list[MemoryRecord]],
        limit: int,
    ) -> list[MemoryRecord]:
        """Keep only items that appear in >= min_agreement backends."""
        counts: dict[str, int] = defaultdict(int)
        first_seen: dict[str, MemoryRecord] = {}
        for results in per_backend.values():
            seen_in_this: set[str] = set()
            for rec in results:
                if rec.id not in seen_in_this:
                    counts[rec.id] += 1
                    seen_in_this.add(rec.id)
                first_seen.setdefault(rec.id, rec)
        kept = [
            first_seen[rid]
            for rid, c in counts.items()
            if c >= self.min_agreement
        ]
        return kept[:limit]

    def _fuse_weighted(
        self,
        per_backend: dict[str, list[MemoryRecord]],
        limit: int,
    ) -> list[MemoryRecord]:
        """Weighted sum of normalized rank scores (per backend)."""
        weight_by_name = {wb.name: wb.weight for wb in self.weighted}
        scores: dict[str, float] = defaultdict(float)
        first_seen: dict[str, MemoryRecord] = {}
        for backend_name, results in per_backend.items():
            w = weight_by_name.get(backend_name, 1.0)
            n = max(len(results), 1)
            for i, rec in enumerate(results):
                # Normalized rank score: 1.0 at top, → 0 at bottom
                normalized = 1.0 - (i / n)
                scores[rec.id] += w * normalized
                first_seen.setdefault(rec.id, rec)
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [first_seen[rid] for rid, _ in ranked[:limit]]

    def _fuse_llm_rerank(
        self,
        per_backend: dict[str, list[MemoryRecord]],
        query: str,
        limit: int,
    ) -> list[MemoryRecord]:
        """LLM-as-judge reranks a deduplicated candidate pool.

        Caller supplies `rerank_fn(query, candidates)`. If absent, falls back
        to RRF — keeps the API non-blocking on optional LLM dep.
        """
        if self._rerank_fn is None:
            return self._fuse_rrf(per_backend, limit)
        # Deduplicate union pool, capped at 3*limit candidates
        seen: dict[str, MemoryRecord] = {}
        for results in per_backend.values():
            for rec in results:
                if rec.id not in seen:
                    seen[rec.id] = rec
        pool = list(seen.values())[: 3 * limit]
        ranked = self._rerank_fn(query, pool)
        return ranked[:limit]
