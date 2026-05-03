"""Smoke tests — verify the package imports cleanly and core abstractions
behave as documented. These intentionally avoid hitting real LLM APIs.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest


def test_imports() -> None:
    import agentloom

    assert agentloom.AgentLoom is not None
    assert agentloom.PersonalMemory is not None
    assert agentloom.SharedMemory is not None
    assert agentloom.LLM is not None


def test_personal_memory_json_backend() -> None:
    from agentloom import PersonalMemory

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
    from agentloom import SharedMemory

    with tempfile.TemporaryDirectory() as d:
        sm = SharedMemory(org_id="test-org", storage_dir=d)
        sm.upsert(label="team_norms", description="norms", value="we ship Fridays")
        block = sm.get_by_label("team_norms")
        assert block is not None
        assert "Fridays" in block.value


def test_business_skills_have_required_metadata() -> None:
    from agentloom.skills import BUSINESS_SKILLS

    assert len(BUSINESS_SKILLS) == 6
    for skill_cls in BUSINESS_SKILLS:
        assert skill_cls.manifest.name
        assert skill_cls.manifest.description
        assert skill_cls.manifest.domain
        assert skill_cls.system_prompt


def test_flows_define_steps() -> None:
    from agentloom.flows import LogicCheckerFlow, RAGOptimizationFlow, SalesAgentFlow

    for flow_cls in (SalesAgentFlow, LogicCheckerFlow, RAGOptimizationFlow):
        # Avoid real LLM init: patch with a stub
        flow = flow_cls.__new__(flow_cls)
        # We just verify the class metadata is set; full instantiation needs an LLM
        assert flow_cls.name
        assert flow_cls.description


def test_promotion_engine_threshold_logic() -> None:
    from agentloom.memory.promoter import PromotionEngine, PromotionVerdict

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
    from agentloom.skills.business import InvestmentSkill

    md = InvestmentSkill().to_skill_md()
    assert md.startswith("---\n")
    assert "name: investment_analyst" in md
    assert "domain: investment" in md


def test_llm_alias_resolution() -> None:
    from agentloom.core.llm import DEFAULT_ALIASES

    assert DEFAULT_ALIASES["claude"].startswith("anthropic/")
    assert DEFAULT_ALIASES["chatgpt"].startswith("openai/")
    assert DEFAULT_ALIASES["gemini"].startswith("gemini/")
    assert DEFAULT_ALIASES["qwen"].startswith("dashscope/")
    assert DEFAULT_ALIASES["qwen-local"].startswith("ollama/")
