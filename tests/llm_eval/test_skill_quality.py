"""LLM output quality tests for the 6 business skills.

Skipped by default. Run with:
    pytest tests/llm_eval -m llm_eval

Each skill gets one canonical test case + structure & keyword rubric.
A regression PR will fail if the LLM judge / keyword score drops below
the committed baseline by more than 5 points.
"""
from __future__ import annotations

import pytest

from tests.llm_eval.framework import (
    LLMEvalCase,
    Rubric,
    run_case,
)

pytestmark = [pytest.mark.llm_eval, pytest.mark.slow]


def _evaluate(case, llm, judge_llm, baseline_store, eval_model, update_baselines):
    """Run + grade + baseline-check helper."""
    result = run_case(case, llm=llm, judge_llm=judge_llm)
    if update_baselines:
        baseline_store.save(result, model=eval_model)
        return
    regressed, msg = baseline_store.regression(result, model=eval_model)
    print(f"\n[{case.id}] {msg}")
    print(f"  output ({len(result.output)} chars): {result.output[:200]}…")
    print(f"  sub-scores: {result.sub_scores}")
    assert not regressed, msg
    assert result.passed, (
        f"score {result.score:.3f} below pass threshold {result.pass_threshold:.3f}"
    )


# --- Investment ------------------------------------------------------------

def test_investment_q3_review(
    llm, judge_llm, baseline_store, eval_model, update_baselines
):
    from praxia.skills.business import InvestmentSkill

    case = LLMEvalCase(
        id="investment_q3_review",
        input=(
            "Mid-term investment thesis on a hypothetical mid-cap consumer-"
            "electronics issuer. Provide a 5-section analysis (Profile / "
            "Quant / Qual / Risk / Decision)."
        ),
        rubric=Rubric.STRUCTURE_PLUS_KEYWORDS,
        expected_keywords=[
            "valuation", "risk", "competitive", "macro", "ESG",
        ],
        expected_sections=["profile", "quant", "qual", "risk", "decision"],
        min_length=800,
        max_length=12_000,
        skill_factory=lambda llm: InvestmentSkill(llm=llm),
        must_not_contain=["actual investment advice"],
    )
    _evaluate(case, llm, judge_llm, baseline_store, eval_model, update_baselines)


# --- Sales -----------------------------------------------------------------

def test_sales_b2b_prep(
    llm, judge_llm, baseline_store, eval_model, update_baselines
):
    from praxia.skills.business import SalesSkill

    case = LLMEvalCase(
        id="sales_b2b_prep",
        input=(
            "B2B sales preparation for a hypothetical mid-cap manufacturer "
            "considering DX investment. Deliver: top-3 pain hypotheses, "
            "5-row FAQ with assumed evidence, 3-paragraph proposal outline."
        ),
        rubric=Rubric.STRUCTURE_PLUS_KEYWORDS,
        expected_keywords=["hypothesis", "FAQ", "proposal", "pain", "value"],
        expected_sections=["hypotheses", "faq", "proposal"],
        min_length=600,
        skill_factory=lambda llm: SalesSkill(llm=llm),
    )
    _evaluate(case, llm, judge_llm, baseline_store, eval_model, update_baselines)


# --- Design ----------------------------------------------------------------

def test_design_review_dragon(
    llm, judge_llm, baseline_store, eval_model, update_baselines
):
    from praxia.skills.business import DesignSkill

    case = LLMEvalCase(
        id="design_review_dragon",
        input=(
            "Review this hypothetical architecture: a payment microservice "
            "with PostgreSQL, Redis cache, gRPC API, deployed on Kubernetes. "
            "Apply the DRAGON framework (Data flow / Requirements / "
            "Architectural fit / Gaps / Operations / NFRs)."
        ),
        rubric=Rubric.STRUCTURE_PLUS_KEYWORDS,
        expected_keywords=["data flow", "requirements", "gap", "NFR", "operations"],
        expected_sections=["data", "requirements", "gap", "operations"],
        min_length=600,
        skill_factory=lambda llm: DesignSkill(llm=llm),
    )
    _evaluate(case, llm, judge_llm, baseline_store, eval_model, update_baselines)


# --- Purchasing ------------------------------------------------------------

def test_purchasing_rfq_compare(
    llm, judge_llm, baseline_store, eval_model, update_baselines
):
    from praxia.skills.business import PurchasingSkill

    case = LLMEvalCase(
        id="purchasing_rfq_compare",
        input=(
            "Compare 3 hypothetical PCB suppliers (annual volume 2M units, "
            "Japan-domiciled HQ, ISO9001). Use QCD+S framework + TCO. "
            "Flag single-source risk + Subcontract Act considerations."
        ),
        rubric=Rubric.STRUCTURE_PLUS_KEYWORDS,
        expected_keywords=["TCO", "quality", "delivery", "BCP", "single-source"],
        expected_sections=["quality", "cost", "delivery"],
        min_length=500,
        skill_factory=lambda llm: PurchasingSkill(llm=llm),
    )
    _evaluate(case, llm, judge_llm, baseline_store, eval_model, update_baselines)


# --- Patent ----------------------------------------------------------------

def test_patent_prior_art(
    llm, judge_llm, baseline_store, eval_model, update_baselines
):
    from praxia.skills.business import PatentSkill

    case = LLMEvalCase(
        id="patent_prior_art",
        input=(
            "Prior-art research for a solid-state battery with three-layer "
            "ceramic electrolyte. Provide: element decomposition, IPC/FI/"
            "F-term search strategy, novelty + inventive-step verdict."
        ),
        rubric=Rubric.STRUCTURE_PLUS_KEYWORDS,
        expected_keywords=["element", "IPC", "F-term", "novelty", "inventive"],
        expected_sections=["element", "search", "novelty"],
        min_length=600,
        must_not_contain=["legal advice"],
        skill_factory=lambda llm: PatentSkill(llm=llm),
    )
    _evaluate(case, llm, judge_llm, baseline_store, eval_model, update_baselines)


# --- Legal -----------------------------------------------------------------

def test_legal_contract_review(
    llm, judge_llm, baseline_store, eval_model, update_baselines
):
    from praxia.skills.business import LegalSkill

    case = LLMEvalCase(
        id="legal_contract_review",
        input=(
            "Review the following hypothetical Services Agreement clauses: "
            "(1) liability cap = 12 months fees; (2) IP fully assigned to "
            "customer; (3) data must be returned within 30 days of "
            "termination; (4) no anti-bribery clause. Apply RACE framework "
            "(Risk / Allocation / Compliance / Exit) with 🔴/🟡/🟢 severity."
        ),
        rubric=Rubric.STRUCTURE_PLUS_KEYWORDS,
        expected_keywords=["liability", "IP", "termination", "anti-bribery", "risk"],
        expected_sections=["risk", "allocation", "compliance", "exit"],
        min_length=500,
        must_not_contain=["definitive legal advice"],
        skill_factory=lambda llm: LegalSkill(llm=llm),
    )
    _evaluate(case, llm, judge_llm, baseline_store, eval_model, update_baselines)
