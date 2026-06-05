"""Unit tests for praxia.agent.commander.

Uses lightweight stand-ins for both the inner agent and the verifier so we
exercise the loop logic without any LLM / disk traffic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from praxia.agent.commander import (
    CommandedAgent,
    CommandedResult,
    DEFAULT_ABSTAIN_MESSAGE,
    DefaultMemoryRetriever,
)
from praxia.agent.result import AgentResult
from praxia.agent.verifier import ClaimScore, Source, Verdict


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


@dataclass
class _FakeAuth:
    """Stand-in for AuthManager — only needs `audit.record`."""
    records: list[dict[str, Any]] = field(default_factory=list)

    class _AuditShim:
        def __init__(self, parent: "_FakeAuth") -> None:
            self.parent = parent

        def record(self, **kw: Any) -> None:
            self.parent.records.append(kw)

    def __post_init__(self) -> None:
        self.audit = self._AuditShim(self)


@dataclass
class _FakeInnerAgent:
    """Stand-in for AutonomousAgent — returns canned drafts from a queue.

    Captures every `run()` call so tests can assert what prompt the
    commander built (initial vs redraft).
    """
    user_id: str = "tester"
    role: str = "member"
    org_id: str = "test-org"
    memory_dir: str = "/tmp/praxia-test"
    drafts: list[str] = field(default_factory=list)
    received_prompts: list[str] = field(default_factory=list)
    received_histories: list[list[dict[str, Any]] | None] = field(default_factory=list)
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
        self.received_histories.append(history)
        if not self.drafts:
            raise RuntimeError("FakeInnerAgent out of canned drafts")
        text = self.drafts.pop(0)
        return AgentResult(
            final_text=text,
            steps=1,
            stopped_reason="completed",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        )


@dataclass
class _ScriptedVerifier:
    """Returns verdicts from a queue, in order."""
    verdicts: list[Verdict]
    seen: list[tuple[str, list[Source]]] = field(default_factory=list)

    def verify(self, draft: str, sources: list[Source]) -> Verdict:
        self.seen.append((draft, list(sources)))
        if not self.verdicts:
            raise RuntimeError("ScriptedVerifier out of verdicts")
        return self.verdicts.pop(0)


def _verdict_accept(score: float = 0.9, cited: list[str] | None = None) -> Verdict:
    return Verdict(
        groundedness=score,
        per_claim=[ClaimScore(claim="x", score=score, supporting_ids=cited or [])],
        unsupported_claims=[],
        decision="accept",
        rationale="strong",
        cited_source_ids=cited or [],
    )


def _verdict_redraft(unsupported: list[str], score: float = 0.5) -> Verdict:
    return Verdict(
        groundedness=score,
        per_claim=[ClaimScore(claim=c, score=0.2) for c in unsupported],
        unsupported_claims=unsupported,
        decision="redraft",
        rationale="needs work",
    )


def _verdict_abstain(score: float = 0.1) -> Verdict:
    return Verdict(
        groundedness=score,
        per_claim=[],
        unsupported_claims=["everything"],
        decision="abstain",
        rationale="too thin",
    )


def _sources(*pairs: tuple[str, str]) -> list[Source]:
    return [Source(id=sid, text=text) for sid, text in pairs]


# ---------------------------------------------------------------------------
# Construction validation
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_max_rounds_must_be_positive(self):
        inner = _FakeInnerAgent()
        with pytest.raises(ValueError, match="max_verify_rounds"):
            CommandedAgent(
                inner,  # type: ignore[arg-type]
                verifier=_ScriptedVerifier(verdicts=[]),
                retriever=lambda q: [],
                max_verify_rounds=0,
            )


# ---------------------------------------------------------------------------
# Happy path: accept on first round
# ---------------------------------------------------------------------------


class TestAcceptPath:
    def test_first_round_accept_returns_with_citations(self):
        inner = _FakeInnerAgent(drafts=["Answer cites [L1#0]."])
        verifier = _ScriptedVerifier(verdicts=[
            _verdict_accept(score=0.9, cited=["L1#0"]),
        ])
        agent = CommandedAgent(
            inner,  # type: ignore[arg-type]
            verifier=verifier,
            retriever=lambda q: _sources(("L1#0", "evidence")),
        )
        result = agent.run("question?")
        assert result.stopped_reason == "accept"
        assert result.verdict.decision == "accept"
        assert result.citations == ["L1#0"]
        assert len(result.rounds) == 1
        # The first prompt includes the sources block
        assert "[L1#0] evidence" in inner.received_prompts[0]
        # Citations footer appended
        assert "Sources: [L1#0]" in result.answer or "[L1#0]" in result.answer

    def test_citations_not_double_appended_when_inline_already_present(self):
        # Inner already wrote [L1#0] inline — commander should NOT add a
        # second footer that duplicates it.
        inner = _FakeInnerAgent(drafts=["The customer wants ROI per [L1#0]."])
        verifier = _ScriptedVerifier(verdicts=[_verdict_accept(cited=["L1#0"])])
        agent = CommandedAgent(
            inner,  # type: ignore[arg-type]
            verifier=verifier,
            retriever=lambda q: _sources(("L1#0", "x")),
        )
        result = agent.run("q?")
        # Don't append a second "Sources: [L1#0]" footer when inline citation exists
        assert result.answer.count("[L1#0]") == 1

    def test_require_citations_false_skips_footer(self):
        inner = _FakeInnerAgent(drafts=["bare answer"])
        verifier = _ScriptedVerifier(verdicts=[_verdict_accept(cited=["L1#0"])])
        agent = CommandedAgent(
            inner,  # type: ignore[arg-type]
            verifier=verifier,
            retriever=lambda q: _sources(("L1#0", "x")),
            require_citations=False,
        )
        result = agent.run("q?")
        assert result.answer == "bare answer"


# ---------------------------------------------------------------------------
# Abstain path
# ---------------------------------------------------------------------------


class TestAbstainPath:
    def test_abstain_returns_abstain_message_and_no_citations(self):
        inner = _FakeInnerAgent(drafts=["I'll just guess things"])
        verifier = _ScriptedVerifier(verdicts=[_verdict_abstain()])
        agent = CommandedAgent(
            inner,  # type: ignore[arg-type]
            verifier=verifier,
            retriever=lambda q: _sources(("L1#0", "x")),
        )
        result = agent.run("q?")
        assert result.stopped_reason == "abstain"
        assert result.answer == DEFAULT_ABSTAIN_MESSAGE
        assert result.citations == []

    def test_custom_abstain_message_used(self):
        inner = _FakeInnerAgent(drafts=["x"])
        verifier = _ScriptedVerifier(verdicts=[_verdict_abstain()])
        agent = CommandedAgent(
            inner,  # type: ignore[arg-type]
            verifier=verifier,
            retriever=lambda q: _sources(("L1#0", "x")),
            abstain_message="custom abstain text",
        )
        result = agent.run("q?")
        assert result.answer == "custom abstain text"


# ---------------------------------------------------------------------------
# Redraft loop
# ---------------------------------------------------------------------------


class TestRedraftLoop:
    def test_redraft_then_accept_on_round_2(self):
        inner = _FakeInnerAgent(drafts=["weak draft", "revised draft [L1#0]"])
        verifier = _ScriptedVerifier(verdicts=[
            _verdict_redraft(["unsupported claim X"], score=0.5),
            _verdict_accept(score=0.9, cited=["L1#0"]),
        ])
        agent = CommandedAgent(
            inner,  # type: ignore[arg-type]
            verifier=verifier,
            retriever=lambda q: _sources(("L1#0", "evidence")),
            max_verify_rounds=3,
        )
        result = agent.run("q?")
        assert result.stopped_reason == "accept"
        assert len(result.rounds) == 2
        # Second prompt is the redraft prompt — should include the
        # unsupported claim feedback
        assert "unsupported claim X" in inner.received_prompts[1]
        assert "REJECTED" in inner.received_prompts[1]

    def test_redraft_then_abstain_returns_abstain_message(self):
        inner = _FakeInnerAgent(drafts=["draft1", "draft2"])
        verifier = _ScriptedVerifier(verdicts=[
            _verdict_redraft(["x"], score=0.5),
            _verdict_abstain(),
        ])
        agent = CommandedAgent(
            inner,  # type: ignore[arg-type]
            verifier=verifier,
            retriever=lambda q: _sources(("L1#0", "x")),
            max_verify_rounds=3,
        )
        result = agent.run("q?")
        assert result.stopped_reason == "abstain"
        assert result.answer == DEFAULT_ABSTAIN_MESSAGE


# ---------------------------------------------------------------------------
# Max rounds budget
# ---------------------------------------------------------------------------


class TestMaxRoundsBudget:
    def test_max_rounds_with_abstain_default(self):
        # 2 rounds, both redraft → exhausted → default policy abstains.
        # min_groundedness_improvement=0 disables the no-improvement
        # early-stop so we can specifically exercise the max-rounds path.
        inner = _FakeInnerAgent(drafts=["d1", "d2"])
        verifier = _ScriptedVerifier(verdicts=[
            _verdict_redraft(["a"]),
            _verdict_redraft(["b"]),
        ])
        agent = CommandedAgent(
            inner,  # type: ignore[arg-type]
            verifier=verifier,
            retriever=lambda q: _sources(("L1#0", "x")),
            max_verify_rounds=2,
            min_groundedness_improvement=0.0,
        )
        result = agent.run("q?")
        assert result.stopped_reason == "abstain"
        assert result.answer == DEFAULT_ABSTAIN_MESSAGE
        assert len(result.rounds) == 2

    def test_max_rounds_without_abstain_returns_last_draft(self):
        inner = _FakeInnerAgent(drafts=["d1", "d2"])
        verifier = _ScriptedVerifier(verdicts=[
            _verdict_redraft(["a"]),
            _verdict_redraft(["b"]),
        ])
        agent = CommandedAgent(
            inner,  # type: ignore[arg-type]
            verifier=verifier,
            retriever=lambda q: _sources(("L1#0", "x")),
            max_verify_rounds=2,
            abstain_on_max_rounds=False,
            min_groundedness_improvement=0.0,
        )
        result = agent.run("q?")
        assert result.stopped_reason == "max_rounds"
        assert result.answer == "d2"  # last draft

    def test_single_round_then_redraft_abstains(self):
        # max_verify_rounds=1 means no actual redraft happens — first
        # verdict is final.
        inner = _FakeInnerAgent(drafts=["only draft"])
        verifier = _ScriptedVerifier(verdicts=[_verdict_redraft(["x"])])
        agent = CommandedAgent(
            inner,  # type: ignore[arg-type]
            verifier=verifier,
            retriever=lambda q: _sources(("L1#0", "x")),
            max_verify_rounds=1,
        )
        result = agent.run("q?")
        assert result.stopped_reason == "abstain"
        assert len(result.rounds) == 1


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


class TestPromptConstruction:
    def test_initial_prompt_includes_user_question_and_sources(self):
        inner = _FakeInnerAgent(drafts=["x"])
        verifier = _ScriptedVerifier(verdicts=[_verdict_accept()])
        agent = CommandedAgent(
            inner,  # type: ignore[arg-type]
            verifier=verifier,
            retriever=lambda q: _sources(("L1#0", "ev1"), ("L3#0", "ev2")),
        )
        agent.run("How do I reset?")
        prompt = inner.received_prompts[0]
        assert "How do I reset?" in prompt
        assert "[L1#0] ev1" in prompt
        assert "[L3#0] ev2" in prompt
        assert "ONLY the labelled sources" in prompt

    def test_no_sources_passes_user_input_through_unchanged(self):
        inner = _FakeInnerAgent(drafts=["x"])
        verifier = _ScriptedVerifier(verdicts=[_verdict_abstain()])  # empty sources → abstain
        agent = CommandedAgent(
            inner,  # type: ignore[arg-type]
            verifier=verifier,
            retriever=lambda q: [],
        )
        agent.run("bare question")
        # When sources is empty, the initial prompt is the user input verbatim
        assert inner.received_prompts[0] == "bare question"

    def test_explicit_sources_skip_retriever(self):
        called: dict[str, int] = {"n": 0}

        def boom(q: str) -> list[Source]:
            called["n"] += 1
            raise AssertionError("retriever should not be called when sources= is passed")

        inner = _FakeInnerAgent(drafts=["x"])
        verifier = _ScriptedVerifier(verdicts=[_verdict_accept(cited=["S1"])])
        agent = CommandedAgent(
            inner,  # type: ignore[arg-type]
            verifier=verifier,
            retriever=boom,
        )
        result = agent.run("q?", sources=_sources(("S1", "x")))
        assert called["n"] == 0
        assert result.stopped_reason == "accept"


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------


class TestAuditLogging:
    def test_audit_records_start_round_and_end(self):
        inner = _FakeInnerAgent(drafts=["x"])
        verifier = _ScriptedVerifier(verdicts=[_verdict_accept(cited=["L1#0"])])
        agent = CommandedAgent(
            inner,  # type: ignore[arg-type]
            verifier=verifier,
            retriever=lambda q: _sources(("L1#0", "x")),
        )
        agent.run("q?")
        actions = [r["action"] for r in inner.auth.records]
        assert "commander.run.start" in actions
        assert "commander.round" in actions
        assert "commander.run.end" in actions

    def test_round_audit_records_decision(self):
        inner = _FakeInnerAgent(drafts=["d1", "d2"])
        verifier = _ScriptedVerifier(verdicts=[
            _verdict_redraft(["a"]),
            _verdict_accept(cited=["L1#0"]),
        ])
        agent = CommandedAgent(
            inner,  # type: ignore[arg-type]
            verifier=verifier,
            retriever=lambda q: _sources(("L1#0", "x")),
        )
        agent.run("q?")
        rounds = [r for r in inner.auth.records if r["action"] == "commander.round"]
        assert len(rounds) == 2
        assert rounds[0]["metadata"]["decision"] == "redraft"
        assert rounds[1]["metadata"]["decision"] == "accept"


# ---------------------------------------------------------------------------
# Default retriever — DefaultMemoryRetriever
# ---------------------------------------------------------------------------


class TestDefaultMemoryRetriever:
    class _StubPersonal:
        def __init__(self, results: list[str]) -> None:
            self.results = results
            self.calls: list[str] = []

        def search(self, query: str, limit: int = 5) -> list[str]:
            self.calls.append(query)
            return self.results[:limit]

    class _StubShared:
        def __init__(self, results: list[str]) -> None:
            self.results = results

        def search(self, *, query: str, limit: int = 5) -> list[str]:
            return self.results[:limit]

    def test_personal_layer_ids_use_L1_prefix(self):
        p = self._StubPersonal(["alpha", "beta"])
        r = DefaultMemoryRetriever(personal=p)  # type: ignore[arg-type]
        sources = r("query")
        assert [s.id for s in sources] == ["L1#0", "L1#1"]
        assert all(s.kind == "personal_memory" for s in sources)

    def test_shared_layer_ids_use_L3_prefix(self):
        s = self._StubShared(["gamma"])
        r = DefaultMemoryRetriever(shared=s)  # type: ignore[arg-type]
        sources = r("query")
        assert sources[0].id == "L3#0"
        assert sources[0].kind == "shared_memory"

    def test_combines_layers_when_all_present(self):
        p = self._StubPersonal(["p1"])
        s = self._StubShared(["s1", "s2"])
        r = DefaultMemoryRetriever(personal=p, shared=s)  # type: ignore[arg-type]
        sources = r("query")
        ids = [s.id for s in sources]
        assert "L1#0" in ids
        assert "L3#0" in ids
        assert "L3#1" in ids

    def test_no_layers_returns_empty(self):
        r = DefaultMemoryRetriever()
        assert r("anything") == []

    def test_per_layer_limit_caps_results(self):
        p = self._StubPersonal(["a", "b", "c", "d", "e", "f"])
        r = DefaultMemoryRetriever(personal=p, per_layer_limit=2)  # type: ignore[arg-type]
        sources = r("q")
        assert len(sources) == 2
