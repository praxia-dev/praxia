"""Self-tests for the LLM eval framework — pure functions, no LLM call.

These tests run under the regular `pytest -m evaluation` path because
they don't actually call an LLM; they just verify the scoring logic.
"""
from __future__ import annotations

import pytest

from tests.llm_eval.framework import (
    BaselineStore,
    EvalResult,
    LLMEvalCase,
    Rubric,
    score_case,
)

pytestmark = pytest.mark.evaluation


class TestKeywordsRubric:
    def test_all_keywords_present_full_score(self):
        case = LLMEvalCase(
            id="t",
            input="x",
            rubric=Rubric.KEYWORDS,
            expected_keywords=["alpha", "beta"],
        )
        result = score_case(case, "alpha and beta are here")
        assert result.sub_scores["keywords"] == 1.0

    def test_partial_keywords_partial_score(self):
        case = LLMEvalCase(
            id="t",
            input="x",
            rubric=Rubric.KEYWORDS,
            expected_keywords=["alpha", "beta", "gamma"],
        )
        result = score_case(case, "alpha only")
        assert result.sub_scores["keywords"] == pytest.approx(1 / 3, abs=0.001)

    def test_case_insensitive_match(self):
        case = LLMEvalCase(
            id="t",
            input="x",
            rubric=Rubric.KEYWORDS,
            expected_keywords=["VALUATION"],
        )
        result = score_case(case, "the valuation is good")
        assert result.sub_scores["keywords"] == 1.0


class TestStructureRubric:
    def test_headings_match(self):
        case = LLMEvalCase(
            id="t",
            input="x",
            rubric=Rubric.STRUCTURE,
            expected_sections=["overview", "risks"],
        )
        text = "# Overview\n\nbody\n\n## Risks\n\nbody"
        result = score_case(case, text)
        assert result.sub_scores["structure"] == 1.0

    def test_partial_structure(self):
        case = LLMEvalCase(
            id="t",
            input="x",
            rubric=Rubric.STRUCTURE,
            expected_sections=["overview", "risks", "decision"],
        )
        text = "## Overview\nbody"
        result = score_case(case, text)
        assert result.sub_scores["structure"] == pytest.approx(1 / 3, abs=0.001)


class TestLengthBand:
    def test_within_band(self):
        case = LLMEvalCase(
            id="t", input="x", rubric=Rubric.LENGTH_BAND,
            min_length=10, max_length=100,
        )
        result = score_case(case, "a" * 50)
        assert result.sub_scores["length"] == 1.0

    def test_below_min(self):
        case = LLMEvalCase(
            id="t", input="x", rubric=Rubric.LENGTH_BAND,
            min_length=100, max_length=200,
        )
        result = score_case(case, "a" * 50)
        assert 0.0 <= result.sub_scores["length"] < 1.0

    def test_above_max(self):
        case = LLMEvalCase(
            id="t", input="x", rubric=Rubric.LENGTH_BAND,
            min_length=10, max_length=100,
        )
        result = score_case(case, "a" * 200)
        assert 0.0 <= result.sub_scores["length"] < 1.0


class TestMustNotContain:
    def test_clean_output_full_score(self):
        case = LLMEvalCase(
            id="t", input="x", rubric=Rubric.KEYWORDS,
            expected_keywords=["foo"],
            must_not_contain=["legal advice", "investment advice"],
        )
        result = score_case(case, "foo is great")
        assert result.sub_scores["must_not_contain"] == 1.0

    def test_forbidden_word_drops_score(self):
        case = LLMEvalCase(
            id="t", input="x", rubric=Rubric.KEYWORDS,
            expected_keywords=["foo"],
            must_not_contain=["legal advice"],
        )
        result = score_case(case, "foo is great. this is legal advice.")
        assert result.sub_scores["must_not_contain"] == 0.0


class TestBaselineStore:
    def test_no_baseline_returns_no_regression(self, tmp_path):
        store = BaselineStore(path=tmp_path / "baselines.json")
        result = EvalResult(case_id="x", output="o", score=0.8)
        regressed, msg = store.regression(result, model="claude")
        assert regressed is False
        assert "no baseline yet" in msg

    def test_save_then_compare_no_regression(self, tmp_path):
        store = BaselineStore(path=tmp_path / "baselines.json")
        first = EvalResult(case_id="x", output="o", score=0.80)
        store.save(first, model="claude")

        # Same score → not a regression
        again = EvalResult(case_id="x", output="o", score=0.80)
        regressed, _ = store.regression(again, model="claude")
        assert regressed is False

        # Slightly higher → not a regression
        better = EvalResult(case_id="x", output="o", score=0.85)
        regressed, _ = store.regression(better, model="claude")
        assert regressed is False

    def test_regression_flagged_beyond_tolerance(self, tmp_path):
        store = BaselineStore(path=tmp_path / "baselines.json")
        store.save(EvalResult(case_id="x", output="o", score=0.80), model="claude")
        worse = EvalResult(case_id="x", output="o", score=0.60)  # Δ = -0.20
        regressed, msg = store.regression(worse, model="claude", tolerance=0.05)
        assert regressed is True
        assert "REGRESSION" in msg

    def test_per_model_baselines_isolated(self, tmp_path):
        store = BaselineStore(path=tmp_path / "baselines.json")
        store.save(EvalResult(case_id="x", output="o", score=0.80), model="claude")
        store.save(EvalResult(case_id="x", output="o", score=0.40), model="qwen")

        c = store.get("x", "claude")
        q = store.get("x", "qwen")
        assert c is not None and c.score == 0.80
        assert q is not None and q.score == 0.40
