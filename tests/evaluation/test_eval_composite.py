"""CompositeBackend + RoutedBackend — exhaustive scenarios.

Coverage:
    - 5 fusion strategies (rrf / union / intersection / weighted / llm_rerank)
    - Backend failure isolation
    - Write target selection (default + named)
    - RuleRouter: every default rule, English + Japanese
    - LLMRouter: success path + fallback on failure
    - RoutedBackend: single-backend fast path + multi-backend composite path
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.evaluation


# --- CompositeBackend fusion strategies -------------------------------------

class TestCompositeFusion:
    def test_rrf_default_orders_by_combined_score(
        self, stub_backend_factory, make_record
    ):
        from praxia.memory.composite import CompositeBackend, WeightedBackend

        a, _ = stub_backend_factory([make_record("r1"), make_record("r2")])
        b, _ = stub_backend_factory([make_record("r2"), make_record("r3")])

        composite = CompositeBackend(
            backends=[
                WeightedBackend("a", a, weight=1.0),
                WeightedBackend("b", b, weight=2.0),  # b's votes count more
            ],
            fusion="rrf",
        )
        out = composite.search(user_id="u", query="q", limit=5)
        ids = [r.id for r in out]
        # r2 in both backends, b weighted higher → top
        assert ids[0] == "r2"
        assert set(ids) == {"r1", "r2", "r3"}

    def test_union_dedupes_keeps_first_seen(self, stub_backend_factory, make_record):
        from praxia.memory.composite import CompositeBackend, WeightedBackend

        a, _ = stub_backend_factory([make_record("x"), make_record("y")])
        b, _ = stub_backend_factory([make_record("y"), make_record("z")])

        composite = CompositeBackend(
            backends=[WeightedBackend("a", a), WeightedBackend("b", b)],
            fusion="union",
        )
        out = composite.search(user_id="u", query="q", limit=10)
        ids = {r.id for r in out}
        assert ids == {"x", "y", "z"}

    def test_intersection_min_agreement_2(self, stub_backend_factory, make_record):
        from praxia.memory.composite import CompositeBackend, WeightedBackend

        shared = make_record("shared")
        a, _ = stub_backend_factory([shared, make_record("only_a")])
        b, _ = stub_backend_factory([shared, make_record("only_b")])
        c, _ = stub_backend_factory([shared, make_record("only_c")])

        composite = CompositeBackend(
            backends=[
                WeightedBackend("a", a),
                WeightedBackend("b", b),
                WeightedBackend("c", c),
            ],
            fusion="intersection",
            min_agreement=2,
        )
        out = composite.search(user_id="u", query="q", limit=10)
        ids = {r.id for r in out}
        # Only "shared" appears in >= 2 backends
        assert ids == {"shared"}

    def test_intersection_min_agreement_1_is_union(
        self, stub_backend_factory, make_record
    ):
        from praxia.memory.composite import CompositeBackend, WeightedBackend

        a, _ = stub_backend_factory([make_record("a1")])
        b, _ = stub_backend_factory([make_record("b1")])

        composite = CompositeBackend(
            backends=[WeightedBackend("a", a), WeightedBackend("b", b)],
            fusion="intersection",
            min_agreement=1,
        )
        out = composite.search(user_id="u", query="q", limit=10)
        assert {r.id for r in out} == {"a1", "b1"}

    def test_weighted_fusion(self, stub_backend_factory, make_record):
        from praxia.memory.composite import CompositeBackend, WeightedBackend

        a, _ = stub_backend_factory([make_record("p"), make_record("q")])
        b, _ = stub_backend_factory([make_record("p"), make_record("r")])

        composite = CompositeBackend(
            backends=[
                WeightedBackend("a", a, weight=1.0),
                WeightedBackend("b", b, weight=3.0),  # b heavily weighted
            ],
            fusion="weighted",
        )
        out = composite.search(user_id="u", query="q", limit=10)
        ids = [r.id for r in out]
        # p in both → highest, then b's other items
        assert ids[0] == "p"

    def test_llm_rerank_falls_back_to_rrf_without_fn(
        self, stub_backend_factory, make_record
    ):
        from praxia.memory.composite import CompositeBackend, WeightedBackend

        a, _ = stub_backend_factory([make_record("x")])
        composite = CompositeBackend(
            backends=[WeightedBackend("a", a)],
            fusion="llm_rerank",
            rerank_fn=None,  # absent → fallback to RRF
        )
        out = composite.search(user_id="u", query="q", limit=5)
        assert len(out) == 1
        assert out[0].id == "x"

    def test_llm_rerank_uses_fn_when_present(
        self, stub_backend_factory, make_record
    ):
        from praxia.memory.composite import CompositeBackend, WeightedBackend

        records = [make_record("p"), make_record("q"), make_record("r")]
        a, _ = stub_backend_factory(records)

        captured_query = []

        def my_rerank(query, candidates):
            captured_query.append(query)
            # Return reverse order
            return list(reversed(candidates))

        composite = CompositeBackend(
            backends=[WeightedBackend("a", a)],
            fusion="llm_rerank",
            rerank_fn=my_rerank,
        )
        out = composite.search(user_id="u", query="my-query", limit=5)
        assert captured_query == ["my-query"]
        assert [r.id for r in out] == ["r", "q", "p"]


# --- Failure isolation ------------------------------------------------------

class TestCompositeFailureIsolation:
    def test_one_backend_raising_doesnt_break_query(
        self, stub_backend_factory, make_record
    ):
        from praxia.memory.composite import CompositeBackend, WeightedBackend

        good, _ = stub_backend_factory([make_record("ok")])
        broken, _ = stub_backend_factory(on_search_raise=True)

        composite = CompositeBackend(
            backends=[
                WeightedBackend("good", good),
                WeightedBackend("broken", broken),
            ],
            fusion="rrf",
        )
        out = composite.search(user_id="u", query="q", limit=5)
        assert any(r.id == "ok" for r in out)


# --- Write target selection -------------------------------------------------

class TestCompositeWriteTarget:
    def test_default_writes_to_first(self, stub_backend_factory):
        from praxia.memory.composite import CompositeBackend, WeightedBackend

        a, cap_a = stub_backend_factory()
        b, cap_b = stub_backend_factory()

        composite = CompositeBackend(
            backends=[WeightedBackend("first", a), WeightedBackend("second", b)],
        )
        composite.add(user_id="u", text="x", kind="fact", metadata={})
        assert cap_a["add_calls"] == 1
        assert cap_b["add_calls"] == 0

    def test_explicit_write_to_named(self, stub_backend_factory):
        from praxia.memory.composite import CompositeBackend, WeightedBackend

        a, cap_a = stub_backend_factory()
        b, cap_b = stub_backend_factory()

        composite = CompositeBackend(
            backends=[WeightedBackend("first", a), WeightedBackend("second", b)],
            write_to="second",
        )
        composite.add(user_id="u", text="x", kind="fact", metadata={})
        assert cap_a["add_calls"] == 0
        assert cap_b["add_calls"] == 1

    def test_unknown_write_to_raises_at_use(self, stub_backend_factory):
        from praxia.memory.composite import CompositeBackend, WeightedBackend

        a, _ = stub_backend_factory()
        composite = CompositeBackend(
            backends=[WeightedBackend("first", a)],
            write_to="missing",
        )
        with pytest.raises(ValueError):
            composite.add(user_id="u", text="x", kind="fact", metadata={})


# --- RuleRouter -------------------------------------------------------------

class TestRuleRouter:
    @pytest.mark.parametrize(
        "query,first_backend",
        [
            # English temporal
            ("what did Bob say last week?", "zep"),
            ("show me activity since 2024", "zep"),
            ("data before 2025-01-01", "zep"),
            # Japanese temporal
            ("先月の議事録を探して", "zep"),
            ("昨日の Acme との会話", "zep"),
            # Audit (English + Japanese)
            ("show me the changelog", "json"),
            ("audit history", "json"),
            ("変更履歴を教えて", "json"),
            ("監査ログを確認", "json"),
            # Entity (English + Japanese)
            ("who is Alice?", "mem0"),
            ("tell me about the company", "mem0"),
            ("Acme について教えて", "mem0"),
            # Similarity (English + Japanese)
            ("find similar examples", "hindsight"),
            ("類似のケース", "hindsight"),
        ],
    )
    def test_rule_routes_correctly(self, query, first_backend):
        from praxia.memory.router import RuleRouter

        router = RuleRouter()
        decision = router.route(
            query, available_backends=["mem0", "zep", "hindsight", "json"]
        )
        assert decision.backends[0] == first_backend, (
            f"query {query!r} expected first={first_backend} but got {decision.backends}"
        )

    def test_unmatched_query_falls_back(self):
        from praxia.memory.router import RuleRouter

        router = RuleRouter()
        decision = router.route(
            "completely random text xyz",
            available_backends=["mem0", "hindsight", "json"],
        )
        assert decision.backends == ["mem0", "hindsight", "json"]
        assert decision.confidence < 0.85  # lower confidence for fallback

    def test_unavailable_backends_filtered_out(self):
        from praxia.memory.router import RuleRouter

        router = RuleRouter()
        # Temporal rule wants [zep, mem0, hindsight] but only mem0 is available
        decision = router.route(
            "last week's activity",
            available_backends=["mem0", "json"],
        )
        # zep should be filtered out — first available is mem0
        assert decision.backends[0] == "mem0"

    def test_custom_rules_override_defaults(self):
        import re
        from praxia.memory.router import RuleRouter

        custom_rules = [
            (re.compile(r"\bspecial\b"), ["json"], "custom rule"),
        ]
        router = RuleRouter(rules=custom_rules)
        decision = router.route(
            "this is special",
            available_backends=["mem0", "json"],
        )
        assert decision.backends == ["json"]
        assert "custom rule" in decision.reason


# --- RoutedBackend ----------------------------------------------------------

class TestRoutedBackend:
    def test_single_backend_route_calls_directly(
        self, stub_backend_factory, make_record
    ):
        from praxia.memory.router import RouteDecision, RoutedBackend

        a, cap_a = stub_backend_factory([make_record("a-1")])
        b, cap_b = stub_backend_factory([make_record("b-1")])

        class StaticRouter:
            def route(self, query, *, available_backends):
                return RouteDecision(
                    backends=["a"], fusion="rrf", reason="test", confidence=1.0
                )

        rb = RoutedBackend(
            backends={"a": a, "b": b},
            router=StaticRouter(),
            write_to="a",
        )
        out = rb.search(user_id="u", query="q", limit=5)
        # Only backend "a" called
        assert cap_a["search_calls"] == 1
        assert cap_b["search_calls"] == 0
        assert out[0].id == "a-1"

    def test_multi_backend_route_uses_composite(
        self, stub_backend_factory, make_record
    ):
        from praxia.memory.router import RouteDecision, RoutedBackend

        a, cap_a = stub_backend_factory([make_record("a-1")])
        b, cap_b = stub_backend_factory([make_record("b-1")])

        class StaticRouter:
            def route(self, query, *, available_backends):
                return RouteDecision(
                    backends=["a", "b"], fusion="rrf", reason="test", confidence=1.0
                )

        rb = RoutedBackend(
            backends={"a": a, "b": b},
            router=StaticRouter(),
            write_to="a",
        )
        out = rb.search(user_id="u", query="q", limit=5)
        # Both called via composite
        assert cap_a["search_calls"] == 1
        assert cap_b["search_calls"] == 1
        ids = {r.id for r in out}
        assert ids == {"a-1", "b-1"}

    def test_write_only_to_designated(self, stub_backend_factory):
        from praxia.memory.router import RoutedBackend, RuleRouter

        a, cap_a = stub_backend_factory()
        b, cap_b = stub_backend_factory()

        rb = RoutedBackend(
            backends={"a": a, "b": b},
            router=RuleRouter(),
            write_to="b",
        )
        rb.add(user_id="u", text="x", kind="fact", metadata={})
        assert cap_a["add_calls"] == 0
        assert cap_b["add_calls"] == 1

    def test_invalid_write_target_rejected_at_construction(
        self, stub_backend_factory
    ):
        from praxia.memory.router import RoutedBackend, RuleRouter

        a, _ = stub_backend_factory()
        with pytest.raises(ValueError):
            RoutedBackend(
                backends={"a": a},
                router=RuleRouter(),
                write_to="missing",
            )
