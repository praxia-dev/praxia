"""Shared memory layer (Layer 3).

Letta-style "shared memory blocks" — labeled chunks of organizational knowledge
that all agents read and selectively write. Each block has an access policy
(`read_write` | `read_only`) so policy-style content can't be mutated by agents.

alpha26+ adds bitemporal-lite storage on top of the original "latest-wins"
semantics:

  * Every block records ``valid_from`` (when this fact became true) and
    ``valid_to`` (when it was superseded; ``None`` while it's current).
  * Updating a label no longer overwrites in place — it marks the
    previous block as superseded and appends the new one. The
    supersede chain is preserved for ``as_of`` queries.
  * ``search`` and ``get_by_label`` return only currently-valid blocks
    by default (``valid_to is None``); ``as_of(ts)`` returns the block
    that was active at the given timestamp.

The motivation is the L1-bench finding in
``real_hermes_l0_verification.md``: append-only / memory-first caches
go stale at 100% after a fact updates, while bitemporal + supersede +
freshness drops staleness to 0%. The full Graphiti / Neo4j flavour is
overkill for Praxia's local-first profile; this lite version captures
the essential property — "you can always look up what we used to
believe" — without the graph backend.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

AccessMode = Literal["read_write", "read_only"]


@dataclass
class SharedBlock:
    id: str
    label: str
    description: str
    value: str
    access: AccessMode = "read_write"
    promoted_from: list[str] = field(default_factory=list)  # contributing user IDs
    promoted_at: float = field(default_factory=time.time)
    metadata: dict[str, str] = field(default_factory=dict)
    # ── alpha26+ bitemporal-lite ──────────────────────────────────
    # When this fact became true. Mirrors promoted_at for newly-
    # inserted blocks, but kept separate so it can be backdated by
    # an ingester (e.g. "this policy was effective 2024-01-01").
    valid_from: float = field(default_factory=time.time)
    # When this fact was superseded. None while the block is the
    # currently-active version for its label.
    valid_to: float | None = None
    # id of the block this one replaces (the previous version of the
    # same label). None for the very first version.
    supersedes: str | None = None
    # id of the block that has replaced this one. Mirror of supersedes
    # so we can walk the chain in either direction without rebuilding
    # an index. None while this block is still current.
    superseded_by: str | None = None
    # Number of distinct contributing users at promotion time —
    # captured here so conflict arbitration in search() can use it
    # without re-querying the promoter.
    source_count: int = 1
    # 0..1 score from the external verifier at promotion time, or
    # None when no verifier was wired in. Higher = stronger evidence
    # the fact is true. Used as a tie-breaker in conflict resolution.
    verification_score: float | None = None


class SharedMemory:
    """Organizational shared memory blocks (Layer 3 of the 5-layer stack)."""

    def __init__(self, org_id: str, storage_dir: Path) -> None:
        self.org_id = org_id
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.storage_dir / f"{org_id}.jsonl"

    def upsert(
        self,
        *,
        label: str,
        description: str,
        value: str,
        access: AccessMode = "read_write",
        promoted_from: list[str] | None = None,
        source_count: int | None = None,
        verification_score: float | None = None,
        valid_from: float | None = None,
    ) -> SharedBlock:
        """Create or supersede the block for ``label``.

        alpha26+ semantics: if an active block already exists for this
        label, it is NOT overwritten in place. Instead:

          1. The existing block's ``valid_to`` is set to ``now`` and
             ``superseded_by`` is set to the new block's id.
          2. A brand-new block is appended with ``supersedes`` pointing
             at the predecessor.

        The supersede chain is preserved for ``as_of()`` queries and
        for audit (someone asks "what did we say about X last quarter?").
        Read-only blocks (e.g. policy text) still raise on attempts to
        supersede them — same protection as before.
        """
        existing = self.get_by_label(label)
        now = time.time()

        if existing is not None and existing.access == "read_only":
            raise PermissionError(
                f"Block '{label}' is read-only; cannot supersede."
            )

        new_block = SharedBlock(
            id=str(uuid.uuid4()),
            label=label,
            description=description,
            value=value,
            access=access,
            promoted_from=(
                promoted_from
                if promoted_from is not None
                else (existing.promoted_from if existing else [])
            ),
            promoted_at=now,
            valid_from=valid_from if valid_from is not None else now,
            valid_to=None,
            supersedes=existing.id if existing else None,
            source_count=(
                int(source_count)
                if source_count is not None
                else (existing.source_count if existing else 1)
            ),
            verification_score=verification_score,
        )

        all_blocks = self.list_all_including_superseded()
        if existing is not None:
            # Mutate the old block's valid_to + superseded_by.
            for b in all_blocks:
                if b.id == existing.id:
                    b.valid_to = now
                    b.superseded_by = new_block.id
                    break
        all_blocks.append(new_block)
        self._save_all(all_blocks)
        return new_block

    def get_by_label(self, label: str) -> SharedBlock | None:
        """Return the currently-active block for the given label, or
        None if no active block exists. Superseded versions are NOT
        returned — use ``as_of`` to reach into history."""
        for block in self.list_all():
            if block.label == label:
                return block
        return None

    def list_all(self) -> list[SharedBlock]:
        """Return every currently-active (non-superseded) block. This
        is what ``search`` and ``get_by_label`` use by default."""
        return [b for b in self.list_all_including_superseded() if b.valid_to is None]

    def list_all_including_superseded(self) -> list[SharedBlock]:
        """Return every block ever stored, including superseded
        history. Used by ``as_of`` and by the supersede mutator."""
        if not self.path.exists():
            return []
        out: list[SharedBlock] = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    out.append(SharedBlock(**json.loads(line)))
                except (json.JSONDecodeError, TypeError):
                    # TypeError catches "unexpected keyword argument"
                    # when an old-schema block is read on a new-schema
                    # codebase. We silently drop in that case rather
                    # than crash startup — the next upsert will
                    # rewrite the file in the new schema.
                    continue
        return out

    def as_of(self, timestamp: float, *, label: str | None = None) -> list[SharedBlock]:
        """Return the blocks that were active at ``timestamp``.

        A block is "active at t" when ``valid_from <= t < (valid_to or
        +inf)``. Useful for reproducing what the org "knew" at a past
        point — e.g. when auditing an agent's past decision.
        """
        out: list[SharedBlock] = []
        for b in self.list_all_including_superseded():
            if b.valid_from > timestamp:
                continue
            if b.valid_to is not None and b.valid_to <= timestamp:
                continue
            if label is not None and b.label != label:
                continue
            out.append(b)
        return out

    def search(
        self,
        *,
        query: str,
        limit: int = 5,
        as_of: float | None = None,
    ) -> list[str]:
        """Score active blocks against the query. When ``as_of`` is
        given, search the history at that timestamp instead of "now".

        alpha26+ scoring combines:
          * keyword overlap (the original signal)
          * recency: newer ``valid_from`` wins ties
          * verification: blocks promoted with a verifier score > 0
            outrank unverified blocks
          * source breadth: blocks with more contributing users beat
            single-source blocks at the same keyword score

        This is the "recency × provenance × verification" rule from
        ``real_hermes_l0_verification.md`` §2.3 — silently picking the
        newest match is exactly what produces silent_wrong=100% in
        the L1 bench. We make verification + source breadth co-equal
        tie-breakers so a stale-but-verified fact beats a fresh-but-
        unverified one when the keyword score is the same.
        """
        pool = (
            self.list_all()
            if as_of is None
            else self.as_of(as_of)
        )
        terms = {t.lower() for t in query.split() if len(t) > 2}
        scored: list[tuple[tuple[int, float, float, int, float], SharedBlock]] = []
        for block in pool:
            haystack = (block.label + " " + block.description + " " + block.value).lower()
            kw_score = sum(1 for t in terms if t in haystack)
            if kw_score == 0:
                continue
            # Tie-break tuple, sorted desc: (kw_score, verification,
            # source_breadth, source_count, recency).
            ver = float(block.verification_score or 0.0)
            breadth = 1.0 if block.source_count >= 2 else 0.0
            scored.append((
                (kw_score, ver, breadth, block.source_count, block.valid_from),
                block,
            ))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [f"[{b.label}] {b.value}" for _, b in scored[: max(1, int(limit))]]

    def append_to_block(self, label: str, addition: str) -> SharedBlock:
        """Append text to a block. Behaves like an upsert in the
        bitemporal sense — the previous block is superseded, a new
        block (with the concatenated value) is created. The full
        text is materialised at promotion time so downstream readers
        don't need to reconstruct from a chain of patches."""
        block = self.get_by_label(label)
        if not block:
            return self.upsert(label=label, description=label, value=addition)
        if block.access == "read_only":
            raise PermissionError(f"Block '{label}' is read-only.")
        return self.upsert(
            label=label,
            description=block.description,
            value=block.value + "\n" + addition,
            access=block.access,
            promoted_from=block.promoted_from,
            source_count=block.source_count,
            verification_score=block.verification_score,
        )

    def _save_all(self, blocks: list[SharedBlock]) -> None:
        with self.path.open("w", encoding="utf-8") as f:
            for block in blocks:
                f.write(json.dumps(asdict(block), ensure_ascii=False) + "\n")

    def remove(self, label: str) -> None:
        """Remove every version of a label, including superseded
        history. Use sparingly — for most operational needs you want
        ``upsert`` (which preserves the audit trail) instead."""
        kept = [
            b for b in self.list_all_including_superseded() if b.label != label
        ]
        self._save_all(kept)
