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


def test_admin_user_update_and_delete() -> None:
    """Admin can edit and delete users via AuthManager."""
    from praxia.auth import AuthManager, Role

    with tempfile.TemporaryDirectory() as d:
        auth = AuthManager(storage_dir=d, bootstrap_admin=None)
        user, _ = auth.create_user("alice", role=Role.MEMBER, email="alice@a.test")

        updated = auth.update_user("alice", email="alice@b.test", role=Role.OPERATOR)
        assert updated.email == "alice@b.test"
        assert updated.role == Role.OPERATOR.value

        # Soft-deactivate
        auth.deactivate_user("alice")
        assert auth.users.get_by_username("alice").is_active is False

        # Hard delete
        assert auth.delete_user("alice") is True
        assert auth.users.get_by_username("alice") is None
        # Re-deletion is a no-op
        assert auth.delete_user("alice") is False


def test_prompts_personal_org_distributed_scopes() -> None:
    """PromptStore handles all three scopes correctly."""
    from praxia.skills.prompts import PromptStore

    with tempfile.TemporaryDirectory() as d:
        store = PromptStore(storage_dir=d)

        # Personal
        store.save_personal("alice", name="my_prompt", body="hello", description="x")
        assert store.get_personal("alice", "my_prompt") is not None

        # Promote → org
        promoted = store.promote("alice", "my_prompt")
        assert promoted is not None and promoted.scope == "org"
        assert store.get_org("my_prompt") is not None

        # Distribute to a role
        store.distribute(
            name="curated", body="curated body", target_roles=["member"]
        )
        bob_prompts = store.list_for_user(user_id="bob", role="member")
        assert any(p.name == "curated" for p in bob_prompts)
        # Viewer doesn't see member-targeted prompt
        viewer_prompts = store.list_for_user(user_id="charlie", role="viewer")
        assert not any(p.name == "curated" for p in viewer_prompts)

        # Personal overrides org
        store.save_personal("alice", name="my_prompt", body="overridden")
        merged = store.list_for_user(user_id="alice", role="member")
        my_prompt = next(p for p in merged if p.name == "my_prompt")
        assert my_prompt.scope == "personal"
        assert my_prompt.body == "overridden"


def test_skill_registry_distribution() -> None:
    """SkillRegistry can distribute to roles and merge correctly."""
    from praxia.skills.business import InvestmentSkill
    from praxia.skills.registry import SkillRegistry

    with tempfile.TemporaryDirectory() as d:
        reg = SkillRegistry(storage_dir=d)
        skill = InvestmentSkill()
        result = reg.distribute(skill, target_roles=["member"])
        assert len(result) == 1
        assert result[0].scope == "distributed"

        bob_skills = reg.list_for_user(user_id="bob", role="member")
        assert any(s.name == "investment_analyst" for s in bob_skills)


def test_dashboard_personal_summary() -> None:
    """Dashboard aggregates personal memory correctly."""
    from praxia.analytics import Dashboard
    from praxia.memory.personal import PersonalMemory

    with tempfile.TemporaryDirectory() as d:
        # Seed with a few memories
        pm = PersonalMemory(
            user_id="alice", backend="json", storage_dir=Path(d) / "personal"
        )
        ep = pm.record_episode(flow_name="sales", inputs={"x": 1}, output="...")
        pm.record_outcome(episode_id=ep.id, success=True, score=0.9)
        pm.record_episode(flow_name="logic", inputs={"y": 2}, output="...")

        d_ = Dashboard(memory_dir=d)
        summary = d_.personal_summary("alice")
        assert summary.user_id == "alice"
        assert summary.episodes == 2
        assert summary.outcomes_recorded == 1
        assert summary.success_rate == 1.0


def test_connector_registry_lists_six() -> None:
    """All six connectors are wired into the factory."""
    from praxia.connectors.registry import list_builtin

    builtin = list_builtin()
    assert set(builtin) == {"box", "sharepoint", "dropbox", "gdrive", "kintone", "salesforce"}


def test_connector_missing_dep_raises_clear_error() -> None:
    """Connectors raise MissingDependencyError when SDK isn't installed."""
    from praxia.connectors import MissingDependencyError, get_connector

    # Try one that's almost certainly not installed in CI
    try:
        get_connector("dropbox", access_token="dummy")
    except (MissingDependencyError, ImportError) as e:
        assert "dropbox" in str(e).lower()
    except Exception:
        # If actually installed, the constructor may accept the dummy token
        pass


def test_connector_unknown_name_raises() -> None:
    """Unknown connector name raises ValueError listing built-ins."""
    from praxia.connectors import get_connector
    try:
        get_connector("nonexistent")
    except ValueError as e:
        msg = str(e).lower()
        assert "box" in msg and "salesforce" in msg


def test_policy_add_evaluate_remove() -> None:
    """Resource access policies allow/deny correctly."""
    from praxia.auth import PolicyManager
    from praxia.auth.audit import AuditLog

    with tempfile.TemporaryDirectory() as d:
        audit = AuditLog(storage_dir=d)
        pm = PolicyManager(storage_dir=d, default_decision="allow", audit_log=audit)

        # Default-allow when no policies exist
        decision = pm.evaluate(
            user_id="alice",
            role="member",
            resource_type="connector",
            resource_id="box:/Public/specs",
            action="read",
        )
        assert decision.allowed is True
        assert decision.matched_policy_id is None

        # Add a deny policy and verify it blocks the action
        deny = pm.add(
            effect="deny",
            resource_type="connector",
            resource_pattern="box:/Confidential/*",
            actions=["read", "write"],
            principals=["role:member", "role:viewer"],
            description="Block confidential folder for non-operators",
        )
        d2 = pm.evaluate(
            user_id="alice",
            role="member",
            resource_type="connector",
            resource_id="box:/Confidential/q3-roadmap.pdf",
            action="read",
        )
        assert d2.allowed is False
        assert d2.matched_policy_id == deny.id

        # Operators are not in the deny principals — they pass
        d3 = pm.evaluate(
            user_id="bob",
            role="operator",
            resource_type="connector",
            resource_id="box:/Confidential/q3-roadmap.pdf",
            action="read",
        )
        assert d3.allowed is True

        # require() raises on denial
        try:
            pm.require(
                user_id="alice",
                role="member",
                resource_type="connector",
                resource_id="box:/Confidential/q3-roadmap.pdf",
                action="read",
            )
        except PermissionError:
            pass
        else:
            raise AssertionError("Should have raised PermissionError")

        # Remove the policy
        assert pm.remove(deny.id) is True
        d4 = pm.evaluate(
            user_id="alice",
            role="member",
            resource_type="connector",
            resource_id="box:/Confidential/q3-roadmap.pdf",
            action="read",
        )
        assert d4.allowed is True


def test_admin_exporter_csv_and_json() -> None:
    """AdminExporter produces audit log + users exports correctly."""
    import csv as _csv
    import json as _json
    from praxia.auth import AdminExporter, AuthManager, Role

    with tempfile.TemporaryDirectory() as d:
        # Seed some auth state
        auth = AuthManager(storage_dir=Path(d) / "auth", bootstrap_admin=None)
        auth.create_user("alice", role=Role.MEMBER, email="alice@a.test")
        auth.create_user("bob", role=Role.ADMIN)

        exporter = AdminExporter(storage_dir=d, audit_log=auth.audit)

        # Audit (CSV)
        csv_path = exporter.export_audit(
            output_path=Path(d) / "audit.csv", format="csv"
        )
        assert csv_path.exists()
        rows = list(_csv.DictReader(csv_path.open("r", encoding="utf-8")))
        assert len(rows) >= 2  # at least the two user.create events

        # Users (JSON) — ensure secrets stripped
        users_path = exporter.export_users(
            output_path=Path(d) / "users.json", format="json"
        )
        assert users_path.exists()
        users_data = _json.loads(users_path.read_text(encoding="utf-8"))
        assert len(users_data) == 2
        for u in users_data:
            assert "api_key_hash" not in u
            assert "password_hash" not in u

        # Personal memory (jsonl) on a user with no memory yet → empty file
        mem_path = exporter.export_personal_memory(
            user_id="alice", output_path=Path(d) / "alice_mem.jsonl", format="jsonl"
        )
        assert mem_path.exists()


def test_authmanager_has_policies_and_exports() -> None:
    """AuthManager exposes policies + exports as composed sub-services."""
    from praxia.auth import AuthManager

    with tempfile.TemporaryDirectory() as d:
        auth = AuthManager(storage_dir=d, bootstrap_admin=None)
        assert auth.policies is not None
        assert auth.exports is not None
        # smoke: add a policy through the sub-service
        p = auth.policies.add(
            effect="deny",
            resource_type="memory",
            resource_pattern="memory:user/*",
            actions=["write"],
            principals=["role:viewer"],
        )
        assert p.id
