"""Coverage for the alpha26 promotion gate + bitemporal lite layer.

Pins down four behaviours that the L0-L3 verification work in
``real_hermes_l0_verification.md`` proves are load-bearing:

  * a verifier returning ``passed=False`` short-circuits to "skip"
    regardless of how high the freq/outcome/self_eval blend goes,
  * single-source candidates can reach "review" but never auto_promote,
  * upserting an existing label preserves the old block as superseded
    (not overwritten in place), so ``as_of`` can reconstruct history,
  * search ranks verified + multi-source blocks above unverified ones
    at the same keyword score.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from praxia.memory.promoter import PromotionEngine, PromotionVerdict
from praxia.memory.shared import SharedMemory


def _llm_stub(self_eval: float = 0.95):
    """Stand-in LLM that always returns the same self_eval JSON. Keeps
    the verification gate test deterministic — what we care about is
    that gates short-circuit regardless of how confident the LLM
    self-rates."""
    llm = MagicMock()
    response = MagicMock()
    response.text = f'{{"score": {self_eval}, "reason": "stub"}}'
    llm.complete = MagicMock(return_value=response)
    return llm


# ─── Promotion gate ──────────────────────────────────────────────────


class TestVerificationGate:
    def test_verifier_failure_short_circuits_to_skip(self):
        llm = _llm_stub(self_eval=0.99)
        engine = PromotionEngine(
            llm=llm,
            verifier=lambda _text, _v: (False, "groundedness=0.1"),
            min_independent_sources=1,  # only test the verifier gate
        )
        # Stack freq + outcome + self_eval as high as possible so the
        # gate is the ONLY thing that can stop the verdict.
        v = engine.evaluate(
            "a plausible-sounding but unverified fact",
            contributors=["u1", "u2", "u3", "u4", "u5"],
            total_users=5,
            outcome_correlation=1.0,
        )
        assert v.decision == "skip"
        assert v.verification_passed is False
        assert "groundedness" in v.verification_reason
        # The blended score should still be high — we want the test
        # to fail if someone "fixes" this by zeroing the score
        # instead of by gating the decision.
        assert v.final_score >= 0.7

    def test_verifier_pass_lets_strong_candidate_promote(self):
        llm = _llm_stub(self_eval=0.5)
        engine = PromotionEngine(
            llm=llm,
            verifier=lambda _text, _v: (True, "grounded against 3 sources"),
            min_independent_sources=2,
        )
        v = engine.evaluate(
            "a verified org-wide pattern",
            contributors=["u1", "u2", "u3"],
            total_users=3,
            outcome_correlation=1.0,
        )
        assert v.verification_passed is True
        assert v.decision == "auto_promote"

    def test_require_verification_without_verifier_rejects(self):
        """``require_verification=True`` but no verifier wired in
        should fail-closed rather than silently let everything through."""
        llm = _llm_stub(self_eval=0.99)
        engine = PromotionEngine(
            llm=llm,
            require_verification=True,
            min_independent_sources=1,
        )
        v = engine.evaluate(
            "anything at all",
            contributors=["u1"],
            total_users=1,
        )
        assert v.decision == "skip"
        assert v.verification_passed is False


class TestIndependentSourceMinimum:
    def test_single_source_caps_at_review(self):
        llm = _llm_stub(self_eval=0.99)
        engine = PromotionEngine(
            llm=llm,
            min_independent_sources=2,
        )
        # One user, three repeated mentions — still one source.
        v = engine.evaluate(
            "single-source claim",
            contributors=["u1", "u1", "u1"],
            total_users=1,
            outcome_correlation=1.0,
        )
        assert v.independent_source_count == 1
        # Single source can't auto-promote, but high score keeps it
        # in the review pile so a human can decide.
        assert v.decision in {"review", "skip"}
        assert v.decision != "auto_promote"

    def test_two_sources_can_auto_promote(self):
        llm = _llm_stub(self_eval=0.9)
        engine = PromotionEngine(llm=llm, min_independent_sources=2)
        v = engine.evaluate(
            "two-source claim",
            contributors=["u1", "u2"],
            total_users=2,
            outcome_correlation=1.0,
        )
        assert v.independent_source_count == 2
        assert v.decision == "auto_promote"


# ─── Bitemporal SharedMemory ─────────────────────────────────────────


class TestBitemporalSharedMemory:
    def test_upsert_creates_supersede_chain(self, tmp_path: Path):
        shared = SharedMemory("acme", tmp_path)
        a = shared.upsert(
            label="onboarding_url",
            description="link",
            value="https://wiki.example/onboarding-v1",
        )
        b = shared.upsert(
            label="onboarding_url",
            description="link",
            value="https://wiki.example/onboarding-v2",
        )

        # Active query returns only the new one.
        active = shared.list_all()
        assert [x.id for x in active] == [b.id]

        # Full history has both, linked via supersedes.
        all_blocks = shared.list_all_including_superseded()
        assert {x.id for x in all_blocks} == {a.id, b.id}
        old = next(x for x in all_blocks if x.id == a.id)
        new = next(x for x in all_blocks if x.id == b.id)
        assert old.valid_to is not None
        assert old.superseded_by == b.id
        assert new.supersedes == a.id
        assert new.valid_to is None

    def test_as_of_returns_historical_version(self, tmp_path: Path):
        shared = SharedMemory("acme", tmp_path)
        a = shared.upsert(
            label="policy",
            description="d",
            value="value-A",
            valid_from=100.0,
        )
        # Simulate manual valid_from so the test is deterministic
        # without relying on wall-clock spacing.
        all_blocks = shared.list_all_including_superseded()
        for b in all_blocks:
            if b.id == a.id:
                b.valid_to = 200.0
                b.superseded_by = "new-id"
        shared._save_all(all_blocks)
        # Now inject a successor that's valid_from=200.
        all_blocks = shared.list_all_including_superseded()
        from praxia.memory.shared import SharedBlock
        succ = SharedBlock(
            id="new-id",
            label="policy",
            description="d",
            value="value-B",
            promoted_from=[],
            valid_from=200.0,
            valid_to=None,
            supersedes=a.id,
        )
        all_blocks.append(succ)
        shared._save_all(all_blocks)

        # Active reads see value-B.
        assert shared.get_by_label("policy").value == "value-B"
        # as_of mid-A-window returns value-A.
        snap = shared.as_of(150.0, label="policy")
        assert len(snap) == 1
        assert snap[0].value == "value-A"
        # as_of mid-B-window returns value-B.
        snap = shared.as_of(250.0, label="policy")
        assert len(snap) == 1
        assert snap[0].value == "value-B"

    def test_search_prefers_verified_multi_source(self, tmp_path: Path):
        shared = SharedMemory("acme", tmp_path)
        # Two blocks contain the same keyword. One is single-source +
        # unverified; the other is two-source + verified. The verified
        # one should sort first.
        shared.upsert(
            label="claim_unverified",
            description="lone user said tofu is dangerous",
            value="tofu is dangerous",
            promoted_from=["u1"],
            source_count=1,
            verification_score=None,
        )
        shared.upsert(
            label="claim_verified",
            description="study says tofu is safe in moderation",
            value="tofu is safe in moderation",
            promoted_from=["u1", "u2", "u3"],
            source_count=3,
            verification_score=1.0,
        )
        hits = shared.search(query="tofu", limit=2)
        # Both should be present (same keyword score = 1), but the
        # verified + multi-source one ranks first.
        assert len(hits) == 2
        assert "safe" in hits[0]
        assert "dangerous" in hits[1]
