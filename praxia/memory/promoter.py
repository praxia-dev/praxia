"""Promotion engine — decides whether a personal-memory candidate should be
promoted to the shared/organizational layer.

Three independent verdicts run in parallel (research-backed design):
    1. FREQUENCY  — pattern recurs across N+ users / sessions.
    2. OUTCOME    — pattern correlates with measured outcomes (e.g., wins).
    3. SELF_EVAL  — LLM scores the candidate on a 0..1 scale for "org-knowledge".

The final score is a weighted blend; threshold selects auto-promote vs review.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from praxia.core.llm import LLM


@dataclass
class PromotionVerdict:
    candidate_text: str
    frequency_score: float = 0.0  # 0..1
    outcome_score: float = 0.0  # 0..1, only when outcome data attached
    self_eval_score: float = 0.0  # 0..1, LLM's judgement
    final_score: float = 0.0
    decision: str = "skip"  # "auto_promote" | "review" | "skip"
    reasoning: str = ""
    contributing_users: list[str] = field(default_factory=list)


class PromotionEngine:
    """Compute a promotion verdict for a candidate memory.

    Weights are tunable; defaults give frequency and self-eval most weight,
    outcome only when explicitly available.
    """

    def __init__(
        self,
        llm: LLM,
        *,
        weights: tuple[float, float, float] = (0.4, 0.3, 0.3),
        auto_threshold: float = 0.75,
        review_threshold: float = 0.5,
    ) -> None:
        self.llm = llm
        self.weight_freq, self.weight_outcome, self.weight_self = weights
        self.auto_threshold = auto_threshold
        self.review_threshold = review_threshold

    def evaluate(
        self,
        candidate_text: str,
        *,
        contributors: list[str],
        total_users: int,
        outcome_correlation: float | None = None,
    ) -> PromotionVerdict:
        verdict = PromotionVerdict(
            candidate_text=candidate_text,
            contributing_users=contributors,
        )

        verdict.frequency_score = self._score_frequency(
            len(set(contributors)), total_users
        )
        if outcome_correlation is not None:
            verdict.outcome_score = max(0.0, min(1.0, outcome_correlation))
        verdict.self_eval_score, verdict.reasoning = self._self_eval(candidate_text)

        verdict.final_score = (
            self.weight_freq * verdict.frequency_score
            + self.weight_outcome * verdict.outcome_score
            + self.weight_self * verdict.self_eval_score
        )

        if verdict.final_score >= self.auto_threshold:
            verdict.decision = "auto_promote"
        elif verdict.final_score >= self.review_threshold:
            verdict.decision = "review"
        else:
            verdict.decision = "skip"

        return verdict

    @staticmethod
    def _score_frequency(unique_contributors: int, total_users: int) -> float:
        if total_users <= 0:
            return 0.0
        # Saturating curve: 1 user = 0.0, 3 = 0.6, 5+ = ~1.0
        if unique_contributors <= 1:
            return 0.0
        ratio = unique_contributors / max(total_users, 3)
        return min(1.0, ratio * 1.2)

    def _self_eval(self, candidate_text: str) -> tuple[float, str]:
        prompt = (
            "You are evaluating whether a memory snippet should be promoted from "
            "an individual's memory to the organization's shared knowledge.\n\n"
            "Score on a 0..1 scale on the following criteria:\n"
            "  - generalizable beyond a single person\n"
            "  - non-PII / non-confidential\n"
            "  - actionable for similar future tasks\n\n"
            f"CANDIDATE:\n{candidate_text}\n\n"
            "Return JSON: {\"score\": 0..1, \"reason\": \"...\"}"
        )
        try:
            response = self.llm.complete(
                [{"role": "user", "content": prompt}],
                response_format="json",
            )
            data: dict[str, Any] = json.loads(response.text)
            return float(data.get("score", 0.0)), str(data.get("reason", ""))
        except Exception as e:
            return 0.0, f"self-eval failed: {e}"
