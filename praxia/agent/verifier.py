"""External verification layer for Praxia agents.

A ``Verifier`` grades a draft answer against a fixed set of retrieved sources
and returns a ``Verdict`` — a structured decision the surrounding commander
loop can act on (accept / redraft / abstain).

The default implementation, :class:`LLMGroundingVerifier`, uses a single
LLM call to atomically extract per-claim grounding scores, so callers only
pay one round trip per verification round.

This protocol is intentionally narrow — anyone shipping a custom verifier
(embedding-based / rule-based / retrieval-overlap-only) only has to satisfy
``verify(draft, sources) -> Verdict``.

See also :mod:`praxia.agent.commander` for the loop that uses this layer.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from praxia.core.llm import LLM

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Source:
    """One piece of evidence the agent retrieved before drafting.

    The ``id`` is what the verifier will quote when it attributes a claim to
    a source — keep it short and human-readable (e.g. ``"L1#42"`` or
    ``"sop:incident-2024-Q3"``).
    """
    id: str
    text: str
    kind: str = "memory"            # memory / skill / frozen / connector / external
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ClaimScore:
    """One atomic claim from the draft and its grounding evidence."""
    claim: str
    score: float                     # 0..1, higher = better grounded
    supporting_ids: list[str] = field(default_factory=list)
    note: str = ""                   # verifier rationale, optional


Decision = Literal["accept", "redraft", "abstain"]


@dataclass
class Verdict:
    """Structured outcome of one verification round.

    Attributes:
        groundedness: aggregate score in [0, 1] over all claims.
        per_claim: per-claim breakdown — useful for UI and audit trails.
        unsupported_claims: convenience view of claims that scored below
            ``LLMGroundingVerifier.claim_pass_threshold``.
        decision: what the commander should do next.
        rationale: short human-readable explanation of the decision.
        cited_source_ids: union of supporting source ids across all
            *accepted* claims — what the commander can quote in the final
            output.
    """
    groundedness: float
    per_claim: list[ClaimScore]
    unsupported_claims: list[str]
    decision: Decision
    rationale: str = ""
    cited_source_ids: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Protocol — anyone shipping a custom verifier satisfies this
# ---------------------------------------------------------------------------


@runtime_checkable
class Verifier(Protocol):
    """Grades a draft against retrieved sources.

    Implementations MUST be deterministic enough that the same
    ``(draft, sources)`` pair yields the same ``decision`` on a hot retry —
    the commander relies on this to decide whether to keep trying or to
    abstain.
    """

    def verify(self, draft: str, sources: list[Source]) -> Verdict: ...


# ---------------------------------------------------------------------------
# Default implementation
# ---------------------------------------------------------------------------


_DEFAULT_SYSTEM_PROMPT = """You are a grounding verifier for an AI agent.

You will receive:
  1. A DRAFT answer the agent produced.
  2. A list of SOURCES the agent had access to (each with a short id).

Your job:
  - Decompose the draft into ATOMIC FACTUAL CLAIMS (each independently
    verifiable). Skip pure opinions, hedges ("might", "in my view"), and
    the agent's own reasoning chatter.
  - For each claim, decide whether it is supported by the sources.
    "Supported" means a reasonable reader could verify the claim from the
    quoted source text — do NOT use background world knowledge to fill gaps.
  - Score each claim in [0, 1]:
      1.0 = explicitly stated by one or more sources
      0.7 = clearly implied / inferable from sources without leaps
      0.4 = partially supported; some words are in sources but the claim
            adds material not present there
      0.0 = not in the sources at all (likely hallucination)
  - Return the supporting source ids ONLY when score >= 0.5.

Output STRICT JSON with this shape:

{
  "claims": [
    {
      "claim": "<verbatim or paraphrased claim>",
      "score": 0.0..1.0,
      "supporting_ids": ["<source.id>", ...],
      "note": "<one short sentence, optional>"
    },
    ...
  ]
}

Rules:
  - Do not include claims you skipped.
  - If the draft contains zero verifiable claims (pure refusal, pure
    opinion), return {"claims": []}.
  - Keep notes short — they go to the audit log."""


@dataclass
class LLMGroundingVerifier:
    """Default verifier — single-LLM-call grounding score.

    Args:
        llm: a :class:`praxia.core.llm.LLM` used to extract + score claims.
        accept_threshold: aggregate groundedness at or above this is
            "accept". Default 0.75.
        abstain_threshold: aggregate groundedness at or below this is
            "abstain" — the agent does not have enough evidence to answer
            and should say so rather than guess. Default 0.35.
        claim_pass_threshold: per-claim score at or above which a claim is
            considered "supported" (used when computing
            ``unsupported_claims``). Default 0.5.
        max_response_tokens: cap on the verifier's JSON output.
        system_prompt: override the verifier's instructions.
    """

    llm: "LLM"
    accept_threshold: float = 0.75
    abstain_threshold: float = 0.35
    claim_pass_threshold: float = 0.5
    max_response_tokens: int = 2048
    system_prompt: str = _DEFAULT_SYSTEM_PROMPT

    def verify(self, draft: str, sources: list[Source]) -> Verdict:
        """Run one verification round."""
        if not draft.strip():
            return Verdict(
                groundedness=0.0,
                per_claim=[],
                unsupported_claims=[],
                decision="abstain",
                rationale="Draft answer is empty.",
            )

        if not sources:
            # No sources to ground against — anything in the draft is
            # ungrounded by definition. Don't waste an LLM call.
            return Verdict(
                groundedness=0.0,
                per_claim=[],
                unsupported_claims=[draft.strip()[:300]],
                decision="abstain",
                rationale="No sources were retrieved; cannot verify draft.",
            )

        user_message = self._build_user_message(draft, sources)
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_message},
        ]
        try:
            resp = self.llm.complete(messages, max_tokens=self.max_response_tokens)
        except Exception as exc:  # pragma: no cover - guarded path
            _log.exception("Verifier LLM call failed")
            return Verdict(
                groundedness=0.0,
                per_claim=[],
                unsupported_claims=[],
                decision="abstain",
                rationale=f"Verifier LLM call failed: {exc}",
            )

        parsed = self._parse_json(resp.text)
        claims = self._parse_claims(parsed)
        return self._aggregate(claims, sources)

    # --- internals ---------------------------------------------------------

    @staticmethod
    def _build_user_message(draft: str, sources: list[Source]) -> str:
        src_block = "\n\n".join(
            f"[{s.id}] ({s.kind})\n{s.text.strip()}" for s in sources
        )
        return (
            "=== DRAFT ===\n"
            f"{draft.strip()}\n\n"
            "=== SOURCES ===\n"
            f"{src_block}\n\n"
            "Return ONLY the JSON object specified in the system prompt — "
            "no prose before or after."
        )

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        """Tolerant JSON parse — strips code-fences, finds the outermost {...}."""
        if not text:
            return {}
        stripped = text.strip()
        # Strip ```json ... ``` or ``` ... ``` fences
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?\s*", "", stripped, count=1)
            stripped = re.sub(r"\s*```\s*$", "", stripped, count=1)
        # Extract the outermost JSON object if the model wrapped it in prose
        match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _parse_claims(parsed: dict[str, Any]) -> list[ClaimScore]:
        raw_claims = parsed.get("claims") if isinstance(parsed, dict) else None
        if not isinstance(raw_claims, list):
            return []
        out: list[ClaimScore] = []
        for c in raw_claims:
            if not isinstance(c, dict):
                continue
            text = str(c.get("claim", "")).strip()
            if not text:
                continue
            try:
                score = max(0.0, min(1.0, float(c.get("score", 0.0))))
            except (TypeError, ValueError):
                score = 0.0
            supporting = c.get("supporting_ids", []) or []
            if not isinstance(supporting, list):
                supporting = []
            out.append(
                ClaimScore(
                    claim=text,
                    score=score,
                    supporting_ids=[str(x) for x in supporting if x is not None],
                    note=str(c.get("note", ""))[:200],
                )
            )
        return out

    def _aggregate(
        self,
        claims: list[ClaimScore],
        sources: list[Source],
    ) -> Verdict:
        if not claims:
            # No verifiable claims extracted. Treat as abstain — the
            # commander can choose to forward the draft anyway if it's a
            # refusal / hedged response.
            return Verdict(
                groundedness=0.0,
                per_claim=[],
                unsupported_claims=[],
                decision="abstain",
                rationale="No verifiable claims extracted from draft.",
            )

        groundedness = sum(c.score for c in claims) / len(claims)
        unsupported = [c.claim for c in claims if c.score < self.claim_pass_threshold]

        # Build cited_source_ids from claims that PASSED, preserving order
        # and uniqueness so the commander can quote them downstream.
        seen: set[str] = set()
        valid_ids = {s.id for s in sources}
        cited: list[str] = []
        for c in claims:
            if c.score < self.claim_pass_threshold:
                continue
            for sid in c.supporting_ids:
                if sid in valid_ids and sid not in seen:
                    cited.append(sid)
                    seen.add(sid)

        if groundedness >= self.accept_threshold and not unsupported:
            decision: Decision = "accept"
            rationale = (
                f"groundedness={groundedness:.2f} >= {self.accept_threshold}; "
                f"all {len(claims)} claims supported."
            )
        elif groundedness <= self.abstain_threshold:
            decision = "abstain"
            rationale = (
                f"groundedness={groundedness:.2f} <= {self.abstain_threshold}; "
                f"{len(unsupported)}/{len(claims)} claims unsupported."
            )
        else:
            decision = "redraft"
            rationale = (
                f"groundedness={groundedness:.2f} in "
                f"({self.abstain_threshold}, {self.accept_threshold}); "
                f"{len(unsupported)} claim(s) need re-grounding."
            )

        return Verdict(
            groundedness=round(groundedness, 4),
            per_claim=claims,
            unsupported_claims=unsupported,
            decision=decision,
            rationale=rationale,
            cited_source_ids=cited,
        )
