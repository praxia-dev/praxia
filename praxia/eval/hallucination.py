"""Hallucination detection — verify each sentence in an answer is grounded
in the retrieved chunks. Powered by the same LLM client as the rest of the
framework.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from praxia.core.llm import LLM


@dataclass
class HallucinationCheck:
    answer: str
    grounded_sentences: list[str]
    ungrounded_sentences: list[str]
    hallucination_rate: float
    # Set when the underlying judge LLM returned a malformed (non-JSON) response.
    # In that case the verdict is **inconclusive** — `hallucination_rate` is set
    # to `nan` so callers must explicitly handle the unknown case rather than
    # treating an unparseable answer as "all clean".
    judge_failed: bool = False
    judge_failure_reason: str = ""

    @property
    def is_clean(self) -> bool:
        if self.judge_failed:
            return False
        return self.hallucination_rate == 0.0


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[\.\!\?。！？])\s+", text.strip())
    return [p for p in parts if p]


def check_hallucination(answer: str, chunks: list[str], llm: LLM | None = None) -> HallucinationCheck:
    """Score each sentence of `answer` against `chunks`.

    Uses LLM-as-judge — fast and good enough for in-the-loop checks. For
    research-grade evaluation use HHEM, RAGAS, or TruthfulQA-style benchmarks.
    """
    sentences = _split_sentences(answer)
    if not sentences:
        return HallucinationCheck(answer=answer, grounded_sentences=[], ungrounded_sentences=[], hallucination_rate=0.0)

    llm = llm or LLM()
    prompt = (
        "あなたは事実検証アシスタントです。"
        "以下の回答の各文について、提供されたチャンクで裏付けられているか判定してください。\n\n"
        "## チャンク\n"
        + "\n---\n".join(chunks)
        + "\n\n## 回答 (各文)\n"
        + "\n".join(f"{i + 1}. {s}" for i, s in enumerate(sentences))
        + '\n\n## 出力形式 (JSON)\n{"verdicts": [{"sentence_idx": 1, "grounded": true|false, "reason": "..."}]}'
    )
    response = llm.complete([{"role": "user", "content": prompt}], response_format="json")
    try:
        data = json.loads(response.text)
    except json.JSONDecodeError as exc:
        # Surface the failure rather than silently report "all grounded".
        # `hallucination_rate=nan` forces callers to branch on `judge_failed`.
        return HallucinationCheck(
            answer=answer,
            grounded_sentences=[],
            ungrounded_sentences=sentences,
            hallucination_rate=float("nan"),
            judge_failed=True,
            judge_failure_reason=(
                f"judge LLM returned non-JSON ({type(exc).__name__}: {exc}). "
                f"first 200 chars: {response.text[:200]!r}"
            ),
        )

    grounded: list[str] = []
    ungrounded: list[str] = []
    for verdict in data.get("verdicts", []):
        idx = int(verdict.get("sentence_idx", 0)) - 1
        if 0 <= idx < len(sentences):
            (grounded if verdict.get("grounded") else ungrounded).append(sentences[idx])

    rate = len(ungrounded) / max(len(sentences), 1)
    return HallucinationCheck(
        answer=answer,
        grounded_sentences=grounded,
        ungrounded_sentences=ungrounded,
        hallucination_rate=rate,
    )
