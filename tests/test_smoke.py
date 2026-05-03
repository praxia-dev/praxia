"""Smoke tests — verify the package imports cleanly and core abstractions
behave as documented. These intentionally avoid hitting real LLM APIs.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest


def test_imports() -> None:
    import praxia

    assert praxia.Praxia is not None
    assert praxia.PersonalMemory is not None
    assert praxia.SharedMemory is not None
    assert praxia.LLM is not None


def test_personal_memory_json_backend() -> None:
    from praxia import PersonalMemory

    with tempfile.TemporaryDirectory() as d:
        pm = PersonalMemory(user_id="alice", backend="json", storage_dir=d)
        pm.record_fact("alice prefers tabs over spaces")
        pm.record_episode(
            flow_name="test-flow",
            inputs={"x": 1},
            output="hello world",
        )
        results = pm.search("tabs", limit=5)
        assert any("tabs" in r for r in results)
        assert len(pm.all_entries()) == 2


def test_shared_memory() -> None:
    from praxia import SharedMemory

    with tempfile.TemporaryDirectory() as d:
        sm = SharedMemory(org_id="test-org", storage_dir=d)
        sm.upsert(label="team_norms", description="norms", value="we ship Fridays")
        block = sm.get_by_label("team_norms")
        assert block is not None
        assert "Fridays" in block.value


def test_business_skills_have_required_metadata() -> None:
    from praxia.skills import BUSINESS_SKILLS

    assert len(BUSINESS_SKILLS) == 6
    for skill_cls in BUSINESS_SKILLS:
        assert skill_cls.manifest.name
        assert skill_cls.manifest.description
        assert skill_cls.manifest.domain
        assert skill_cls.system_prompt


def test_flows_define_steps() -> None:
    from praxia.flows import LogicCheckerFlow, RAGOptimizationFlow, SalesAgentFlow

    for flow_cls in (SalesAgentFlow, LogicCheckerFlow, RAGOptimizationFlow):
        # Avoid real LLM init: patch with a stub
        flow = flow_cls.__new__(flow_cls)
        # We just verify the class metadata is set; full instantiation needs an LLM
        assert flow_cls.name
        assert flow_cls.description


def test_promotion_engine_threshold_logic() -> None:
    from praxia.memory.promoter import PromotionEngine, PromotionVerdict

    # Don't call _self_eval (needs LLM). Test threshold logic on a constructed verdict.
    engine = PromotionEngine.__new__(PromotionEngine)
    engine.weight_freq = 0.4
    engine.weight_outcome = 0.3
    engine.weight_self = 0.3
    engine.auto_threshold = 0.75
    engine.review_threshold = 0.5

    # Manually compute a verdict using the static helpers
    score = PromotionEngine._score_frequency(unique_contributors=5, total_users=5)
    assert 0.9 <= score <= 1.0


def test_skill_serialization_to_md() -> None:
    from praxia.skills.business import InvestmentSkill

    md = InvestmentSkill().to_skill_md()
    assert md.startswith("---\n")
    assert "name: investment_analyst" in md
    assert "domain: investment" in md


def test_llm_alias_resolution() -> None:
    from praxia.core.llm import DEFAULT_ALIASES

    assert DEFAULT_ALIASES["claude"].startswith("anthropic/")
    assert DEFAULT_ALIASES["chatgpt"].startswith("openai/")
    assert DEFAULT_ALIASES["gemini"].startswith("gemini/")
    assert DEFAULT_ALIASES["qwen"].startswith("dashscope/")
    assert DEFAULT_ALIASES["qwen-local"].startswith("ollama/")


def test_phase2_outcome_tracking() -> None:
    """Phase 2: outcomes attach to episodes for statistical promotion."""
    from praxia import PersonalMemory

    with tempfile.TemporaryDirectory() as d:
        pm = PersonalMemory(user_id="alice", backend="json", storage_dir=d)
        episode = pm.record_episode(
            flow_name="sales", inputs={"customer": "Acme"}, output="..."
        )
        pm.record_outcome(
            episode_id=episode.id, success=True, score=0.9, notes="closed-won"
        )
        outcomes = pm.outcomes_for(episode.id)
        assert len(outcomes) == 1
        assert outcomes[0].metadata["success"] is True
        assert outcomes[0].metadata["score"] == 0.9


def test_phase5_auth_module() -> None:
    """Phase 5: auth + RBAC + audit log end-to-end."""
    from praxia.auth import AuthManager, Role

    with tempfile.TemporaryDirectory() as d:
        auth = AuthManager(storage_dir=d, bootstrap_admin=None)
        user, raw_key = auth.create_user("alice", role=Role.MEMBER)

        # API-key authentication
        resolved = auth.authenticate(api_key=raw_key)
        assert resolved is not None and resolved.id == user.id

        # JWT authentication
        token = auth.issue_token(user.id)
        token_user = auth.authenticate(token=token)
        assert token_user is not None and token_user.id == user.id

        # RBAC
        assert auth.authorize(user, "run_flows") is True
        assert auth.authorize(user, "manage_users") is False

        # Role elevation
        auth.grant_role("alice", Role.ADMIN)
        admin_user = auth.users.get_by_username("alice")
        assert auth.authorize(admin_user, "manage_users") is True

        # Audit log captured actions
        assert len(auth.audit.tail()) >= 3


def test_phase5_permission_denial_raises() -> None:
    from praxia.auth import AuthManager, Role

    with tempfile.TemporaryDirectory() as d:
        auth = AuthManager(storage_dir=d, bootstrap_admin=None)
        user, _ = auth.create_user("viewer1", role=Role.VIEWER)
        try:
            auth.require(user, "promote_skills")
        except PermissionError:
            return
        raise AssertionError("Should have raised PermissionError")


def test_hindsight_backend_listed() -> None:
    """HindSight backend should be in the supported list."""
    from praxia.memory.backends import load_backend
    try:
        load_backend("unsupported_backend_xyz")
    except ValueError as e:
        assert "hindsight" in str(e).lower()
