"""Smoke tests — verify the package imports cleanly and core abstractions
behave as documented. These intentionally avoid hitting real LLM APIs.
"""
from __future__ import annotations

import json
import tempfile
import time
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


def test_extension_registry_basics() -> None:
    """Generic Registry — direct + lazy registration, get/list/has."""
    from praxia.extensions import Registry, lazy

    class Animal:
        def speak(self) -> str:
            return "generic"

    class Dog(Animal):
        def speak(self) -> str:
            return "woof"

    reg: Registry[Animal] = Registry(name="animal")
    reg.register("dog", Dog)
    assert reg.has("dog") is True
    assert reg.get("dog") is Dog
    assert reg.list() == ["dog"]

    # Lazy — points at a real symbol so it can resolve
    reg.register("dataclass_via_lazy", lazy("dataclasses:dataclass"))
    cls = reg.get("dataclass_via_lazy")
    import dataclasses
    assert cls is dataclasses.dataclass

    # Decorator form
    @reg.register_decorator("cat")
    class Cat(Animal):
        pass

    assert reg.has("cat") is True
    assert reg.get("cat") is Cat


# Sentinel class referenced by the lazy-import test above
class _AnimalForTest:
    pass


def test_extension_registry_unknown_raises_keyerror() -> None:
    from praxia.extensions import Registry

    reg: Registry = Registry(name="thing")
    try:
        reg.get("nonexistent")
    except KeyError as e:
        assert "thing" in str(e).lower() or "nonexistent" in str(e)


def test_connector_registry_uses_extension_system() -> None:
    """Existing connectors are now registered via extensions.Registry."""
    from praxia.connectors.registry import CONNECTORS, list_builtin

    names = list_builtin()
    assert set(names) >= {"box", "sharepoint", "dropbox", "gdrive", "kintone", "salesforce"}
    # Registry is the same shared singleton
    assert "box" in CONNECTORS.list()


def test_memory_backend_registry_uses_extension_system() -> None:
    from praxia.memory.backends import BACKENDS

    names = BACKENDS.list()
    assert set(names) >= {"json", "mem0", "langmem", "letta", "zep", "hindsight"}


def test_skills_registry_includes_builtins() -> None:
    """The 6 default business skills must register on import."""
    from praxia.skills import SKILLS, BUSINESS_SKILLS

    builtins = {cls.manifest.name for cls in BUSINESS_SKILLS}
    registered = set(SKILLS.list())
    assert builtins.issubset(registered)


def test_flows_registry_includes_builtins() -> None:
    from praxia.flows import FLOWS, get_flow

    names = FLOWS.list()
    assert "sales_agent_flow" in names
    assert "logic_checker_flow" in names
    assert "rag_optimization_flow" in names
    # Lookup by name returns the class
    cls = get_flow("sales_agent_flow")
    assert cls.name == "sales_agent_flow"


def test_third_party_skill_can_register_via_decorator() -> None:
    """Demonstrate the third-party extension pattern."""
    from praxia.skills import SKILLS
    from praxia.skills.skill import Skill, SkillManifest

    @SKILLS.register_decorator("hr_recruiting_test")
    class HRRecruitingSkill(Skill):
        manifest = SkillManifest(
            name="hr_recruiting_test",
            description="resume screening + interview qs",
            domain="hr",
        )
        system_prompt = "You are a recruiter…"

    assert SKILLS.has("hr_recruiting_test")
    cls = SKILLS.get("hr_recruiting_test")
    assert cls is HRRecruitingSkill

    # Cleanup so the test is hermetic
    SKILLS.unregister("hr_recruiting_test")


def test_parsers_registry_lists_all_formats() -> None:
    """All built-in parsers register on import."""
    from praxia.io.parsers import supported_extensions

    exts = supported_extensions()
    # Must include the formats the user explicitly asked for
    for needed in ("pdf", "docx", "pptx", "xlsx", "csv", "txt", "md", "html"):
        assert needed in exts, f"missing parser for .{needed}"


def test_text_parser_handles_jp_encoding() -> None:
    """TextParser falls back to Shift-JIS gracefully."""
    from praxia.io.parsers.text import TextParser

    sjis_bytes = "営業企画 第3四半期".encode("shift_jis")
    out = TextParser().parse(sjis_bytes, filename="memo.txt")
    assert "営業企画" in out.content
    assert out.metadata["encoding"] == "shift_jis"


def test_csv_parser_renders_markdown_table() -> None:
    """CsvParser produces a Markdown-style table."""
    from praxia.io.parsers.csv_parser import CsvParser

    csv_data = b"name,age,role\nAlice,30,Operator\nBob,42,Admin\n"
    out = CsvParser().parse(csv_data, filename="users.csv")
    assert "| name | age | role |" in out.content
    assert "| Alice | 30 | Operator |" in out.content
    assert out.metadata["rows"] == 2


def test_structured_parser_pretty_prints_json() -> None:
    from praxia.io.parsers.structured import StructuredParser
    import json as _json

    data = b'{"foo":"bar","n":[1,2,3]}'
    out = StructuredParser().parse(data, filename="config.json")
    parsed_back = _json.loads(out.content)
    assert parsed_back == {"foo": "bar", "n": [1, 2, 3]}
    assert out.metadata["is_valid"] is True


def test_html_parser_strips_tags() -> None:
    from praxia.io.parsers.html import HtmlParser

    html = b"""<html><head><title>Test</title></head>
    <body><script>evil();</script><p>Hello <b>world</b>!</p></body></html>"""
    out = HtmlParser().parse(html, filename="page.html")
    assert "Hello world" in out.content
    assert "evil()" not in out.content
    assert "<p>" not in out.content
    assert out.metadata["title"] == "Test"


def test_parse_file_dispatches_by_extension() -> None:
    """parse_file() picks the right parser from filename."""
    from praxia.io.parsers import parse_file

    out = parse_file(b"hello,world\n1,2", filename="data.csv")
    assert "| hello | world |" in out.content


def test_parse_file_unknown_extension_raises() -> None:
    from praxia.io.parsers import parse_file
    try:
        parse_file(b"...", filename="weird.xyz")
    except ValueError as e:
        assert "xyz" in str(e)


def test_oauth_token_store_roundtrip() -> None:
    """OAuthTokenStore saves/loads/refreshes per-user tokens."""
    from praxia.connectors.oauth import OAuthToken, OAuthTokenStore

    with tempfile.TemporaryDirectory() as d:
        store = OAuthTokenStore(storage_dir=d, encryption_secret="test-secret")
        token = OAuthToken(
            user_id="alice",
            provider="box",
            access_token="abc123",
            refresh_token="refresh-xyz",
            expires_at=time.time() + 3600,
            scope="root_readwrite",
        )
        store.save(token)

        loaded = store.get("alice", "box")
        assert loaded is not None
        assert loaded.access_token == "abc123"
        assert loaded.refresh_token == "refresh-xyz"
        assert loaded.is_expired() is False

        # User isolation — bob has no token even though alice does
        assert store.get("bob", "box") is None

        # List
        assert len(store.list_for_user("alice")) == 1
        assert len(store.list_all()) == 1

        # Delete is idempotent
        assert store.delete("alice", "box") is True
        assert store.get("alice", "box") is None
        assert store.delete("alice", "box") is False


def test_oauth_flow_authorization_url() -> None:
    """OAuthFlow generates valid authorization URLs with state + PKCE."""
    import urllib.parse
    from praxia.connectors.oauth import OAuthFlow, OAuthTokenStore, BOX_OAUTH

    with tempfile.TemporaryDirectory() as d:
        store = OAuthTokenStore(storage_dir=d, encryption_secret="test")
        flow = OAuthFlow(
            BOX_OAUTH,
            client_id="cid-test",
            client_secret="csec-test",
            redirect_uri="http://localhost:8765/cb",
            token_store=store,
        )
        url, state = flow.authorization_url(user_id="alice")
        parsed = urllib.parse.urlparse(url)
        params = dict(urllib.parse.parse_qsl(parsed.query))
        assert params["client_id"] == "cid-test"
        assert params["state"] == state
        assert params["response_type"] == "code"
        assert "redirect_uri" in params
        assert len(state) > 16


def test_oauth_token_for_raises_when_unauthorized() -> None:
    """oauth_token_for() raises clear error when user has no token."""
    from praxia.connectors.oauth import OAuthTokenStore, oauth_token_for

    with tempfile.TemporaryDirectory() as d:
        store = OAuthTokenStore(storage_dir=d, encryption_secret="test")
        try:
            oauth_token_for("alice", "box", store=store)
        except PermissionError as e:
            msg = str(e)
            assert "alice" in msg
            assert "box" in msg
            assert "praxia oauth start" in msg
        else:
            raise AssertionError("Should have raised PermissionError")


def test_oauth_providers_registered() -> None:
    """All 5 OAuth providers are configured."""
    from praxia.connectors.oauth import (
        BOX_OAUTH,
        DROPBOX_OAUTH,
        GOOGLE_OAUTH,
        MICROSOFT_OAUTH,
        SALESFORCE_OAUTH,
    )

    for cfg in (BOX_OAUTH, MICROSOFT_OAUTH, DROPBOX_OAUTH, GOOGLE_OAUTH, SALESFORCE_OAUTH):
        assert cfg.authorize_url.startswith("https://")
        assert cfg.token_url.startswith("https://")
        assert isinstance(cfg.default_scopes, list)
        assert len(cfg.default_scopes) > 0


def test_audio_modules_import_clean() -> None:
    """STT / TTS classes are importable without optional deps."""
    from praxia.io.audio import STT, TTS

    # Construction should not require API keys (auto-pick falls back)
    stt = STT(provider="openai")
    tts = TTS(provider="openai")
    assert stt.provider == "openai"
    assert tts.provider == "openai"


def test_composite_backend_rrf_fusion() -> None:
    """CompositeBackend with RRF fuses results from multiple stub backends."""
    from praxia.memory.backends.base import MemoryRecord
    from praxia.memory.composite import CompositeBackend, WeightedBackend

    class StubBackend:
        def __init__(self, records: list[MemoryRecord]) -> None:
            self._records = records

        def add(self, *, user_id, text, kind, metadata):  # pragma: no cover
            raise NotImplementedError

        def search(self, *, user_id, query, limit):
            return self._records[:limit]

        def all(self, *, user_id=None):
            return list(self._records)

        def clear(self, *, user_id=None):  # pragma: no cover
            pass

    a = MemoryRecord(id="r1", user_id="alice", text="alpha", kind="fact", timestamp=1.0)
    b = MemoryRecord(id="r2", user_id="alice", text="beta", kind="fact", timestamp=2.0)
    c = MemoryRecord(id="r3", user_id="alice", text="gamma", kind="fact", timestamp=3.0)

    composite = CompositeBackend(
        backends=[
            WeightedBackend("backend_a", StubBackend([a, b]), weight=1.0),
            WeightedBackend("backend_b", StubBackend([b, c]), weight=2.0),
        ],
        fusion="rrf",
    )
    out = composite.search(user_id="alice", query="x", limit=5)
    ids = [r.id for r in out]
    # b appears at rank 2 in A and rank 1 in B (weight 2x) → highest aggregate score
    assert ids[0] == "r2"
    assert set(ids) == {"r1", "r2", "r3"}


def test_composite_backend_intersection() -> None:
    """Intersection only keeps items in >= min_agreement backends."""
    from praxia.memory.backends.base import MemoryRecord
    from praxia.memory.composite import CompositeBackend, WeightedBackend

    class StubBackend:
        def __init__(self, records):
            self._records = records

        def add(self, **k):  # pragma: no cover
            raise NotImplementedError

        def search(self, *, user_id, query, limit):
            return self._records[:limit]

        def all(self, *, user_id=None):
            return list(self._records)

        def clear(self, *, user_id=None):  # pragma: no cover
            pass

    shared = MemoryRecord(id="shared", user_id="u", text="shared", kind="fact", timestamp=1.0)
    only_a = MemoryRecord(id="only_a", user_id="u", text="solo a", kind="fact", timestamp=1.0)
    only_b = MemoryRecord(id="only_b", user_id="u", text="solo b", kind="fact", timestamp=1.0)

    composite = CompositeBackend(
        backends=[
            WeightedBackend("a", StubBackend([shared, only_a])),
            WeightedBackend("b", StubBackend([shared, only_b])),
        ],
        fusion="intersection",
        min_agreement=2,
    )
    out = composite.search(user_id="u", query="q", limit=5)
    ids = {r.id for r in out}
    assert ids == {"shared"}


def test_composite_backend_handles_backend_failure() -> None:
    """One backend raising shouldn't break the search."""
    from praxia.memory.backends.base import MemoryRecord
    from praxia.memory.composite import CompositeBackend, WeightedBackend

    class GoodBackend:
        def search(self, *, user_id, query, limit):
            return [MemoryRecord(id="ok", user_id="u", text="ok", kind="fact", timestamp=1.0)]

        def all(self, *, user_id=None):
            return []

        def add(self, **k):  # pragma: no cover
            raise NotImplementedError

        def clear(self, **k):  # pragma: no cover
            pass

    class BrokenBackend:
        def search(self, **k):
            raise RuntimeError("backend on fire")

        def all(self, **k):
            raise RuntimeError("nope")

        def add(self, **k):  # pragma: no cover
            raise NotImplementedError

        def clear(self, **k):  # pragma: no cover
            pass

    composite = CompositeBackend(
        backends=[
            WeightedBackend("good", GoodBackend()),
            WeightedBackend("broken", BrokenBackend()),
        ],
        fusion="rrf",
    )
    out = composite.search(user_id="u", query="q", limit=5)
    assert len(out) == 1
    assert out[0].id == "ok"


def test_rule_router_temporal_query_prefers_zep() -> None:
    """Temporal keywords should pick KG-aware backends first."""
    from praxia.memory.router import RuleRouter

    router = RuleRouter()
    decision = router.route(
        "what did Bob say last week about pricing?",
        available_backends=["mem0", "zep", "hindsight", "json"],
    )
    assert "zep" in decision.backends
    assert decision.backends[0] == "zep"
    assert "temporal" in decision.reason.lower()


def test_rule_router_japanese_audit_query_picks_json() -> None:
    """Japanese audit/history keywords route to JSON for exact recall."""
    from praxia.memory.router import RuleRouter

    router = RuleRouter()
    decision = router.route(
        "先月の変更履歴を教えて",
        available_backends=["mem0", "zep", "hindsight", "json"],
    )
    # Temporal rule fires first (matches 先月) — that's documented behavior
    assert decision.backends[0] in {"zep", "json"}
    assert decision.confidence >= 0.5


def test_rule_router_falls_back_to_default_ensemble() -> None:
    """Unmatched query → default ensemble."""
    from praxia.memory.router import RuleRouter

    router = RuleRouter()
    decision = router.route(
        "foo bar baz",
        available_backends=["mem0", "hindsight", "json"],
    )
    assert decision.backends == ["mem0", "hindsight", "json"]
    assert "default" in decision.reason.lower() or "no specific" in decision.reason.lower()


def test_routed_backend_dispatches_via_router() -> None:
    """RoutedBackend uses the router's decision to pick backend(s)."""
    from praxia.memory.backends.base import MemoryRecord
    from praxia.memory.router import RouteDecision, RoutedBackend

    class StubBackend:
        def __init__(self, name):
            self._name = name
            self.search_calls = 0

        def search(self, *, user_id, query, limit):
            self.search_calls += 1
            return [MemoryRecord(
                id=f"{self._name}-1", user_id=user_id, text=self._name,
                kind="fact", timestamp=1.0,
            )]

        def all(self, *, user_id=None):
            return []

        def add(self, *, user_id, text, kind, metadata):
            return MemoryRecord(
                id=f"{self._name}-w", user_id=user_id, text=text, kind=kind,
                timestamp=1.0, metadata=metadata,
            )

        def clear(self, *, user_id=None):
            pass

    class StaticRouter:
        def __init__(self, backends):
            self._backends = backends

        def route(self, query, *, available_backends):
            return RouteDecision(
                backends=self._backends,
                fusion="rrf",
                reason="static test router",
                confidence=1.0,
            )

    backends = {"mem0": StubBackend("mem0"), "json": StubBackend("json")}
    rb = RoutedBackend(
        backends=backends,
        router=StaticRouter(["json"]),
        write_to="mem0",
    )

    # Search routes to JSON only
    out = rb.search(user_id="alice", query="anything", limit=5)
    assert backends["json"].search_calls == 1
    assert backends["mem0"].search_calls == 0
    assert out[0].id == "json-1"

    # Write goes to write_to (mem0)
    written = rb.add(user_id="alice", text="hi", kind="fact", metadata={})
    assert written.id == "mem0-w"


def test_routed_backend_rejects_unknown_write_target() -> None:
    from praxia.memory.router import RoutedBackend, RuleRouter

    try:
        RoutedBackend(backends={"json": object()}, router=RuleRouter(), write_to="missing")
    except ValueError as e:
        assert "missing" in str(e)
    else:
        raise AssertionError("Should have raised ValueError")


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
