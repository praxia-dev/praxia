"""Memory backends + mode + admin policy — regression scenarios.

Coverage:
    - JsonBackend: add / search / all / clear / namespace isolation
    - read_only mode: every record_* method drops writes
    - mode persistence + retrieval
    - MemoryAdminPolicy: load / save / round-trip
    - MemoryUserPreference: load / save / round-trip
    - resolve_memory_config: full precedence matrix
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.evaluation


class TestJsonBackend:
    def test_add_and_search(self, tmp_storage):
        from praxia import PersonalMemory

        pm = PersonalMemory(user_id="alice", backend="json", storage_dir=tmp_storage)
        pm.record_fact("alice prefers tabs over spaces")
        pm.record_fact("she uses dark mode")
        results = pm.search("tabs", limit=5)
        assert any("tabs" in r for r in results)

    def test_user_namespace_isolation(self, tmp_storage):
        from praxia import PersonalMemory

        pm_a = PersonalMemory(user_id="alice", backend="json", storage_dir=tmp_storage)
        pm_b = PersonalMemory(user_id="bob", backend="json", storage_dir=tmp_storage)

        pm_a.record_fact("alice secret")
        pm_b.record_fact("bob secret")

        assert any("alice" in e.text for e in pm_a.all_entries())
        assert not any("bob" in e.text for e in pm_a.all_entries())

        assert any("bob" in e.text for e in pm_b.all_entries())
        assert not any("alice" in e.text for e in pm_b.all_entries())

    def test_clear_removes_only_owner(self, tmp_storage):
        from praxia import PersonalMemory

        pm_a = PersonalMemory(user_id="alice", backend="json", storage_dir=tmp_storage)
        pm_b = PersonalMemory(user_id="bob", backend="json", storage_dir=tmp_storage)

        pm_a.record_fact("a-1")
        pm_b.record_fact("b-1")

        pm_a.clear()
        assert pm_a.all_entries() == []
        assert len(pm_b.all_entries()) == 1


class TestReadOnlyMode:
    @pytest.mark.parametrize(
        "method,kwargs",
        [
            ("record_fact", {"text": "x"}),
            ("record_preference", {"text": "y"}),
            ("record_episode", {"flow_name": "f", "inputs": {}, "output": "o"}),
        ],
    )
    def test_record_methods_dropped(self, tmp_storage, method, kwargs):
        from praxia import PersonalMemory

        pm = PersonalMemory(
            user_id="alice", backend="json", storage_dir=tmp_storage, mode="read_only"
        )
        result = getattr(pm, method)(**kwargs)
        assert result.metadata.get("read_only_dropped") is True
        assert pm.all_entries() == []

    def test_record_outcome_dropped(self, tmp_storage):
        from praxia import PersonalMemory

        pm = PersonalMemory(
            user_id="alice", backend="json", storage_dir=tmp_storage, mode="read_only"
        )
        result = pm.record_outcome(
            episode_id="ep-1", success=True, score=0.9, notes="closed"
        )
        assert result.metadata.get("read_only_dropped") is True
        assert pm.all_entries() == []

    def test_search_works_in_read_only(self, tmp_storage):
        from praxia import PersonalMemory

        # First, record in accumulate mode
        pm1 = PersonalMemory(
            user_id="alice", backend="json", storage_dir=tmp_storage, mode="accumulate"
        )
        pm1.record_fact("alice prefers tabs")

        # Reopen in read_only — search should still find the fact
        pm2 = PersonalMemory(
            user_id="alice", backend="json", storage_dir=tmp_storage, mode="read_only"
        )
        results = pm2.search("tabs", limit=5)
        assert any("tabs" in r for r in results)

    def test_set_mode_toggles_behavior(self, tmp_storage):
        from praxia import PersonalMemory

        pm = PersonalMemory(
            user_id="alice", backend="json", storage_dir=tmp_storage, mode="accumulate"
        )
        pm.record_fact("first")
        assert len(pm.all_entries()) == 1

        pm.set_mode("read_only")
        pm.record_fact("dropped")
        assert len(pm.all_entries()) == 1  # not 2

        pm.set_mode("accumulate")
        pm.record_fact("kept")
        assert len(pm.all_entries()) == 2

    def test_invalid_mode_raises(self, tmp_storage):
        from praxia import PersonalMemory

        pm = PersonalMemory(user_id="x", backend="json", storage_dir=tmp_storage)
        with pytest.raises(ValueError):
            pm.set_mode("strange_mode")


class TestAdminPolicy:
    def test_save_load_round_trip(self, tmp_storage):
        from praxia.memory.policy import MemoryAdminPolicy

        original = MemoryAdminPolicy(
            enforced_backend="mem0",
            default_backend="json",
            allowed_backends=["mem0", "zep", "json"],
            default_mode="read_only",
            mode_locked=True,
            accumulate_locked_to=["operator"],
        )
        original.save(tmp_storage)

        loaded = MemoryAdminPolicy.load(tmp_storage)
        assert loaded.enforced_backend == "mem0"
        assert loaded.default_backend == "json"
        assert loaded.allowed_backends == ["mem0", "zep", "json"]
        assert loaded.default_mode == "read_only"
        assert loaded.mode_locked is True
        assert loaded.accumulate_locked_to == ["operator"]

    def test_load_missing_returns_defaults(self, tmp_storage):
        from praxia.memory.policy import MemoryAdminPolicy

        loaded = MemoryAdminPolicy.load(tmp_storage / "nonexistent")
        assert loaded.enforced_backend is None
        assert loaded.default_backend == "json"
        assert loaded.default_mode == "accumulate"
        assert loaded.mode_locked is False

    @pytest.mark.parametrize(
        "policy_kwargs,backend,expected",
        [
            # Empty allowed list = any allowed
            ({"allowed_backends": []}, "anything", True),
            # Whitelist
            ({"allowed_backends": ["json", "mem0"]}, "mem0", True),
            ({"allowed_backends": ["json", "mem0"]}, "zep", False),
            # Enforced takes precedence over allowed
            (
                {"enforced_backend": "mem0", "allowed_backends": ["json", "mem0", "zep"]},
                "json",
                False,
            ),
            (
                {"enforced_backend": "mem0", "allowed_backends": ["json", "mem0", "zep"]},
                "mem0",
                True,
            ),
        ],
    )
    def test_is_backend_allowed(self, policy_kwargs, backend, expected):
        from praxia.memory.policy import MemoryAdminPolicy

        p = MemoryAdminPolicy(**policy_kwargs)
        assert p.is_backend_allowed(backend) is expected


class TestUserPreference:
    def test_save_load(self, tmp_storage):
        from praxia.memory.policy import MemoryUserPreference

        pref = MemoryUserPreference(user_id="alice", backend="zep", mode="read_only")
        pref.save(tmp_storage)

        loaded = MemoryUserPreference.load(tmp_storage, "alice")
        assert loaded.user_id == "alice"
        assert loaded.backend == "zep"
        assert loaded.mode == "read_only"

    def test_load_missing_returns_empty(self, tmp_storage):
        from praxia.memory.policy import MemoryUserPreference

        loaded = MemoryUserPreference.load(tmp_storage, "missing_user")
        assert loaded.user_id == "missing_user"
        assert loaded.backend is None
        assert loaded.mode is None


class TestResolveMemoryConfig:
    def test_default_when_nothing_set(self, tmp_storage):
        from praxia.memory.policy import resolve_memory_config

        cfg = resolve_memory_config(user_id="alice", storage_dir=tmp_storage)
        assert cfg.backend == "json"
        assert cfg.mode == "accumulate"
        assert cfg.locked_by_admin is False

    def test_admin_enforced_overrides_user_pref(self, tmp_storage):
        from praxia.memory.policy import (
            MemoryAdminPolicy,
            MemoryUserPreference,
            resolve_memory_config,
        )

        MemoryAdminPolicy(enforced_backend="mem0").save(tmp_storage)
        MemoryUserPreference(user_id="alice", backend="zep").save(tmp_storage)

        cfg = resolve_memory_config(user_id="alice", storage_dir=tmp_storage)
        assert cfg.backend == "mem0"
        assert "admin enforced" in cfg.reason

    def test_admin_mode_lock_wins(self, tmp_storage):
        from praxia.memory.policy import (
            MemoryAdminPolicy,
            MemoryUserPreference,
            resolve_memory_config,
        )

        MemoryAdminPolicy(default_mode="read_only", mode_locked=True).save(tmp_storage)
        MemoryUserPreference(user_id="alice", mode="accumulate").save(tmp_storage)

        cfg = resolve_memory_config(user_id="alice", storage_dir=tmp_storage)
        assert cfg.mode == "read_only"
        assert cfg.locked_by_admin is True

    def test_role_lock_forces_accumulate(self, tmp_storage):
        from praxia.memory.policy import (
            MemoryAdminPolicy,
            MemoryUserPreference,
            resolve_memory_config,
        )

        MemoryAdminPolicy(
            default_mode="read_only",  # default would be read_only...
            accumulate_locked_to=["operator"],  # ...but operator gets accumulate forced
        ).save(tmp_storage)
        MemoryUserPreference(user_id="op_alice", mode="read_only").save(tmp_storage)

        cfg = resolve_memory_config(
            user_id="op_alice", storage_dir=tmp_storage, user_role="operator"
        )
        assert cfg.mode == "accumulate"
        assert cfg.locked_by_admin is True

    def test_user_pref_used_when_no_admin_lock(self, tmp_storage):
        from praxia.memory.policy import MemoryUserPreference, resolve_memory_config

        MemoryUserPreference(user_id="alice", backend="hindsight", mode="read_only").save(tmp_storage)

        cfg = resolve_memory_config(user_id="alice", storage_dir=tmp_storage)
        assert cfg.backend == "hindsight"
        assert cfg.mode == "read_only"
        assert cfg.locked_by_admin is False

    def test_call_site_arg_beats_user_pref(self, tmp_storage):
        from praxia.memory.policy import MemoryUserPreference, resolve_memory_config

        MemoryUserPreference(user_id="alice", backend="json", mode="accumulate").save(tmp_storage)

        cfg = resolve_memory_config(
            user_id="alice", storage_dir=tmp_storage,
            requested_backend="hindsight", requested_mode="read_only",
        )
        # Note: requested_backend respected only if admin allows it
        assert cfg.backend == "hindsight"
        assert cfg.mode == "read_only"

    def test_admin_disallowed_backend_falls_through_to_default(self, tmp_storage):
        from praxia.memory.policy import (
            MemoryAdminPolicy,
            MemoryUserPreference,
            resolve_memory_config,
        )

        MemoryAdminPolicy(
            allowed_backends=["json", "mem0"],
            default_backend="mem0",
        ).save(tmp_storage)
        MemoryUserPreference(user_id="alice", backend="zep").save(tmp_storage)  # not allowed

        cfg = resolve_memory_config(user_id="alice", storage_dir=tmp_storage)
        assert cfg.backend == "mem0"  # falls back to admin default
