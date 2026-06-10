"""Promotion engine — decides whether a personal-memory candidate should be
promoted to the shared/organizational layer.

Three independent verdicts run in parallel (research-backed design):
    1. FREQUENCY  — pattern recurs across N+ users / sessions.
    2. OUTCOME    — pattern correlates with measured outcomes (e.g., wins).
    3. SELF_EVAL  — LLM scores the candidate on a 0..1 scale for "org-knowledge".

The final score is a weighted blend; threshold selects auto-promote vs review.

alpha26+ hardened mode (gated by ``require_verification`` and
``min_independent_sources``) adds two **hard pre-conditions** that
short-circuit the score blend entirely:

  * **External verification gate**: if a verifier callback is wired in
    and returns ``passed=False`` for the candidate, the verdict is
    immediately ``"skip"`` regardless of how high freq/outcome/self_eval
    score. This is the L2-bench finding from
    ``real_hermes_l0_verification.md`` — promotions weighted on
    self-evaluation collapse into "always answer / wrong" reward
    hacking. An external check (grounding gate, outcome verification,
    multi-source consistency) is the only signal that doesn't bias
    toward the model's own confidence.

  * **Independent-source minimum**: auto-promote requires at least
    ``min_independent_sources`` distinct contributors (default 2).
    A single-user pattern can still reach the *review* tier but never
    auto-promote. This is the L3-bench finding — single-source
    promotions of plausible-but-wrong facts contaminate the shared
    layer at 100% in unguarded mode; two independent confirmations
    block contamination structurally.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from praxia.core.llm import LLM


# Verifier signature: receives the candidate text + verdict-in-progress
# (so the gate can look at contributors / outcome correlation if it
# wants) and returns (passed, reason). Returns True/empty for "no
# verifier wired in" (preserves pre-alpha26 behaviour).
VerifierCallable = Callable[[str, "PromotionVerdict"], tuple[bool, str]]


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
    # alpha26+: verification gate outcome. None when no verifier was
    # configured (pre-alpha26 behaviour). True/False otherwise.
    verification_passed: bool | None = None
    verification_reason: str = ""
    # alpha26+: number of distinct contributors after deduplication.
    # Auto-promote requires >= min_independent_sources.
    independent_source_count: int = 0


class PromotionEngine:
    """Compute a promotion verdict for a candidate memory.

    Weights are (frequency, outcome, self_eval). Default favours external
    signals — frequency across users and measured outcome — and uses the
    LLM self-evaluation only as a tie-breaker.

    Rationale: multi-hop RAG / external-verification benchmarks
    (HotpotQA, SQuAD v2) show that LLM self-evaluation is biased toward
    its own outputs (self-preference bias) and cannot reliably grade
    correctness on its own. Promotion decisions therefore lean on
    independent signals — recurrence across users and outcome
    correlation when available — and only use self_eval to break ties
    when those are inconclusive. See `agentic_rag_verification_lessons.md`
    in the project's memory, principle K4.
    """

    # Old default was (0.4, 0.3, 0.3); reweighted so self_eval cannot
    # carry a verdict on its own when outcome data is absent.
    DEFAULT_WEIGHTS: tuple[float, float, float] = (0.5, 0.4, 0.1)

    def __init__(
        self,
        llm: LLM,
        *,
        weights: tuple[float, float, float] | None = None,
        auto_threshold: float = 0.75,
        review_threshold: float = 0.5,
        verifier: VerifierCallable | None = None,
        min_independent_sources: int = 2,
        require_verification: bool = False,
    ) -> None:
        self.llm = llm
        w = weights if weights is not None else self.DEFAULT_WEIGHTS
        self.weight_freq, self.weight_outcome, self.weight_self = w
        self.auto_threshold = auto_threshold
        self.review_threshold = review_threshold
        # alpha26+ verification gate.
        # - verifier=None  → no gate (pre-alpha26 behaviour preserved).
        # - verifier=<fn>  → fn is called with (candidate_text, verdict);
        #   if it returns passed=False the verdict is immediately "skip".
        # require_verification=True flips the gate: when no verifier is
        # configured, every candidate is rejected. Use this in
        # production deployments where the operator wants to be sure
        # no candidate slips past unverified.
        self.verifier = verifier
        self.require_verification = require_verification
        # auto_promote requires >= this many *distinct* contributing
        # users. Default 2 — the L3 bench shows 1-source promotions
        # contaminate the shared layer near-100%. Tests that don't
        # care about this constraint should explicitly pass 1.
        self.min_independent_sources = max(1, int(min_independent_sources))

    def evaluate(
        self,
        candidate_text: str,
        *,
        contributors: list[str],
        total_users: int,
        outcome_correlation: float | None = None,
    ) -> PromotionVerdict:
        unique_contributors = len(set(contributors))
        verdict = PromotionVerdict(
            candidate_text=candidate_text,
            contributing_users=contributors,
            independent_source_count=unique_contributors,
        )

        verdict.frequency_score = self._score_frequency(
            unique_contributors, total_users
        )
        if outcome_correlation is not None:
            verdict.outcome_score = max(0.0, min(1.0, outcome_correlation))
        verdict.self_eval_score, verdict.reasoning = self._self_eval(candidate_text)

        verdict.final_score = (
            self.weight_freq * verdict.frequency_score
            + self.weight_outcome * verdict.outcome_score
            + self.weight_self * verdict.self_eval_score
        )

        # alpha26+ external verification gate. Runs BEFORE the
        # auto/review threshold check so a failed verifier short-circuits
        # the verdict to "skip" no matter how high the blended score is.
        # See class docstring for the L2/L3 evidence motivating this.
        if self.verifier is not None:
            try:
                passed, reason = self.verifier(candidate_text, verdict)
            except Exception as e:  # pragma: no cover
                passed, reason = False, f"verifier raised: {e}"
            verdict.verification_passed = bool(passed)
            verdict.verification_reason = str(reason or "")
        elif self.require_verification:
            verdict.verification_passed = False
            verdict.verification_reason = (
                "require_verification=True but no verifier was wired in"
            )

        # Gate 1: verification must not have explicitly failed.
        if verdict.verification_passed is False:
            verdict.decision = "skip"
            return verdict

        # Score-based tier selection.
        if verdict.final_score >= self.auto_threshold:
            tentative_decision = "auto_promote"
        elif verdict.final_score >= self.review_threshold:
            tentative_decision = "review"
        else:
            tentative_decision = "skip"

        # Gate 2: independent-source minimum applies to auto_promote
        # only. A single-source pattern can reach review (a human looks
        # at it) but never auto-promotes into the shared layer.
        if (
            tentative_decision == "auto_promote"
            and unique_contributors < self.min_independent_sources
        ):
            tentative_decision = "review"

        verdict.decision = tentative_decision
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
