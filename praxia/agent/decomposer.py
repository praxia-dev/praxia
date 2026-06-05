"""Query decomposition for multi-hop knowledge questions.

Verification finding K2: multi-hop QA (HotpotQA-style 2-hop questions)
gains +10-12pt of accuracy when the question is split into sub-questions
and retrieval is run per hop, then the chunks are unioned before the
draft is composed. A single-pass retriever on the original question
misses bridge passages whose vocabulary doesn't overlap with the
original wording. A single-pass critic does NOT recover that — it
actually hurts slightly because over-rejection rises.

This module ships a thin :class:`QueryDecomposer` protocol and a default
LLM-driven implementation. The :class:`praxia.agent.commander.DefaultMemoryRetriever`
consults the decomposer before retrieving — if the decomposer returns
multiple sub-questions, the retriever runs each one and unions the
resulting Sources (deduped by id).

Pitfalls observed in the original benchmark:
- For single-hop / already-known facts, decomposition adds latency
  without quality gain (verification finding K1). The default
  classifier therefore returns ``[query]`` for inputs that look obviously
  single-hop, so callers always get a list back without paying the LLM
  round-trip on every question.
- LLM-decomposed sub-questions can leak the original question verbatim
  back into one slot — that's fine; the retriever's dedup handles it.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from praxia.core.llm import LLM

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class QueryDecomposer(Protocol):
    """Decompose a user query into 1..N retrieval sub-queries."""

    def decompose(self, query: str) -> list[str]: ...


# ---------------------------------------------------------------------------
# Heuristics — cheap pre-filter so we don't pay the LLM on every call
# ---------------------------------------------------------------------------


# Tokens that strongly suggest the question is multi-hop / comparative
# / chained. Bilingual (EN/JA). Conservative on purpose: a false negative
# here (multi-hop wrongly skipped) just collapses to single-pass behaviour
# — no regression, only missed upside.
_MULTIHOP_HINTS = (
    # English
    "compare", "comparison", "vs", "versus",
    "which of", "which one", "and then", "after that",
    "both", "either", "between",
    "what is the relationship between",
    "who succeeded", "who preceded",
    # Japanese
    "比較", "違い", "どちら", "どっち", "両方", "間の",
    "そして", "その後", "関係", "後継", "前任",
)


def looks_multihop(query: str) -> bool:
    """Cheap, regex-light heuristic — true if the query is plausibly
    multi-hop and worth decomposing.
    """
    if not query or len(query.strip()) < 15:
        return False
    lowered = query.lower()
    for kw in _MULTIHOP_HINTS:
        if kw in lowered:
            return True
    # Multiple capitalised entity tokens often signal a bridge question
    # ("X works for which company that was founded by Y?"). We use a
    # light token count rather than NER — 3+ proper-noun-ish tokens.
    proper = re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", query)
    if len(set(proper)) >= 3:
        return True
    return False


# ---------------------------------------------------------------------------
# Default implementation
# ---------------------------------------------------------------------------


_DEFAULT_SYSTEM_PROMPT = """You decompose user questions into the minimal
set of sub-questions a search engine should run to find evidence for the
answer.

Rules:
  - If the question is single-hop (one fact lookup), return the original
    question as the only item. Do NOT invent extra sub-questions.
  - For multi-hop questions, produce 2 to 4 sub-questions, each
    self-contained (resolvable without seeing the others).
  - Do NOT include the final synthesis question — only the retrieval
    sub-questions.
  - Sub-questions should be in the same language as the input.

Output STRICT JSON:
{"sub_queries": ["<sub-question 1>", "<sub-question 2>", ...]}

Never include any prose outside the JSON object."""


@dataclass
class LLMQueryDecomposer:
    """Default decomposer — one LLM call per query when the heuristic
    flags the question as multi-hop, otherwise short-circuits to
    ``[query]``.

    Args:
        llm: a :class:`praxia.core.llm.LLM` used to generate the
            decomposition.
        max_subqueries: hard cap on the number of sub-questions returned
            (LLM output is truncated to this). Default 4.
        always_run: bypass the heuristic and call the LLM on every input.
            Slower but recommended when the input domain is known to be
            multi-hop heavy (e.g. analytics, compliance crosswalks).
        max_response_tokens: cap on the JSON output the LLM emits.
        system_prompt: override the decomposer's instructions.
    """

    llm: "LLM"
    max_subqueries: int = 4
    always_run: bool = False
    max_response_tokens: int = 512
    system_prompt: str = _DEFAULT_SYSTEM_PROMPT

    def decompose(self, query: str) -> list[str]:
        if not query.strip():
            return []
        if not self.always_run and not looks_multihop(query):
            return [query.strip()]

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Question: {query}"},
        ]
        try:
            raw = self.llm.complete(
                messages,
                max_tokens=self.max_response_tokens,
                temperature=0.0,
                response_format={"type": "json_object"},
            )
        except TypeError:
            # Some LLM adapters don't accept ``response_format`` — retry
            # without it and rely on the prompt's JSON constraint.
            raw = self.llm.complete(
                messages,
                max_tokens=self.max_response_tokens,
                temperature=0.0,
            )
        except Exception:
            _log.exception("Decomposer LLM call failed; falling back to single-pass")
            return [query.strip()]

        subs = self._parse(raw)
        if not subs:
            return [query.strip()]

        # Cap, dedupe (case-insensitive), preserve order.
        seen: set[str] = set()
        out: list[str] = []
        for s in subs[: self.max_subqueries]:
            k = s.strip().lower()
            if not k or k in seen:
                continue
            seen.add(k)
            out.append(s.strip())
        return out or [query.strip()]

    @staticmethod
    def _parse(raw: str) -> list[str]:
        # Some adapters wrap the JSON in ```json ... ``` fences. Strip
        # them before parsing.
        s = raw.strip()
        if s.startswith("```"):
            s = s.lstrip("`").lstrip("json").strip()
            if s.endswith("```"):
                s = s[: -3].strip()
        try:
            obj = json.loads(s)
        except json.JSONDecodeError:
            return []
        subs = obj.get("sub_queries") if isinstance(obj, dict) else None
        if not isinstance(subs, list):
            return []
        return [str(x) for x in subs if isinstance(x, (str, int, float))]
