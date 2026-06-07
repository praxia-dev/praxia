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


TaskClassifier = Callable[[str], str]
"""Signature: ``(user_input: str) -> task_kind: str``.

Returned kinds:
  ``"knowledge"`` (default — grounded verification applies)
  ``"action"``    (skip verifier, environment provides correctness:
                   code/tool/command flows)
  ``"synthesis"`` (retrieve sources as inspiration, but skip the
                   verifier: the user is asking for a draft / proposal /
                   summary / creative extension where many claims will
                   be novel by design and can't be claim-by-claim
                   grounded against the corpus)

Verification finding K6: questions that the *environment* can self-verify
(tests pass, command exits 0, file exists) don't need a grounding gate.
Knowledge-QA over private corpora does. Generative / synthesis tasks
fall in between — sources are useful as material, but per-claim
grounding doesn't apply.

The default classifier is keyword-based and intentionally conservative —
when in doubt, treat as ``knowledge`` so the verifier still runs.
"""


# ---------------------------------------------------------------------------
# Default abstention text
# ---------------------------------------------------------------------------

DEFAULT_ABSTAIN_MESSAGE = (
    "I don't have enough grounded information in the available sources to "
    "answer this confidently.\n\n"
    "Things you can try:\n"
    "  • If you wanted me to process MULTIPLE documents in parallel "
    "(e.g. \"extract action items from all PDFs in Documents\"), "
    "rephrase to make the list explicit: \"for each PDF in Documents, "
    "extract the action items.\" That triggers the batch tool which "
    "fans out one agent run per file.\n"
    "  • If you wanted a one-shot answer, point me at the specific "
    "folder or rephrase with concrete keywords from the document.\n"
    "  • Add the relevant documents to a Documents folder if you "
    "haven't yet (auto-watch will index them)."
)


# Tokens that strongly suggest the user is asking for code / a command /
# a tool invocation rather than a knowledge-QA answer. Bilingual (EN/JA)
# because Praxia's primary deployments are both. Kept narrow on purpose:
# the verifier is a safety net, so a false negative here (knowledge
# wrongly classified as action) is much worse than a false positive
# (action wrongly classified as knowledge).
_ACTION_KEYWORDS = (
    # English — imperative / coding / tool verbs
    "write code", "implement", "refactor", "debug",
    "run the", "run this", "execute", "deploy",
    "fix the bug", "patch", "compile", "build the",
    "install", "rebase", "git ", "npm ", "pip install",
    # Japanese
    "コードを書", "実装して", "リファクタ", "デバッグ",
    "実行して", "走らせて", "ビルドして", "コンパイル",
    "インストール", "デプロイ",
)


# Tokens that flag a synthesis / generative request — the user is
# asking the agent to PRODUCE a new artefact (proposal, summary,
# slide deck, draft) using the corpus as inspiration, not to
# REPORT facts from it. Per-claim grounding doesn't fit:
# 「営業支援テーマの資料を元に提案資料を作って」 contains many novel
# claims by construction.
_SYNTHESIS_KEYWORDS = (
    # English — generative / creative verbs
    "draft", "make a", "write a", "create a", "design a",
    "compose", "outline", "summarize", "summarise", "brainstorm",
    "propose", "proposal", "make slides", "make a presentation",
    "make a report", "write a report", "generate a", "render a",
    "design slides", "design a deck",
    # Japanese
    "作成して", "作って", "起草", "草稿", "下書き",
    "提案", "プレゼン", "発表資料",
    "アイデア", "考案", "案を",
    "サマリ", "要約", "纏めて", "まとめて",
    "デザイン", "資料を作",
    "出力して下さい", "出力してください", "生成して",
)


def default_task_classifier(user_input: str) -> str:
    """Cheap regex-free classifier. Returns one of:

    - ``"action"``: the input contains an imperative coding/tool verb.
    - ``"synthesis"``: the input asks for a generated artefact (draft,
      proposal, summary, deck). Sources are still retrieved (as
      inspiration) but the verifier is bypassed because per-claim
      grounding doesn't fit a creative output.
    - ``"knowledge"`` (default): grounded fact-QA — verifier runs.

    Precedence: action > synthesis > knowledge. A request to "write
    code for a slide-deck generator" reads as code work, not
    synthesis.
    """
    lowered = user_input.lower()
    for kw in _ACTION_KEYWORDS:
        if kw in lowered:
            return "action"
    for kw in _SYNTHESIS_KEYWORDS:
        if kw in lowered:
            return "synthesis"
    return "knowledge"


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
    stopped_reason: str = "accept"            # accept | abstain | max_rounds | no_improvement | bypass_action | no_sources_fallback | synthesis_pass
    task_kind: str = "knowledge"              # knowledge | action | synthesis — picked by TaskClassifier
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
    """Pulls evidence from PersonalMemory (L1) + SharedMemory (L3) + MarkdownStore (L4)
    and, optionally, from local-folder documents the user has ingested via the
    desktop app (search callable wired in by the host).

    Each Source gets a stable id of the form ``<layer>#<index>`` so the
    verifier can attribute claims unambiguously. Documents use the ``D#``
    prefix to keep them distinct from L1-L4 memory.

    When a ``decomposer`` is supplied, the retriever splits the query into
    sub-questions and unions the per-sub retrieval results, deduplicated
    by Source id. Single-hop questions pass through as-is, so adding a
    decomposer does not penalise simple lookups (verification finding K2).
    """
    personal: "PersonalMemory | None" = None
    shared: "SharedMemory | None" = None
    frozen: "MarkdownStore | None" = None
    # When set, called as documents_search(query) -> list[dict] with keys
    # text / doc_id / relative_path / score. Wired in by hosts that have a
    # local-document store (see praxia.server.routers.documents.search_for_user).
    documents_search: "Any" = None        # Callable[[str], list[dict]] | None
    decomposer: "Any" = None              # QueryDecomposer | None
    per_layer_limit: int = 5

    def __call__(self, query: str) -> list[Source]:
        sub_queries = self._sub_queries(query)

        # Single-hop: original behaviour, including stable L1#0/L3#0 ids.
        if len(sub_queries) <= 1:
            q = sub_queries[0] if sub_queries else query
            sources: list[Source] = []
            sources.extend(self._from_personal(q))
            sources.extend(self._from_shared(q))
            sources.extend(self._from_frozen(q))
            sources.extend(self._from_documents(q))
            return sources

        # Multi-hop: retrieve per sub-question, union with stable ids.
        # We index Sources by (layer, source-of-truth key) so the same
        # memory chunk surfaced by two sub-questions only appears once.
        seen: dict[tuple[str, str], Source] = {}
        ordered_keys: list[tuple[str, str]] = []
        for sq in sub_queries:
            for layer_get in (self._from_personal, self._from_shared,
                              self._from_frozen, self._from_documents):
                for src in layer_get(sq):
                    key = (src.kind, src.text)
                    if key in seen:
                        continue
                    seen[key] = src
                    ordered_keys.append(key)

        # Rewrite ids so they remain sequential and human-readable
        # across the unioned set: L1#0, L1#1, L3#0, ...
        per_kind_counter: dict[str, int] = {}
        prefix_for_kind = {
            "personal_memory": "L1",
            "shared_memory": "L3",
            "frozen": "L4",
            "local_document": "D",
        }
        out: list[Source] = []
        for key in ordered_keys:
            src = seen[key]
            prefix = prefix_for_kind.get(src.kind, src.kind[:2].upper() or "X")
            idx = per_kind_counter.get(prefix, 0)
            per_kind_counter[prefix] = idx + 1
            out.append(Source(
                id=f"{prefix}#{idx}",
                text=src.text,
                kind=src.kind,
                metadata=src.metadata,
            ))
        return out

    def _sub_queries(self, query: str) -> list[str]:
        if self.decomposer is None:
            return [query]
        try:
            subs = self.decomposer.decompose(query) or []
        except Exception:  # pragma: no cover - retriever must never crash
            _log.exception("Decomposer failed; falling back to single-pass")
            return [query]
        subs = [s for s in subs if isinstance(s, str) and s.strip()]
        return subs or [query]

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

    def _from_documents(self, query: str) -> list[Source]:
        if self.documents_search is None:
            return []
        try:
            hits = self.documents_search(query) or []
        except Exception:  # pragma: no cover
            _log.exception("documents_search callable failed")
            return []
        out: list[Source] = []
        for i, h in enumerate(hits[: self.per_layer_limit]):
            text = h.get("text") if isinstance(h, dict) else None
            if not text:
                continue
            out.append(Source(
                id=f"D#{i}",
                text=str(text),
                kind="local_document",
                metadata={
                    "doc_id": h.get("doc_id"),
                    "folder_id": h.get("folder_id"),
                    "relative_path": h.get("relative_path"),
                    "chunk_index": h.get("chunk_index"),
                    "score": h.get("score"),
                },
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
            Default: :class:`LLMGroundingVerifier` using ``scout_llm`` if
            provided, else ``inner.llm``.
        retriever: a callable ``(query) -> list[Source]``. Default:
            :class:`DefaultMemoryRetriever` wired against ``inner``. When
            ``scout_llm`` is set, the default retriever auto-attaches an
            :class:`LLMQueryDecomposer` so multi-hop questions get split
            into sub-queries.
        scout_llm: a smaller / cheaper LLM used for "scout" sub-calls —
            grounding-verifier claim extraction and query decomposition.
            The main answer still goes through ``inner.llm``. Set to
            ``None`` (default) to use one LLM for everything.
        max_verify_rounds: maximum redrafts before stopping. Default 3.
            (Round 1 is the first verification of the initial draft; up to
            ``max_verify_rounds - 1`` redrafts will follow.)
        abstain_on_max_rounds: when the budget is exhausted with a
            verdict still in "redraft", emit the abstention message instead
            of forwarding the last unsupported draft. Default True.
        min_groundedness_improvement: minimum increase in
            ``Verdict.groundedness`` that a redraft must produce over the
            previous round to be considered making progress. Default 0.05
            (5 pt on a 0..1 scale). Set to 0 to disable early stopping.
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
        task_classifier: TaskClassifier | None = None,
        scout_llm: Any = None,
        max_verify_rounds: int = 3,
        abstain_on_max_rounds: bool = True,
        min_groundedness_improvement: float = 0.05,
        fallback_when_no_sources: bool = True,
        abstain_message: str = DEFAULT_ABSTAIN_MESSAGE,
        require_citations: bool = True,
        per_layer_limit: int = 5,
    ) -> None:
        if max_verify_rounds < 1:
            raise ValueError("max_verify_rounds must be >= 1")
        if min_groundedness_improvement < 0:
            raise ValueError("min_groundedness_improvement must be >= 0")
        self.inner = inner
        self.scout_llm = scout_llm
        # The grounding verifier and the query decomposer are the
        # "scout" sub-calls — they extract structured JSON / split a
        # question into atomic claims. A smaller LLM is fine for these.
        sub_llm = scout_llm if scout_llm is not None else inner.llm
        self.verifier = verifier or LLMGroundingVerifier(llm=sub_llm)
        self.retriever = retriever or self._build_default_retriever(
            per_layer_limit, decomposer_llm=sub_llm if scout_llm is not None else None
        )
        self.task_classifier = task_classifier or default_task_classifier
        self.max_verify_rounds = int(max_verify_rounds)
        self.abstain_on_max_rounds = bool(abstain_on_max_rounds)
        self.min_groundedness_improvement = float(min_groundedness_improvement)
        self.fallback_when_no_sources = bool(fallback_when_no_sources)
        self.abstain_message = abstain_message
        self.require_citations = bool(require_citations)

    # --- public API --------------------------------------------------------

    def run(
        self,
        user_input: str,
        *,
        history: list[dict[str, Any]] | None = None,
        sources: list[Source] | None = None,
        images: list[dict[str, str]] | None = None,
    ) -> CommandedResult:
        """Run the commander loop.

        Args:
            user_input: the user's question.
            history: prior conversation messages (forwarded to inner).
            sources: pre-computed sources to skip retrieval — useful for
                tests and for hosts that have already done the retrieval.
            images: optional vision attachments — same shape as
                ``AutonomousAgent.run(images=...)`` expects. Passed
                through to every inner.run() call in this loop so the
                vision-capable LLM can use the image as evidence in
                each draft/redraft round. The verifier doesn't see the
                image; it only judges the draft against retrieved
                text sources.
        """
        task_kind = self.task_classifier(user_input)

        # K6: action-class tasks (code, tool, command) don't benefit from
        # the grounding gate — the environment is the verifier. Hand
        # straight to the inner agent and return its draft as-is.
        if task_kind == "action":
            inner_result = self.inner.run(user_input, history=history, images=images)
            self._audit(
                "commander.bypass_action",
                f"user:{self.inner.user_id}",
                metadata={"input_chars": str(len(user_input))},
            )
            result = CommandedResult(
                answer=(inner_result.final_text or "").strip(),
                verdict=Verdict(
                    groundedness=0.0,
                    per_claim=[],
                    unsupported_claims=[],
                    decision="accept",
                    rationale="Action-class task; grounding verifier bypassed.",
                ),
                sources=[],
                stopped_reason="bypass_action",
                task_kind=task_kind,
            )
            result.add_usage(inner_result.usage)
            return result

        if sources is None:
            sources = self.retriever(user_input)

        # Synthesis path: user asked for a generated artefact (proposal,
        # draft, slide deck, summary). Retrieve sources so the LLM can
        # use them as inspiration, augment the prompt the same way the
        # verifier-mode would, but DON'T run the verifier — per-claim
        # grounding rejects creative content by design. The bare
        # inner agent then produces the artefact with the sources
        # already in context.
        if task_kind == "synthesis":
            augmented = self._build_initial_prompt(user_input, sources) if sources else user_input
            inner_result = self.inner.run(augmented, history=history, images=images)
            self._audit(
                "commander.synthesis_pass",
                f"user:{self.inner.user_id}",
                metadata={
                    "input_chars": str(len(user_input)),
                    "sources": str(len(sources)),
                },
            )
            synth_result = CommandedResult(
                answer=(inner_result.final_text or "").strip(),
                verdict=Verdict(
                    groundedness=0.0,
                    per_claim=[],
                    unsupported_claims=[],
                    decision="accept",
                    rationale=(
                        "Synthesis request — sources provided as "
                        "inspiration; per-claim grounding not applied."
                    ),
                ),
                sources=sources,
                stopped_reason="synthesis_pass",
                task_kind=task_kind,
                # Expose the source ids so the UI can still link the
                # output to the inspiration material — they aren't
                # "verified citations" but they ARE traceable.
                citations=[s.id for s in sources],
            )
            synth_result.add_usage(inner_result.usage)
            return synth_result

        # Sensible-default fallback: if the retriever returned nothing
        # there is literally nothing to ground claims against. Forcing
        # an abstain in that case turns the agent into a useless
        # "I don't know" machine for users who haven't ingested any
        # documents / memory yet (which is every first-launch user).
        # Skip verification entirely and let the inner agent answer
        # like a normal chat. The stopped_reason makes the path
        # auditable so callers know no verification happened.
        if self.fallback_when_no_sources and not sources:
            inner_result = self.inner.run(user_input, history=history, images=images)
            self._audit(
                "commander.no_sources_fallback",
                f"user:{self.inner.user_id}",
                metadata={"input_chars": str(len(user_input))},
            )
            fallback_result = CommandedResult(
                answer=(inner_result.final_text or "").strip(),
                verdict=Verdict(
                    groundedness=0.0,
                    per_claim=[],
                    unsupported_claims=[],
                    decision="accept",
                    rationale=(
                        "No sources retrieved; verification skipped. "
                        "Response is an unverified chat answer."
                    ),
                ),
                sources=[],
                stopped_reason="no_sources_fallback",
                task_kind=task_kind,
            )
            fallback_result.add_usage(inner_result.usage)
            return fallback_result

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
            task_kind=task_kind,
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
        prev_groundedness: float | None = None

        for round_i in range(self.max_verify_rounds):
            inner_result = self.inner.run(augmented_input, history=history, images=images)
            result.add_usage(inner_result.usage)
            last_draft = (inner_result.final_text or "").strip()

            verdict = self.verifier.verify(last_draft, sources)
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

            # decision == "redraft": before queueing another draft, check
            # whether the previous redraft actually moved the needle. If
            # groundedness didn't improve by at least
            # `min_groundedness_improvement`, the loop is stuck — bail out
            # with `abstain` rather than burning more rounds for nothing
            # (verification finding K4: self-evaluation loops without an
            # external improvement signal cannot decide when to stop).
            if (
                self.min_groundedness_improvement > 0.0
                and prev_groundedness is not None
                and verdict.groundedness - prev_groundedness < self.min_groundedness_improvement
            ):
                self._audit(
                    "commander.no_improvement",
                    f"user:{self.inner.user_id}",
                    metadata={
                        "round": str(round_i),
                        "groundedness_prev": f"{prev_groundedness:.3f}",
                        "groundedness_now": f"{verdict.groundedness:.3f}",
                    },
                )
                result.answer = self.abstain_message
                result.verdict = verdict
                result.citations = []
                result.rounds = rounds
                result.stopped_reason = "no_improvement"
                self._audit_end(result)
                return result

            prev_groundedness = verdict.groundedness
            last_verdict = verdict

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

    def _build_default_retriever(
        self,
        per_layer_limit: int,
        *,
        decomposer_llm: Any = None,
    ) -> Retriever:
        """Construct a :class:`DefaultMemoryRetriever` wired to the inner
        agent's memory layers.

        When ``decomposer_llm`` is provided, an
        :class:`LLMQueryDecomposer` is auto-attached so multi-hop
        questions are split into sub-queries before retrieval. This is
        how a CommandedAgent with a ``scout_llm`` ends up doing
        decomposition without callers having to wire it manually.
        """
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

        # Local-document store (populated by the desktop app's folder
        # ingestion). The search helper has no FastAPI dependency, but the
        # try/except keeps this safe if the module shape ever changes.
        documents_search = None
        try:
            from praxia.server.routers.documents import search_for_user
            user_id = self.inner.user_id

            def _docs_search(q: str):
                return search_for_user(memory_dir, user_id, q, limit=per_layer_limit)

            documents_search = _docs_search
        except Exception:  # pragma: no cover
            _log.debug("Document store unavailable for default retriever")

        decomposer = None
        if decomposer_llm is not None:
            try:
                from praxia.agent.decomposer import LLMQueryDecomposer
                decomposer = LLMQueryDecomposer(llm=decomposer_llm)
            except Exception:  # pragma: no cover
                _log.debug("LLMQueryDecomposer unavailable for default retriever")

        return DefaultMemoryRetriever(
            personal=personal,
            shared=shared,
            frozen=frozen,
            documents_search=documents_search,
            decomposer=decomposer,
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
