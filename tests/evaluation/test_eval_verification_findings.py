"""Tests for the agentic-RAG verification findings reflected in Praxia:

- K4-a: PromotionEngine's self-eval weight is bounded (default tuple).
- K4-b: CommandedAgent aborts early when a redraft fails to improve
  groundedness by at least ``min_groundedness_improvement``.
- K6: action-class prompts bypass the grounding verifier entirely.
- K2: DefaultMemoryRetriever runs the QueryDecomposer and unions hops.

The tests reuse the test doubles from ``test_eval_commander.py`` where
they already exist (fake inner agent, scripted verifier), so the loop
mechanics here are exercised without any LLM/disk traffic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from praxia.agent.commander import (
    CommandedAgent,
    DefaultMemoryRetriever,
    DEFAULT_ABSTAIN_MESSAGE,
    default_task_classifier,
)
from praxia.agent.decomposer import LLMQueryDecomposer, looks_multihop
from praxia.agent.result import AgentResult
from praxia.agent.verifier import ClaimScore, Source, Verdict


# ---------------------------------------------------------------------------
# Test doubles — kept local so we don't depend on test_eval_commander.py
# being run in the same collection.
# ---------------------------------------------------------------------------


class _FakeAudit:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def record(self, **kw: Any) -> None:
        self.records.append(kw)


@dataclass
class _FakeAuth:
    def __post_init__(self) -> None:
        self.audit = _FakeAudit()


@dataclass
class _FakeInnerAgent:
    user_id: str = "tester"
    role: str = "member"
    org_id: str = "test-org"
    memory_dir: str = "/tmp/praxia-test"
    drafts: list[str] = field(default_factory=list)
    received_prompts: list[str] = field(default_factory=list)
    llm: Any = None
    auth: _FakeAuth = field(default_factory=_FakeAuth)

    def run(
        self,
        user_input: str,
        *,
        history: list[dict[str, Any]] | None = None,
        **_kw: Any,
    ) -> AgentResult:
        self.received_prompts.append(user_input)
        if not self.drafts:
            raise RuntimeError("FakeInnerAgent out of canned drafts")
        return AgentResult(
            final_text=self.drafts.pop(0),
            steps=1,
            stopped_reason="completed",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        )


@dataclass
class _ScriptedVerifier:
    verdicts: list[Verdict]

    def verify(self, draft: str, sources: list[Source]) -> Verdict:
        return self.verdicts.pop(0)


def _redraft(score: float, unsupported: tuple[str, ...] = ("u",)) -> Verdict:
    return Verdict(
        groundedness=score,
        per_claim=[ClaimScore(claim="c", score=score, supporting_ids=[])],
        unsupported_claims=list(unsupported),
        decision="redraft",
        rationale="needs more grounding",
    )


def _accept(score: float = 0.9, cited: tuple[str, ...] = ("L1#0",)) -> Verdict:
    return Verdict(
        groundedness=score,
        per_claim=[ClaimScore(claim="c", score=score, supporting_ids=list(cited))],
        unsupported_claims=[],
        decision="accept",
        rationale="all claims supported",
        cited_source_ids=list(cited),
    )


def _src(*pairs: tuple[str, str]) -> list[Source]:
    return [Source(id=i, text=t) for i, t in pairs]


# ---------------------------------------------------------------------------
# K4-a: PromotionEngine default weights — self-eval capped at 0.1
# ---------------------------------------------------------------------------


class TestPromotionWeightsK4a:
    def test_default_weights_favor_external_signals(self) -> None:
        from praxia.memory.promoter import PromotionEngine

        engine = PromotionEngine.__new__(PromotionEngine)
        PromotionEngine.__init__(engine, llm=None)
        # External signals (freq + outcome) must dominate.
        assert engine.weight_freq + engine.weight_outcome > 0.8
        assert engine.weight_self <= 0.15

    def test_override_preserves_back_compat(self) -> None:
        from praxia.memory.promoter import PromotionEngine

        engine = PromotionEngine.__new__(PromotionEngine)
        PromotionEngine.__init__(engine, llm=None, weights=(0.4, 0.3, 0.3))
        assert (engine.weight_freq, engine.weight_outcome, engine.weight_self) == (0.4, 0.3, 0.3)

    def test_self_eval_alone_cannot_auto_promote_at_default(self) -> None:
        """Even perfect self-eval (1.0) with zero outcome should not clear
        the auto-promote threshold by itself — K4 says self-evaluation
        cannot carry a promotion decision.
        """
        from praxia.memory.promoter import PromotionEngine

        engine = PromotionEngine.__new__(PromotionEngine)
        PromotionEngine.__init__(engine, llm=None)
        # Worst-case freq (0.0), no outcome, max self-eval
        final = (
            engine.weight_freq * 0.0
            + engine.weight_outcome * 0.0
            + engine.weight_self * 1.0
        )
        assert final < engine.auto_threshold
        assert final < engine.review_threshold


# ---------------------------------------------------------------------------
# K4-b: CommandedAgent early abstain on no groundedness improvement
# ---------------------------------------------------------------------------


class TestNoImprovementStopK4b:
    def test_flat_groundedness_triggers_no_improvement_abort(self) -> None:
        # Round 1: 0.5, Round 2: 0.5 → no improvement → abort.
        inner = _FakeInnerAgent(drafts=["d1", "d2", "d3"])
        verifier = _ScriptedVerifier(verdicts=[
            _redraft(0.5),
            _redraft(0.5),
            _redraft(0.5),  # never reached
        ])
        agent = CommandedAgent(
            inner,  # type: ignore[arg-type]
            verifier=verifier,
            retriever=lambda q: _src(("L1#0", "x")),
            max_verify_rounds=3,
        )
        result = agent.run("What is the capital of France?")
        assert result.stopped_reason == "no_improvement"
        assert result.answer == DEFAULT_ABSTAIN_MESSAGE
        # Stops at round 1 (zero-indexed) — only 2 rounds consumed.
        assert len(result.rounds) == 2

    def test_improving_groundedness_does_not_trigger_abort(self) -> None:
        # 0.5 → 0.7 (+0.20, well above 0.05 default) → keep going → accept.
        inner = _FakeInnerAgent(drafts=["d1", "d2"])
        verifier = _ScriptedVerifier(verdicts=[
            _redraft(0.5),
            _accept(0.9, cited=("L1#0",)),
        ])
        agent = CommandedAgent(
            inner,  # type: ignore[arg-type]
            verifier=verifier,
            retriever=lambda q: _src(("L1#0", "x")),
            max_verify_rounds=3,
        )
        result = agent.run("knowledge question about something")
        assert result.stopped_reason == "accept"

    def test_zero_min_disables_early_stop(self) -> None:
        inner = _FakeInnerAgent(drafts=["d1", "d2"])
        verifier = _ScriptedVerifier(verdicts=[
            _redraft(0.5),
            _redraft(0.5),
        ])
        agent = CommandedAgent(
            inner,  # type: ignore[arg-type]
            verifier=verifier,
            retriever=lambda q: _src(("L1#0", "x")),
            max_verify_rounds=2,
            min_groundedness_improvement=0.0,
        )
        result = agent.run("knowledge question about something")
        # No early stop → max_rounds path → default abstain
        assert result.stopped_reason == "abstain"


# ---------------------------------------------------------------------------
# K6: action-class prompts bypass the verifier
# ---------------------------------------------------------------------------


class TestTaskRouterK6:
    @pytest.mark.parametrize("prompt", [
        "implement a binary search in python",
        "Run the script and tell me what breaks",
        "refactor this code to use async/await",
        "git rebase main into my branch",
        "コードを書いてください: バイナリサーチ",
        "実装して: スタックの push と pop",
    ])
    def test_action_prompts_classified_as_action(self, prompt: str) -> None:
        assert default_task_classifier(prompt) == "action"

    @pytest.mark.parametrize("prompt", [
        "What is the capital of France?",
        "Who is the CEO of Acme?",
        "次の四半期の売上計画を教えて",
        "SOC2 監査の保持期間は何年ですか",
    ])
    def test_knowledge_prompts_classified_as_knowledge(self, prompt: str) -> None:
        assert default_task_classifier(prompt) == "knowledge"

    def test_action_path_bypasses_verifier(self) -> None:
        """Action prompts must never reach the verifier — the inner agent's
        draft becomes the answer as-is.
        """
        inner = _FakeInnerAgent(drafts=["the resulting code"])
        verifier_calls: list[tuple[str, list[Source]]] = []

        class _SpyVerifier:
            def verify(self, draft: str, sources: list[Source]) -> Verdict:
                verifier_calls.append((draft, sources))
                return _accept()

        retrieve_calls: list[str] = []
        def _ret(q: str) -> list[Source]:
            retrieve_calls.append(q)
            return _src(("L1#0", "x"))

        agent = CommandedAgent(
            inner,  # type: ignore[arg-type]
            verifier=_SpyVerifier(),
            retriever=_ret,
        )
        result = agent.run("Implement a sorting function in TypeScript.")
        assert result.task_kind == "action"
        assert result.stopped_reason == "bypass_action"
        assert result.answer == "the resulting code"
        assert verifier_calls == []   # verifier NEVER called
        assert retrieve_calls == []   # retriever NEVER called

    def test_knowledge_path_uses_verifier(self) -> None:
        inner = _FakeInnerAgent(drafts=["the answer [L1#0]"])
        verifier = _ScriptedVerifier(verdicts=[_accept(cited=("L1#0",))])
        agent = CommandedAgent(
            inner,  # type: ignore[arg-type]
            verifier=verifier,
            retriever=lambda q: _src(("L1#0", "evidence")),
        )
        result = agent.run("What is X?")
        assert result.task_kind == "knowledge"
        assert result.stopped_reason == "accept"

    def test_custom_classifier_can_override(self) -> None:
        inner = _FakeInnerAgent(drafts=["d"])
        agent = CommandedAgent(
            inner,  # type: ignore[arg-type]
            verifier=_ScriptedVerifier(verdicts=[]),
            retriever=lambda q: _src(("L1#0", "x")),
            task_classifier=lambda q: "action",  # always bypass
        )
        result = agent.run("nominally a knowledge question")
        assert result.stopped_reason == "bypass_action"


# ---------------------------------------------------------------------------
# K2: QueryDecomposer + multi-hop retrieval
# ---------------------------------------------------------------------------


class TestDecomposerHeuristic:
    @pytest.mark.parametrize("q", [
        "compare X and Y in terms of performance",
        "What is the relationship between Alice and the company she works for?",
        "AcmeとBetaの違いを教えて",
        "両方の会社の創業者を比較してください",
    ])
    def test_multihop_hints_detected(self, q: str) -> None:
        assert looks_multihop(q)

    @pytest.mark.parametrize("q", [
        "What is the capital of France?",
        "今日の天気は",
        "",
        "X?",  # too short
    ])
    def test_single_hop_not_flagged(self, q: str) -> None:
        assert not looks_multihop(q)


class _FakeDecomposer:
    """Decomposer with a scripted output for testing the retriever."""

    def __init__(self, mapping: dict[str, list[str]]) -> None:
        self.mapping = mapping
        self.calls: list[str] = []

    def decompose(self, query: str) -> list[str]:
        self.calls.append(query)
        return self.mapping.get(query, [query])


class _FakePersonal:
    """Stand-in for PersonalMemory.search returning per-query results."""

    def __init__(self, mapping: dict[str, list[str]]) -> None:
        self.mapping = mapping
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, *, limit: int = 5) -> list[str]:
        self.calls.append((query, limit))
        return self.mapping.get(query, [])


class TestRetrieverDecompositionK2:
    def test_single_hop_passes_through_unchanged(self) -> None:
        personal = _FakePersonal({"What is X?": ["fact about X"]})
        decomposer = _FakeDecomposer({"What is X?": ["What is X?"]})
        ret = DefaultMemoryRetriever(
            personal=personal,  # type: ignore[arg-type]
            decomposer=decomposer,
        )
        out = ret("What is X?")
        assert [s.id for s in out] == ["L1#0"]
        assert out[0].text == "fact about X"
        # Single-hop hits the single-pass branch — only the original query
        # is retrieved against.
        assert personal.calls == [("What is X?", 5)]

    def test_multi_hop_runs_each_subquery_and_unions(self) -> None:
        personal = _FakePersonal({
            "Who founded Acme?": ["Alice founded Acme."],
            "What does Alice work on?": ["Alice researches LLMs."],
        })
        decomposer = _FakeDecomposer({
            "Who is the founder of Acme and what do they research?":
                ["Who founded Acme?", "What does Alice work on?"],
        })
        ret = DefaultMemoryRetriever(
            personal=personal,  # type: ignore[arg-type]
            decomposer=decomposer,
        )
        out = ret("Who is the founder of Acme and what do they research?")
        # Both hops contribute, ids are renumbered, order preserved.
        assert {s.text for s in out} == {
            "Alice founded Acme.",
            "Alice researches LLMs.",
        }
        assert [s.id for s in out] == ["L1#0", "L1#1"]

    def test_dedup_across_hops(self) -> None:
        # Same chunk surfaces from two different sub-questions — it must
        # appear once in the unioned output.
        personal = _FakePersonal({
            "Q1": ["shared fact", "fact 1"],
            "Q2": ["shared fact", "fact 2"],
        })
        decomposer = _FakeDecomposer({"orig": ["Q1", "Q2"]})
        ret = DefaultMemoryRetriever(
            personal=personal,  # type: ignore[arg-type]
            decomposer=decomposer,
        )
        out = ret("orig")
        texts = [s.text for s in out]
        assert texts.count("shared fact") == 1
        assert "fact 1" in texts and "fact 2" in texts
        # 3 unique chunks → ids are L1#0..L1#2
        assert [s.id for s in out] == ["L1#0", "L1#1", "L1#2"]

    def test_no_decomposer_keeps_original_behaviour(self) -> None:
        personal = _FakePersonal({"orig": ["x"]})
        ret = DefaultMemoryRetriever(personal=personal)  # type: ignore[arg-type]
        out = ret("orig")
        assert [s.text for s in out] == ["x"]
        assert personal.calls == [("orig", 5)]


class TestLLMQueryDecomposerBypass:
    """The default LLMQueryDecomposer should short-circuit single-hop
    inputs without ever calling the LLM (verification finding K1: don't
    pay verification cost on simple lookups).
    """

    def test_single_hop_skips_llm_call(self) -> None:
        class _ExplosiveLLM:
            def complete(self, *a: Any, **kw: Any) -> str:
                raise AssertionError("LLM must not be called for single-hop")

        dec = LLMQueryDecomposer(llm=_ExplosiveLLM())  # type: ignore[arg-type]
        assert dec.decompose("What is the capital of France?") == [
            "What is the capital of France?"
        ]


# ---------------------------------------------------------------------------
# Scout LLM split — small model for decomposer + verifier sub-calls
# ---------------------------------------------------------------------------


class TestScoutLLMSplit:
    """CommandedAgent's optional ``scout_llm`` parameter lets callers pin
    decomposition + verifier claim-extraction to a cheaper LLM while the
    main answer still runs on the big one. This split is the K7 cost-vs-
    quality lever from `agentic_rag_verification_lessons.md`.
    """

    def test_scout_llm_used_for_default_verifier(self) -> None:
        from praxia.agent.verifier import LLMGroundingVerifier

        class _MarkedLLM:
            def __init__(self, tag: str) -> None:
                self.tag = tag

        main_llm = _MarkedLLM("main")
        scout = _MarkedLLM("scout")

        inner = _FakeInnerAgent(drafts=[])
        inner.llm = main_llm  # type: ignore[assignment]
        agent = CommandedAgent(
            inner,  # type: ignore[arg-type]
            retriever=lambda q: [],
            scout_llm=scout,
        )
        # Default verifier is auto-constructed — it should pick up the
        # scout LLM, not the main inner.llm.
        assert isinstance(agent.verifier, LLMGroundingVerifier)
        assert agent.verifier.llm is scout

    def test_scout_llm_attaches_decomposer_to_default_retriever(self) -> None:
        """When scout_llm is provided AND no explicit retriever is passed,
        the auto-built DefaultMemoryRetriever should carry a decomposer
        bound to the scout LLM."""
        class _MarkedLLM:
            def __init__(self, tag: str) -> None:
                self.tag = tag

        scout = _MarkedLLM("scout")

        inner = _FakeInnerAgent(drafts=[])
        inner.llm = _MarkedLLM("main")  # type: ignore[assignment]
        agent = CommandedAgent(inner, scout_llm=scout)  # type: ignore[arg-type]

        retr = agent.retriever
        # DefaultMemoryRetriever exposes the decomposer it was built with.
        assert getattr(retr, "decomposer", None) is not None
        assert retr.decomposer.llm is scout  # type: ignore[union-attr]

    def test_no_scout_llm_no_decomposer_by_default(self) -> None:
        """Without scout_llm, the existing default behaviour is preserved
        — no decomposer is auto-attached, so single-LLM setups don't
        suddenly start paying for decomposition calls."""
        class _MarkedLLM:
            pass

        inner = _FakeInnerAgent(drafts=[])
        inner.llm = _MarkedLLM()  # type: ignore[assignment]
        agent = CommandedAgent(inner)  # type: ignore[arg-type]
        retr = agent.retriever
        assert getattr(retr, "decomposer", None) is None

    def test_explicit_verifier_wins_over_scout_llm(self) -> None:
        """If the caller passes a verifier, scout_llm doesn't override it
        — explicit beats implicit."""
        class _MarkedLLM:
            pass

        explicit = _ScriptedVerifier(verdicts=[])
        inner = _FakeInnerAgent(drafts=[])
        inner.llm = _MarkedLLM()  # type: ignore[assignment]
        agent = CommandedAgent(
            inner,  # type: ignore[arg-type]
            verifier=explicit,
            scout_llm=_MarkedLLM(),
        )
        assert agent.verifier is explicit


# ---------------------------------------------------------------------------
# fallback_when_no_sources — verified mode is usable as a default
# ---------------------------------------------------------------------------


class TestNoSourcesFallback:
    """With ``fallback_when_no_sources=True`` (the default since the
    fix), a CommandedAgent run that retrieves zero sources must NOT
    abstain — it should pass through to the bare inner agent, so a
    first-launch user with no documents / memory ingested still gets
    real chat answers instead of "I don't have enough grounded
    information". The abstain-on-no-sources branch is preserved as
    opt-in for compliance deployments that prefer an explicit refusal.
    """

    def test_default_falls_through_when_retriever_empty(self) -> None:
        inner = _FakeInnerAgent(drafts=["unverified hello"])
        verifier_calls: list[str] = []

        class _SpyVerifier:
            def verify(self, draft: str, sources: list[Source]) -> Verdict:
                verifier_calls.append(draft)
                return _accept()

        agent = CommandedAgent(
            inner,  # type: ignore[arg-type]
            verifier=_SpyVerifier(),
            retriever=lambda q: [],  # zero sources
        )
        result = agent.run("hi")
        assert result.stopped_reason == "no_sources_fallback"
        assert result.answer == "unverified hello"
        # Verifier never invoked — there was nothing to verify against
        assert verifier_calls == []
        # task_kind stays "knowledge" so the audit trail is honest
        assert result.task_kind == "knowledge"

    def test_disabling_fallback_keeps_strict_abstain(self) -> None:
        """Compliance-mode deployments can flip the flag off and get
        the old strict-abstain behaviour back — the verifier sees the
        empty source list and abstains explicitly."""
        inner = _FakeInnerAgent(drafts=["d1"])
        # Verifier returns abstain on the empty-source draft (exactly
        # what LLMGroundingVerifier does in production with no sources).
        verifier = _ScriptedVerifier(verdicts=[_accept_or_abstain := _abstain_verdict()])
        agent = CommandedAgent(
            inner,  # type: ignore[arg-type]
            verifier=verifier,
            retriever=lambda q: [],
            fallback_when_no_sources=False,
        )
        result = agent.run("hi")
        # Fallback path NOT taken — the verifier abstain decided it.
        assert result.stopped_reason == "abstain"
        assert result.stopped_reason != "no_sources_fallback"


    def test_synthesis_prompts_skip_verifier_even_with_sources(self) -> None:
        """Bug report: a user with documents asked "Documents の資料を元に
        提案資料のたたき台を出力して下さい" and the verifier abstained
        because the proposal's claims couldn't be grounded source-by-
        source. Synthesis prompts must reach the bare agent — sources
        are still retrieved + injected (so the LLM uses them as
        inspiration) but the verifier is bypassed."""
        from praxia.agent.commander import default_task_classifier

        # 1) Classifier picks "synthesis" for proposal prompts.
        prompts = [
            "提案資料のたたき台を .md と .pptx で出力して下さい",
            "Draft a proposal slide deck about renewal terms",
            "営業支援テーマで効果的な提案資料を作成して",
            "Make a presentation about Q3 priorities",
        ]
        for p in prompts:
            kind = default_task_classifier(p)
            assert kind == "synthesis", f"{p!r} -> {kind}"

        # 2) Synthesis path retrieves sources, augments the prompt,
        # invokes the inner agent, and DOES NOT call the verifier.
        inner = _FakeInnerAgent(drafts=["the proposal draft"])
        verifier_calls: list[str] = []

        class _SpyVerifier:
            def verify(self, draft: str, sources: list[Source]) -> Verdict:
                verifier_calls.append(draft)
                return _accept()

        retrieved = _src(("D#0", "sales-support handbook section 3"))
        agent = CommandedAgent(
            inner,  # type: ignore[arg-type]
            verifier=_SpyVerifier(),
            retriever=lambda q: retrieved,
        )
        result = agent.run("Documents を参考に提案資料を作成して下さい")
        assert result.stopped_reason == "synthesis_pass"
        assert result.task_kind == "synthesis"
        assert result.answer == "the proposal draft"
        assert verifier_calls == []  # verifier NEVER invoked
        # Sources are still surfaced as supplementary citations
        assert result.citations == ["D#0"]
        # The inner agent received the augmented prompt that includes
        # the retrieved source content
        assert any("sales-support handbook" in p for p in inner.received_prompts)

    def test_synthesis_works_even_without_sources(self) -> None:
        """A "make me a 5-slide deck about X" with no documents still
        runs — sources are optional for synthesis."""
        inner = _FakeInnerAgent(drafts=["the deck markdown"])
        agent = CommandedAgent(
            inner,  # type: ignore[arg-type]
            verifier=_ScriptedVerifier(verdicts=[]),
            retriever=lambda q: [],
        )
        result = agent.run("Make a 5-slide deck about Praxia")
        assert result.stopped_reason == "synthesis_pass"
        assert result.answer == "the deck markdown"
        assert result.citations == []

    def test_action_still_beats_synthesis(self) -> None:
        """Precedence: a prompt that mentions both 'write code' and
        'proposal' should classify as action — codegen is more
        specific."""
        from praxia.agent.commander import default_task_classifier
        assert default_task_classifier(
            "write code for a proposal-generator tool"
        ) == "action"

    def test_fallback_skipped_when_sources_present(self) -> None:
        """Sanity: fallback ONLY kicks in when sources are empty. With
        any source, the verifier path runs normally."""
        inner = _FakeInnerAgent(drafts=["d1"])
        verifier_calls: list[str] = []

        class _SpyVerifier:
            def verify(self, draft: str, sources: list[Source]) -> Verdict:
                verifier_calls.append(draft)
                return _accept(cited=("L1#0",))

        agent = CommandedAgent(
            inner,  # type: ignore[arg-type]
            verifier=_SpyVerifier(),
            retriever=lambda q: _src(("L1#0", "evidence")),
        )
        result = agent.run("hi")
        assert result.stopped_reason == "accept"
        assert verifier_calls == ["d1"]


def _abstain_verdict() -> Verdict:
    return Verdict(
        groundedness=0.0,
        per_claim=[],
        unsupported_claims=["no sources"],
        decision="abstain",
        rationale="no sources",
    )
