"""CommandedAgent — autonomous agent with an external grounding commander.

Where :class:`praxia.agent.autonomous.AutonomousAgent` is a free-running
tool-use loop, :class:`CommandedAgent` wraps that loop with three guards:

1. **Pre-retrieval** — before the agent starts drafting, the commander
   pulls evidence from the available memory layers and stitches it into the
   prompt as ``[L1#0]…[L4#1]`` numbered sources.
2. **Verification** — the draft is checked by a :class:`Verifier` against
   those sources. A grounded answer is accepted (with citations); a
   partially-grounded one is redrafted; an unsupported one triggers an
   explicit abstention.
3. **Bounded retry** — at most ``max_verify_rounds`` redrafts. Every
   round is recorded so it can be replayed or audited.

This is the right shape when the *environment* does not give you a free
answer key — private-corpus fact QA, compliance / SOP questions, customer
support over manuals, technical-knowledge transfer. For coding / DevOps
loops, where tests and exit codes ARE the answer key, the bare
:class:`AutonomousAgent` is the simpler choice.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from praxia.agent.autonomous import AutonomousAgent
from praxia.agent.result import AgentResult
from praxia.agent.verifier import (
    LLMGroundingVerifier,
    Source,
    Verdict,
    Verifier,
)

if TYPE_CHECKING:
    from praxia.memory.markdown_store import MarkdownStore
    from praxia.memory.personal import PersonalMemory
    from praxia.memory.shared import SharedMemory

_log = logging.getLogger(__name__)


Retriever = Callable[[str], list[Source]]
"""Signature: ``(query: str) -> list[Source]``.

A retriever may be a default :class:`DefaultMemoryRetriever`, a callable
the host wires up, or any object that walks like one.
"""


# ---------------------------------------------------------------------------
# Default abstention text
# ---------------------------------------------------------------------------

DEFAULT_ABSTAIN_MESSAGE = (
    "I don't have enough grounded information in the available sources to "
    "answer this confidently. Please add more context, point me at the right "
    "documents, or rephrase the question."
)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class CommandedResult:
    """Outcome of a :meth:`CommandedAgent.run` call.

    The full ``rounds`` log lets you replay or audit the agent's reasoning;
    each round captures the draft text, the verifier's verdict, and the
    underlying :class:`AgentResult` (token usage + tool trace).
    """
    answer: str
    verdict: Verdict
    sources: list[Source] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    rounds: list["CommandedRound"] = field(default_factory=list)
    stopped_reason: str = "accept"            # accept | abstain | max_rounds
    usage: dict[str, int] = field(default_factory=dict)

    def add_usage(self, more: dict[str, int]) -> None:
        for k, v in more.items():
            self.usage[k] = self.usage.get(k, 0) + int(v or 0)


@dataclass
class CommandedRound:
    """One commander iteration: draft → verify → decision."""
    round: int
    draft: str
    verdict: Verdict
    inner_result: AgentResult | None = None   # raw AutonomousAgent output


# ---------------------------------------------------------------------------
# Default retriever — Praxia memory layers
# ---------------------------------------------------------------------------


@dataclass
class DefaultMemoryRetriever:
    """Pulls evidence from PersonalMemory (L1) + SharedMemory (L3) + MarkdownStore (L4).

    Each Source gets a stable id of the form ``<layer>#<index>`` so the
    verifier can attribute claims unambiguously.
    """
    personal: "PersonalMemory | None" = None
    shared: "SharedMemory | None" = None
    frozen: "MarkdownStore | None" = None
    per_layer_limit: int = 5

    def __call__(self, query: str) -> list[Source]:
        sources: list[Source] = []
        sources.extend(self._from_personal(query))
        sources.extend(self._from_shared(query))
        sources.extend(self._from_frozen(query))
        return sources

    def _from_personal(self, query: str) -> list[Source]:
        if self.personal is None:
            return []
        try:
            texts = self.personal.search(query, limit=self.per_layer_limit)
        except Exception:  # pragma: no cover - retriever must never crash
            _log.exception("PersonalMemory search failed")
            return []
        return [
            Source(id=f"L1#{i}", text=str(t), kind="personal_memory")
            for i, t in enumerate(texts) if t
        ]

    def _from_shared(self, query: str) -> list[Source]:
        if self.shared is None:
            return []
        try:
            texts = self.shared.search(query=query, limit=self.per_layer_limit)
        except Exception:  # pragma: no cover
            _log.exception("SharedMemory search failed")
            return []
        return [
            Source(id=f"L3#{i}", text=str(t), kind="shared_memory")
            for i, t in enumerate(texts) if t
        ]

    def _from_frozen(self, query: str) -> list[Source]:
        if self.frozen is None:
            return []
        try:
            entries = self.frozen.list_all()
        except Exception:  # pragma: no cover
            _log.exception("MarkdownStore list_all failed")
            return []
        # Naive keyword filter — MarkdownStore doesn't carry an ANN index.
        # Hosts that want stronger frozen-layer retrieval should wire in a
        # custom retriever (callable) rather than relying on this default.
        q_tokens = {t.lower() for t in query.split() if len(t) >= 3}
        scored: list[tuple[int, Any]] = []
        for entry in entries:
            body = getattr(entry, "body", "") or ""
            title = getattr(entry, "title", "") or ""
            haystack = (title + " " + body).lower()
            hits = sum(1 for t in q_tokens if t in haystack)
            if hits:
                scored.append((hits, entry))
        scored.sort(key=lambda x: -x[0])
        out: list[Source] = []
        for i, (_, entry) in enumerate(scored[: self.per_layer_limit]):
            title = getattr(entry, "title", f"frozen-{i}")
            body = getattr(entry, "body", "")[:2000]
            out.append(Source(
                id=f"L4#{i}",
                text=f"# {title}\n\n{body}",
                kind="frozen",
                metadata={"title": title},
            ))
        return out


# ---------------------------------------------------------------------------
# Commander
# ---------------------------------------------------------------------------


class CommandedAgent:
    """Wraps an :class:`AutonomousAgent` with pre-retrieval + verification.

    Args:
        inner: the underlying autonomous agent that produces the draft.
        verifier: anything satisfying the :class:`Verifier` protocol.
            Default: :class:`LLMGroundingVerifier` using ``inner.llm``.
        retriever: a callable ``(query) -> list[Source]``. Default:
            :class:`DefaultMemoryRetriever` wired against ``inner``.
        max_verify_rounds: maximum redrafts before stopping. Default 3.
            (Round 1 is the first verification of the initial draft; up to
            ``max_verify_rounds - 1`` redrafts will follow.)
        abstain_on_max_rounds: when the budget is exhausted with a
            verdict still in "redraft", emit the abstention message instead
            of forwarding the last unsupported draft. Default True.
        abstain_message: text used when the commander abstains.
        require_citations: append a ``[source_id, …]`` footer to accepted
            answers. Default True.
        per_layer_limit: forwarded to :class:`DefaultMemoryRetriever` when
            no custom retriever is supplied. Default 5.
    """

    def __init__(
        self,
        inner: AutonomousAgent,
        *,
        verifier: Verifier | None = None,
        retriever: Retriever | None = None,
        max_verify_rounds: int = 3,
        abstain_on_max_rounds: bool = True,
        abstain_message: str = DEFAULT_ABSTAIN_MESSAGE,
        require_citations: bool = True,
        per_layer_limit: int = 5,
    ) -> None:
        if max_verify_rounds < 1:
            raise ValueError("max_verify_rounds must be >= 1")
        self.inner = inner
        self.verifier = verifier or LLMGroundingVerifier(llm=inner.llm)
        self.retriever = retriever or self._build_default_retriever(per_layer_limit)
        self.max_verify_rounds = int(max_verify_rounds)
        self.abstain_on_max_rounds = bool(abstain_on_max_rounds)
        self.abstain_message = abstain_message
        self.require_citations = bool(require_citations)

    # --- public API --------------------------------------------------------

    def run(
        self,
        user_input: str,
        *,
        history: list[dict[str, Any]] | None = None,
        sources: list[Source] | None = None,
    ) -> CommandedResult:
        """Run the commander loop.

        Args:
            user_input: the user's question.
            history: prior conversation messages (forwarded to inner).
            sources: pre-computed sources to skip retrieval — useful for
                tests and for hosts that have already done the retrieval.
        """
        if sources is None:
            sources = self.retriever(user_input)

        rounds: list[CommandedRound] = []
        result = CommandedResult(
            answer="",
            verdict=Verdict(  # placeholder — will be replaced after round 1
                groundedness=0.0,
                per_claim=[],
                unsupported_claims=[],
                decision="redraft",
                rationale="not yet evaluated",
            ),
            sources=sources,
        )

        self._audit(
            "commander.run.start",
            f"user:{self.inner.user_id}",
            metadata={
                "input_chars": str(len(user_input)),
                "sources": str(len(sources)),
                "max_rounds": str(self.max_verify_rounds),
            },
        )

        augmented_input = self._build_initial_prompt(user_input, sources)
        last_draft = ""
        last_verdict: Verdict | None = None

        for round_i in range(self.max_verify_rounds):
            inner_result = self.inner.run(augmented_input, history=history)
            result.add_usage(inner_result.usage)
            last_draft = (inner_result.final_text or "").strip()

            verdict = self.verifier.verify(last_draft, sources)
            last_verdict = verdict
            rounds.append(CommandedRound(
                round=round_i,
                draft=last_draft,
                verdict=verdict,
                inner_result=inner_result,
            ))

            self._audit(
                "commander.round",
                f"user:{self.inner.user_id}",
                metadata={
                    "round": str(round_i),
                    "decision": verdict.decision,
                    "groundedness": f"{verdict.groundedness:.3f}",
                    "unsupported": str(len(verdict.unsupported_claims)),
                },
            )

            if verdict.decision == "accept":
                result.answer = self._format_accepted(last_draft, verdict)
                result.verdict = verdict
                result.citations = list(verdict.cited_source_ids)
                result.rounds = rounds
                result.stopped_reason = "accept"
                self._audit_end(result)
                return result

            if verdict.decision == "abstain":
                result.answer = self.abstain_message
                result.verdict = verdict
                result.citations = []
                result.rounds = rounds
                result.stopped_reason = "abstain"
                self._audit_end(result)
                return result

            # decision == "redraft": loop with feedback (unless it's the
            # last round, in which case the next iteration won't happen)
            if round_i < self.max_verify_rounds - 1:
                augmented_input = self._build_redraft_prompt(
                    user_input, last_draft, verdict, sources
                )

        # Exhausted budget with the last verdict still "redraft"
        result.verdict = last_verdict or result.verdict
        result.rounds = rounds
        if self.abstain_on_max_rounds:
            result.answer = self.abstain_message
            result.stopped_reason = "abstain"
        else:
            result.answer = last_draft
            result.citations = list(result.verdict.cited_source_ids)
            result.stopped_reason = "max_rounds"
        self._audit_end(result)
        return result

    # --- prompt builders --------------------------------------------------

    @staticmethod
    def _build_initial_prompt(user_input: str, sources: list[Source]) -> str:
        if not sources:
            return user_input
        src_block = "\n\n".join(
            f"[{s.id}] {s.text.strip()}" for s in sources
        )
        return (
            "Answer the user using ONLY the labelled sources below. If a "
            "claim is not supported by the sources, do not assert it — say "
            "so. When you make a factual statement, mention the source id "
            "you relied on inline (e.g. [L1#2]).\n\n"
            "=== SOURCES ===\n"
            f"{src_block}\n\n"
            "=== USER QUESTION ===\n"
            f"{user_input}"
        )

    @staticmethod
    def _build_redraft_prompt(
        user_input: str,
        prev_draft: str,
        verdict: Verdict,
        sources: list[Source],
    ) -> str:
        unsupported = "\n".join(f"- {c}" for c in verdict.unsupported_claims) or "(none enumerated)"
        src_block = "\n\n".join(
            f"[{s.id}] {s.text.strip()}" for s in sources
        )
        return (
            "Your previous draft was REJECTED by the grounding verifier "
            f"(groundedness={verdict.groundedness:.2f}). The following "
            "claims are not supported by the sources:\n\n"
            f"{unsupported}\n\n"
            "Revise the answer. Either (a) remove or hedge the unsupported "
            "claims, or (b) re-derive them directly from the sources "
            "(cite the source id inline). If the sources genuinely don't "
            "cover the question, say so explicitly — do NOT invent.\n\n"
            "=== SOURCES ===\n"
            f"{src_block}\n\n"
            "=== PREVIOUS DRAFT ===\n"
            f"{prev_draft}\n\n"
            "=== USER QUESTION ===\n"
            f"{user_input}"
        )

    # --- formatting -------------------------------------------------------

    def _format_accepted(self, draft: str, verdict: Verdict) -> str:
        if not self.require_citations or not verdict.cited_source_ids:
            return draft
        cited = ", ".join(verdict.cited_source_ids)
        # Avoid double-appending if the model already added the citations
        if f"[{cited}]" in draft or all(f"[{sid}]" in draft for sid in verdict.cited_source_ids):
            return draft
        return f"{draft}\n\nSources: [{cited}]"

    # --- defaults ---------------------------------------------------------

    def _build_default_retriever(self, per_layer_limit: int) -> Retriever:
        """Construct a :class:`DefaultMemoryRetriever` wired to the inner
        agent's memory layers."""
        memory_dir = Path(self.inner.memory_dir)
        personal = None
        shared = None
        frozen = None

        # Lazy imports so optional pieces don't break a minimal setup.
        try:
            personal = self.inner._personal_memory()  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover
            _log.debug("PersonalMemory unavailable for default retriever")

        try:
            from praxia.memory.shared import SharedMemory as _SM
            shared = _SM(org_id=self.inner.org_id, storage_dir=memory_dir / "shared")
        except Exception:  # pragma: no cover
            _log.debug("SharedMemory unavailable for default retriever")

        try:
            from praxia.memory.markdown_store import MarkdownStore as _MS
            frozen = _MS(root_dir=memory_dir / "frozen")
        except Exception:  # pragma: no cover
            _log.debug("MarkdownStore unavailable for default retriever")

        return DefaultMemoryRetriever(
            personal=personal,
            shared=shared,
            frozen=frozen,
            per_layer_limit=per_layer_limit,
        )

    # --- audit ------------------------------------------------------------

    def _audit(
        self,
        action: str,
        resource: str,
        *,
        outcome: str = "success",
        metadata: dict[str, str] | None = None,
    ) -> None:
        try:
            self.inner.auth.audit.record(
                actor_id=self.inner.user_id,
                actor_role=self.inner.role,
                action=action,
                resource=resource,
                outcome=outcome,
                metadata=metadata or {},
            )
        except Exception:  # pragma: no cover - audit must never break the loop
            _log.exception("commander audit recording failed")

    def _audit_end(self, result: CommandedResult) -> None:
        self._audit(
            "commander.run.end",
            f"user:{self.inner.user_id}",
            outcome="success" if result.stopped_reason == "accept" else "warning",
            metadata={
                "stopped_reason": result.stopped_reason,
                "rounds": str(len(result.rounds)),
                "final_groundedness": f"{result.verdict.groundedness:.3f}",
                "citations": str(len(result.citations)),
            },
        )
