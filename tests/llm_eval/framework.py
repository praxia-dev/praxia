"""Core eval framework — case runner + rubrics + baseline store.

Designed to keep tests **declarative**. A test author writes:

    case = LLMEvalCase(
        id="investment_q3",
        input="3-year thesis on a hypothetical mid-cap consumer-electronics issuer",
        expected_keywords=["valuation", "risk", "competitive", "ESG"],
        rubric=Rubric.STRUCTURE_PLUS_KEYWORDS,
        skill_factory=lambda llm: InvestmentSkill(llm=llm),
    )
    result = run_case(case, llm=LLM("claude"))
    assert_no_regression(case.id, result.score)

The framework keeps deterministic numbers (temperature=0) and a
regression-flagging baseline so reviewers can see at a glance "this PR
dropped quality from 0.78 to 0.65 on case investment_q3".
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

# --- Rubrics ---------------------------------------------------------------


class Rubric(str, Enum):
    """Built-in scoring strategies."""

    EXACT_MATCH = "exact_match"
    KEYWORDS = "keywords"
    STRUCTURE = "structure"
    STRUCTURE_PLUS_KEYWORDS = "structure_plus_keywords"
    LENGTH_BAND = "length_band"
    HALLUCINATION_LOW = "hallucination_low"
    LLM_JUDGE = "llm_judge"


# --- Case + Result ---------------------------------------------------------


@dataclass
class LLMEvalCase:
    """One declarative test case."""

    id: str
    input: str
    rubric: Rubric
    expected_keywords: list[str] = field(default_factory=list)
    expected_sections: list[str] = field(default_factory=list)
    min_length: int = 0
    max_length: int = 100_000
    skill_factory: Callable[[Any], Any] | None = None  # given llm → Skill
    flow_factory: Callable[[Any], Any] | None = None    # given llm → Flow
    inputs: dict[str, Any] | None = None              # for flows
    judge_prompt: str | None = None                   # for LLM_JUDGE
    must_not_contain: list[str] = field(default_factory=list)


@dataclass
class EvalResult:
    case_id: str
    output: str
    score: float          # 0.0 .. 1.0
    sub_scores: dict[str, float] = field(default_factory=dict)
    duration_seconds: float = 0.0
    notes: str = ""
    pass_threshold: float = 0.7

    @property
    def passed(self) -> bool:
        return self.score >= self.pass_threshold


# --- Scoring ---------------------------------------------------------------


def _score_keywords(text: str, expected: list[str]) -> float:
    if not expected:
        return 1.0
    found = sum(1 for kw in expected if kw.lower() in text.lower())
    return found / len(expected)


def _score_structure(text: str, expected_sections: list[str]) -> float:
    """Markdown-style heading match."""
    if not expected_sections:
        return 1.0
    headings = re.findall(r"^#{1,6}\s+(.*)$", text, re.MULTILINE)
    headings_lower = [h.lower() for h in headings]
    matched = sum(
        1 for sec in expected_sections
        if any(sec.lower() in h for h in headings_lower)
    )
    return matched / len(expected_sections)


def _score_length(text: str, *, min_len: int, max_len: int) -> float:
    n = len(text)
    if n < min_len:
        return n / max(min_len, 1)
    if n > max_len:
        return max(0.0, 1.0 - (n - max_len) / max_len)
    return 1.0


def _score_must_not_contain(text: str, forbidden: list[str]) -> float:
    if not forbidden:
        return 1.0
    hits = sum(1 for w in forbidden if w.lower() in text.lower())
    return 1.0 - (hits / len(forbidden))


def _score_llm_judge(text: str, judge_prompt: str, judge_llm: Any) -> float:
    """Ask an LLM to score 0-10. Normalize to 0-1.

    The judge_llm should be a different model than the one being evaluated
    (e.g., evaluate Claude with GPT-4 to avoid self-preference bias).
    """
    full = (
        f"{judge_prompt}\n\n"
        f"OUTPUT TO EVALUATE:\n---\n{text}\n---\n\n"
        f"Reply with ONLY a single number from 0 to 10."
    )
    resp = judge_llm.complete([{"role": "user", "content": full}])
    m = re.search(r"\b([0-9]|10)(?:\.\d+)?\b", resp.text.strip())
    if not m:
        return 0.0
    return float(m.group(1)) / 10.0


def score_case(case: LLMEvalCase, output: str, *, judge_llm: Any = None) -> EvalResult:
    """Apply the case's rubric and produce a scored result."""
    sub: dict[str, float] = {}

    if case.rubric in (Rubric.KEYWORDS, Rubric.STRUCTURE_PLUS_KEYWORDS):
        sub["keywords"] = _score_keywords(output, case.expected_keywords)

    if case.rubric in (Rubric.STRUCTURE, Rubric.STRUCTURE_PLUS_KEYWORDS):
        sub["structure"] = _score_structure(output, case.expected_sections)

    if case.min_length or case.max_length < 100_000:
        sub["length"] = _score_length(
            output, min_len=case.min_length, max_len=case.max_length
        )

    if case.must_not_contain:
        sub["must_not_contain"] = _score_must_not_contain(
            output, case.must_not_contain
        )

    if case.rubric == Rubric.EXACT_MATCH:
        sub["exact_match"] = 1.0 if output.strip() == case.input.strip() else 0.0

    if case.rubric == Rubric.LLM_JUDGE:
        if judge_llm is None or case.judge_prompt is None:
            sub["llm_judge"] = 0.0
        else:
            sub["llm_judge"] = _score_llm_judge(
                output, case.judge_prompt, judge_llm
            )

    score = sum(sub.values()) / len(sub) if sub else 0.0
    return EvalResult(case_id=case.id, output=output, score=score, sub_scores=sub)


# --- Runner ----------------------------------------------------------------


def run_case(case: LLMEvalCase, *, llm: Any, judge_llm: Any = None) -> EvalResult:
    """Execute the case and produce a scored result."""
    start = time.time()
    if case.skill_factory:
        skill = case.skill_factory(llm)
        output = skill.run(case.input)
    elif case.flow_factory:
        flow = case.flow_factory(llm)
        result = flow.run(case.inputs or {"input": case.input})
        output = result.final_output
    else:
        # Direct LLM call
        resp = llm.complete([{"role": "user", "content": case.input}])
        output = resp.text

    result = score_case(case, output, judge_llm=judge_llm)
    result.duration_seconds = time.time() - start
    return result


# --- Baselines -------------------------------------------------------------


@dataclass
class BaselineEntry:
    case_id: str
    score: float
    sub_scores: dict[str, float]
    model: str
    timestamp: float


class BaselineStore:
    """Persists prior scores so PRs can be flagged on regression.

    File layout: `tests/llm_eval/baselines.json` (committed to git).
    """

    def __init__(self, path: Path | str = "tests/llm_eval/baselines.json") -> None:
        self.path = Path(path)

    def _read(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data: dict[str, dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )

    def get(self, case_id: str, model: str) -> BaselineEntry | None:
        key = f"{model}::{case_id}"
        record = self._read().get(key)
        if not record:
            return None
        return BaselineEntry(**record)

    def save(self, result: EvalResult, *, model: str) -> None:
        data = self._read()
        key = f"{model}::{result.case_id}"
        data[key] = asdict(BaselineEntry(
            case_id=result.case_id,
            score=result.score,
            sub_scores=dict(result.sub_scores),
            model=model,
            timestamp=time.time(),
        ))
        self._write(data)

    def regression(
        self, result: EvalResult, *, model: str, tolerance: float = 0.05
    ) -> tuple[bool, str]:
        """Return (regressed, message)."""
        baseline = self.get(result.case_id, model)
        if baseline is None:
            return False, f"no baseline yet — first run for {model}::{result.case_id}"
        delta = result.score - baseline.score
        if delta < -tolerance:
            return True, (
                f"REGRESSION on {result.case_id}: {baseline.score:.3f} → "
                f"{result.score:.3f} (Δ {delta:+.3f}, tolerance ±{tolerance})"
            )
        return False, (
            f"OK: {result.case_id} score {result.score:.3f} "
            f"(baseline {baseline.score:.3f}, Δ {delta:+.3f})"
        )


__all__ = [
    "Rubric",
    "LLMEvalCase",
    "EvalResult",
    "BaselineEntry",
    "BaselineStore",
    "score_case",
    "run_case",
]
