"""Sleep-time consolidator — Layer 2 of the 5-layer stack.

Periodic batch process that:
  1. Reads recent personal-memory entries.
  2. Groups them into pattern candidates.
  3. Runs each candidate through the PromotionEngine.
  4. Auto-promotes high-confidence candidates to SharedMemory.
  5. Files medium-confidence candidates into a review queue.

Runs daily/nightly. Idempotent — safe to re-run.
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from agentloom.core.llm import LLM
from agentloom.memory.personal import MemoryEntry, PersonalMemory
from agentloom.memory.promoter import PromotionEngine, PromotionVerdict
from agentloom.memory.shared import SharedMemory


@dataclass
class ConsolidationReport:
    candidates_evaluated: int
    auto_promoted: int
    review_queued: int
    skipped: int
    verdicts: list[dict[str, Any]]


class SleepTimeConsolidator:
    def __init__(
        self,
        *,
        personal: PersonalMemory | None,
        shared: SharedMemory | None,
        llm: LLM,
        threshold: float = 0.75,
        review_dir: Path | str = ".agentloom/review_queue",
    ) -> None:
        self.personal = personal
        self.shared = shared
        self.engine = PromotionEngine(llm=llm, auto_threshold=threshold)
        self.review_dir = Path(review_dir)
        self.review_dir.mkdir(parents=True, exist_ok=True)

    def run(self, *, dry_run: bool = False) -> dict[str, Any]:
        if not self.personal:
            return {"error": "personal memory disabled"}

        entries = self.personal.all_entries()
        candidates = self._cluster_candidates(entries)

        report = ConsolidationReport(
            candidates_evaluated=len(candidates),
            auto_promoted=0,
            review_queued=0,
            skipped=0,
            verdicts=[],
        )

        for candidate_text, contributors in candidates:
            verdict = self.engine.evaluate(
                candidate_text=candidate_text,
                contributors=contributors,
                total_users=max(len(set(contributors)), 1),
                outcome_correlation=None,
            )
            report.verdicts.append(asdict(verdict))

            if dry_run:
                continue

            if verdict.decision == "auto_promote" and self.shared:
                self.shared.upsert(
                    label=self._derive_label(candidate_text),
                    description="Auto-promoted from personal memory",
                    value=candidate_text,
                    promoted_from=verdict.contributing_users,
                )
                report.auto_promoted += 1
            elif verdict.decision == "review":
                self._enqueue_review(verdict)
                report.review_queued += 1
            else:
                report.skipped += 1

        return asdict(report)

    @staticmethod
    def _cluster_candidates(
        entries: list[MemoryEntry],
    ) -> list[tuple[str, list[str]]]:
        """Group entries by 'kind' and a coarse keyword bucket.

        This is intentionally simple — production deployments should swap in
        a clustering pass over embeddings (e.g., HDBSCAN over OpenAI/Voyage
        embeddings) before promotion-engine evaluation.
        """
        buckets: dict[tuple[str, str], list[MemoryEntry]] = defaultdict(list)
        for entry in entries:
            key_term = next(
                (
                    word
                    for word in entry.text.split()
                    if len(word) > 5 and word.isalnum()
                ),
                "misc",
            )
            buckets[(entry.kind, key_term.lower())].append(entry)

        candidates: list[tuple[str, list[str]]] = []
        for (_kind, _term), group in buckets.items():
            if len(group) < 2:
                continue
            text = "\n".join(e.text for e in group[:5])
            contributors = [e.user_id for e in group]
            candidates.append((text, contributors))
        return candidates

    @staticmethod
    def _derive_label(text: str) -> str:
        first_line = text.splitlines()[0] if text else "candidate"
        words = [w for w in first_line.split() if w.isalnum()][:3]
        return ("_".join(words) or "candidate").lower()

    def _enqueue_review(self, verdict: PromotionVerdict) -> None:
        path = self.review_dir / f"{int(time.time() * 1000)}.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(asdict(verdict), f, ensure_ascii=False, indent=2)
