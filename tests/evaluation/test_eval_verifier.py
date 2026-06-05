"""Unit tests for praxia.agent.verifier.

Uses a mock LLM that returns canned JSON so tests are deterministic and
require no API key.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from praxia.agent.verifier import (
    ClaimScore,
    LLMGroundingVerifier,
    Source,
    Verdict,
    Verifier,
)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


@dataclass
class _MockResponse:
    text: str
    usage: dict[str, int]


class _MockLLM:
    """Returns a queued sequence of JSON strings; records call count."""

    def __init__(self, *replies: str) -> None:
        self._queue = list(replies)
        self.calls: list[list[dict[str, Any]]] = []

    def complete(self, messages: list[dict[str, Any]], **_kw: Any) -> _MockResponse:
        self.calls.append(messages)
        if not self._queue:
            raise RuntimeError("MockLLM out of replies")
        return _MockResponse(text=self._queue.pop(0), usage={"prompt_tokens": 50, "completion_tokens": 50})


def _sources(*pairs: tuple[str, str]) -> list[Source]:
    return [Source(id=sid, text=text) for sid, text in pairs]


# ---------------------------------------------------------------------------
# Verdict structure / dataclass behaviour
# ---------------------------------------------------------------------------


class TestVerdictDataclass:
    def test_verdict_carries_per_claim(self):
        v = Verdict(
            groundedness=0.8,
            per_claim=[ClaimScore(claim="x", score=0.8)],
            unsupported_claims=[],
            decision="accept",
        )
        assert v.per_claim[0].claim == "x"
        assert v.decision == "accept"

    def test_protocol_is_satisfied_by_default_impl(self):
        # Static-like check: instance is a Verifier
        v = LLMGroundingVerifier(llm=_MockLLM())
        assert isinstance(v, Verifier)


# ---------------------------------------------------------------------------
# Short-circuit paths (no LLM call)
# ---------------------------------------------------------------------------


class TestShortCircuit:
    def test_empty_draft_abstains_without_llm_call(self):
        llm = _MockLLM()  # no replies — would error if called
        v = LLMGroundingVerifier(llm=llm)
        verdict = v.verify("", sources=_sources(("s1", "anything")))
        assert verdict.decision == "abstain"
        assert verdict.groundedness == 0.0
        assert llm.calls == []  # never called

    def test_whitespace_draft_abstains(self):
        v = LLMGroundingVerifier(llm=_MockLLM())
        verdict = v.verify("   \n\t ", sources=_sources(("s1", "x")))
        assert verdict.decision == "abstain"

    def test_no_sources_abstains_without_llm_call(self):
        llm = _MockLLM()
        v = LLMGroundingVerifier(llm=llm)
        verdict = v.verify("The customer wants ROI focus.", sources=[])
        assert verdict.decision == "abstain"
        assert "No sources" in verdict.rationale
        assert llm.calls == []


# ---------------------------------------------------------------------------
# JSON parsing tolerance
# ---------------------------------------------------------------------------


class TestJsonParsing:
    def test_strips_json_code_fence(self):
        reply = "```json\n" + json.dumps(
            {"claims": [{"claim": "fact A", "score": 0.9, "supporting_ids": ["s1"]}]}
        ) + "\n```"
        v = LLMGroundingVerifier(llm=_MockLLM(reply))
        verdict = v.verify("fact A.", sources=_sources(("s1", "fact A is documented")))
        assert verdict.groundedness == pytest.approx(0.9)
        assert verdict.decision == "accept"

    def test_strips_plain_code_fence(self):
        reply = "```\n" + json.dumps({"claims": [{"claim": "X", "score": 0.8, "supporting_ids": ["s1"]}]}) + "\n```"
        v = LLMGroundingVerifier(llm=_MockLLM(reply))
        verdict = v.verify("X.", sources=_sources(("s1", "X is true")))
        assert verdict.decision == "accept"

    def test_extracts_json_from_prose_wrapper(self):
        reply = "Sure, here is the analysis:\n" + json.dumps(
            {"claims": [{"claim": "alpha", "score": 0.85, "supporting_ids": ["s1"]}]}
        ) + "\nLet me know if you need more."
        v = LLMGroundingVerifier(llm=_MockLLM(reply))
        verdict = v.verify("alpha.", sources=_sources(("s1", "alpha holds")))
        assert verdict.decision == "accept"

    def test_unparseable_json_yields_abstain(self):
        v = LLMGroundingVerifier(llm=_MockLLM("not json at all"))
        verdict = v.verify("anything", sources=_sources(("s1", "x")))
        assert verdict.decision == "abstain"
        assert verdict.per_claim == []

    def test_missing_claims_key_yields_abstain(self):
        v = LLMGroundingVerifier(llm=_MockLLM(json.dumps({"foo": "bar"})))
        verdict = v.verify("anything", sources=_sources(("s1", "x")))
        assert verdict.decision == "abstain"

    def test_non_list_claims_field_tolerated(self):
        v = LLMGroundingVerifier(llm=_MockLLM(json.dumps({"claims": "not a list"})))
        verdict = v.verify("anything", sources=_sources(("s1", "x")))
        assert verdict.decision == "abstain"


# ---------------------------------------------------------------------------
# Per-claim parsing edge cases
# ---------------------------------------------------------------------------


class TestClaimParsing:
    def test_invalid_score_defaults_to_zero(self):
        reply = json.dumps({"claims": [
            {"claim": "x", "score": "garbage", "supporting_ids": ["s1"]},
            {"claim": "y", "score": 1.0, "supporting_ids": ["s1"]},
        ]})
        v = LLMGroundingVerifier(llm=_MockLLM(reply))
        verdict = v.verify("x and y", sources=_sources(("s1", "y")))
        assert verdict.per_claim[0].score == 0.0
        assert verdict.per_claim[1].score == 1.0

    def test_score_clamped_to_unit_interval(self):
        reply = json.dumps({"claims": [
            {"claim": "high", "score": 5.0, "supporting_ids": []},
            {"claim": "low", "score": -2.0, "supporting_ids": []},
        ]})
        v = LLMGroundingVerifier(llm=_MockLLM(reply))
        verdict = v.verify("x", sources=_sources(("s1", "s1")))
        assert verdict.per_claim[0].score == 1.0
        assert verdict.per_claim[1].score == 0.0

    def test_empty_claim_text_is_skipped(self):
        reply = json.dumps({"claims": [
            {"claim": "", "score": 0.9, "supporting_ids": []},
            {"claim": "real", "score": 0.9, "supporting_ids": ["s1"]},
        ]})
        v = LLMGroundingVerifier(llm=_MockLLM(reply))
        verdict = v.verify("real", sources=_sources(("s1", "real")))
        assert len(verdict.per_claim) == 1
        assert verdict.per_claim[0].claim == "real"

    def test_non_string_supporting_ids_become_strings(self):
        reply = json.dumps({"claims": [
            {"claim": "x", "score": 0.8, "supporting_ids": [1, "s2", None]},
        ]})
        v = LLMGroundingVerifier(llm=_MockLLM(reply))
        verdict = v.verify("x", sources=_sources(("1", "y"), ("s2", "y")))
        # None is filtered out; 1 becomes "1"
        assert verdict.per_claim[0].supporting_ids == ["1", "s2"]


# ---------------------------------------------------------------------------
# Decision aggregation
# ---------------------------------------------------------------------------


class TestDecisionAggregation:
    def test_high_groundedness_accepts(self):
        reply = json.dumps({"claims": [
            {"claim": "a", "score": 0.9, "supporting_ids": ["s1"]},
            {"claim": "b", "score": 0.85, "supporting_ids": ["s2"]},
        ]})
        v = LLMGroundingVerifier(llm=_MockLLM(reply))
        verdict = v.verify("a. b.", sources=_sources(("s1", "a"), ("s2", "b")))
        assert verdict.decision == "accept"
        assert verdict.groundedness >= 0.85
        assert set(verdict.cited_source_ids) == {"s1", "s2"}

    def test_low_groundedness_abstains(self):
        reply = json.dumps({"claims": [
            {"claim": "made up A", "score": 0.1, "supporting_ids": []},
            {"claim": "made up B", "score": 0.2, "supporting_ids": []},
        ]})
        v = LLMGroundingVerifier(llm=_MockLLM(reply))
        verdict = v.verify("two hallucinations", sources=_sources(("s1", "x")))
        assert verdict.decision == "abstain"
        assert verdict.groundedness <= 0.35

    def test_middling_groundedness_routes_to_redraft(self):
        reply = json.dumps({"claims": [
            {"claim": "ok", "score": 0.9, "supporting_ids": ["s1"]},
            {"claim": "weak", "score": 0.3, "supporting_ids": []},
        ]})
        v = LLMGroundingVerifier(llm=_MockLLM(reply))
        verdict = v.verify("ok. weak.", sources=_sources(("s1", "x")))
        # mean = 0.6, in (0.35, 0.75) → redraft
        assert verdict.decision == "redraft"
        assert "weak" in verdict.unsupported_claims

    def test_accept_requires_all_claims_above_pass_threshold(self):
        # avg might be high but one claim could be just-passed and another
        # could be borderline-unsupported. Verify accept demands NO
        # unsupported claims.
        reply = json.dumps({"claims": [
            {"claim": "a", "score": 1.0, "supporting_ids": ["s1"]},
            {"claim": "b", "score": 0.55, "supporting_ids": ["s1"]},
            {"claim": "c", "score": 0.45, "supporting_ids": []},  # < pass threshold 0.5
        ]})
        v = LLMGroundingVerifier(llm=_MockLLM(reply))
        verdict = v.verify("a. b. c.", sources=_sources(("s1", "x")))
        # mean ≈ 0.67 → redraft (not accept, because c is unsupported)
        assert verdict.decision == "redraft"
        assert verdict.unsupported_claims == ["c"]

    def test_empty_claims_yields_abstain_with_rationale(self):
        reply = json.dumps({"claims": []})
        v = LLMGroundingVerifier(llm=_MockLLM(reply))
        verdict = v.verify("I refuse to answer.", sources=_sources(("s1", "x")))
        assert verdict.decision == "abstain"
        assert "No verifiable claims" in verdict.rationale


# ---------------------------------------------------------------------------
# Citation construction
# ---------------------------------------------------------------------------


class TestCitations:
    def test_cited_source_ids_filtered_to_valid_only(self):
        reply = json.dumps({"claims": [
            {"claim": "a", "score": 0.9, "supporting_ids": ["s1", "phantom-id"]},
        ]})
        v = LLMGroundingVerifier(llm=_MockLLM(reply))
        verdict = v.verify("a.", sources=_sources(("s1", "x")))
        # Hallucinated source ids are dropped
        assert verdict.cited_source_ids == ["s1"]

    def test_cited_source_ids_dedup_and_preserve_order(self):
        reply = json.dumps({"claims": [
            {"claim": "a", "score": 0.9, "supporting_ids": ["s2", "s1"]},
            {"claim": "b", "score": 0.9, "supporting_ids": ["s1", "s3"]},
        ]})
        v = LLMGroundingVerifier(llm=_MockLLM(reply))
        verdict = v.verify("a. b.", sources=_sources(("s1", "x"), ("s2", "y"), ("s3", "z")))
        # First occurrence wins for order: s2 (claim 1) before s1, then s3 from claim 2
        assert verdict.cited_source_ids == ["s2", "s1", "s3"]

    def test_failed_claims_do_not_contribute_citations(self):
        reply = json.dumps({"claims": [
            {"claim": "ok", "score": 0.9, "supporting_ids": ["s1"]},
            {"claim": "bad", "score": 0.1, "supporting_ids": ["s2"]},  # under threshold
        ]})
        v = LLMGroundingVerifier(llm=_MockLLM(reply))
        verdict = v.verify("ok. bad.", sources=_sources(("s1", "x"), ("s2", "y")))
        assert verdict.cited_source_ids == ["s1"]


# ---------------------------------------------------------------------------
# Threshold customisation
# ---------------------------------------------------------------------------


class TestCustomThresholds:
    def test_lenient_thresholds_accept_more(self):
        reply = json.dumps({"claims": [
            {"claim": "a", "score": 0.6, "supporting_ids": ["s1"]},
        ]})
        v = LLMGroundingVerifier(
            llm=_MockLLM(reply),
            accept_threshold=0.5,
            abstain_threshold=0.1,
            claim_pass_threshold=0.5,
        )
        verdict = v.verify("a.", sources=_sources(("s1", "x")))
        assert verdict.decision == "accept"

    def test_strict_thresholds_abstain_more(self):
        reply = json.dumps({"claims": [
            {"claim": "a", "score": 0.6, "supporting_ids": ["s1"]},
        ]})
        v = LLMGroundingVerifier(
            llm=_MockLLM(reply),
            accept_threshold=0.9,
            abstain_threshold=0.7,
        )
        verdict = v.verify("a.", sources=_sources(("s1", "x")))
        assert verdict.decision == "abstain"
