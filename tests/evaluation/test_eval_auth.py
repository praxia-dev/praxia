"""Authentication / RBAC / ACL — regression scenarios.

Coverage:
    - API-key auth (success / wrong-key / deactivated user)
    - JWT auth (valid / expired / unsigned / wrong subject)
    - Role grant + role-based action allowance
    - PolicyManager: deny precedence, glob patterns, principal filters
    - Audit log: every privileged action records, user/admin export hides secrets
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.evaluation


# --- API key authentication --------------------------------------------------

class TestApiKeyAuth:
    def test_create_user_returns_one_time_key(self, tmp_storage):
        from praxia.auth import AuthManager, Role

        auth = AuthManager(storage_dir=tmp_storage, bootstrap_admin=None)
        user, raw_key = auth.create_user("alice", role=Role.MEMBER)

        assert raw_key.startswith("praxia_") or len(raw_key) >= 32
        # The hash is stored, not the raw key
        stored = auth.users.get_by_username("alice")
        assert stored.api_key_hash != raw_key
        assert stored.api_key_hash  # not empty

    def test_authenticate_correct_key_succeeds(self, tmp_storage):
        from praxia.auth import AuthManager, Role

        auth = AuthManager(storage_dir=tmp_storage, bootstrap_admin=None)
        user, key = auth.create_user("alice", role=Role.MEMBER)

        resolved = auth.authenticate(api_key=key)
        assert resolved is not None
        assert resolved.id == user.id
        assert resolved.username == "alice"

    def test_authenticate_wrong_key_returns_none(self, tmp_storage):
        from praxia.auth import AuthManager, Role

        auth = AuthManager(storage_dir=tmp_storage, bootstrap_admin=None)
        auth.create_user("alice", role=Role.MEMBER)
        assert auth.authenticate(api_key="praxia_wrong_key") is None

    def test_authenticate_deactivated_user_returns_none(self, tmp_storage):
        from praxia.auth import AuthManager, Role

        auth = AuthManager(storage_dir=tmp_storage, bootstrap_admin=None)
        user, key = auth.create_user("alice", role=Role.MEMBER)
        auth.deactivate_user("alice")
        assert auth.authenticate(api_key=key) is None

    def test_rotate_key_invalidates_old_returns_new(self, tmp_storage):
        from praxia.auth import AuthManager, Role

        auth = AuthManager(storage_dir=tmp_storage, bootstrap_admin=None)
        user, old_key = auth.create_user("alice", role=Role.MEMBER)
        new_key = auth.users.rotate_api_key(user.id)
        assert new_key != old_key
        assert auth.authenticate(api_key=old_key) is None
        assert auth.authenticate(api_key=new_key) is not None


# --- JWT authentication -----------------------------------------------------

class TestJwtAuth:
    def test_issued_token_resolves_to_user(self, tmp_storage):
        from praxia.auth import AuthManager, Role

        auth = AuthManager(storage_dir=tmp_storage, bootstrap_admin=None)
        user, _ = auth.create_user("alice", role=Role.MEMBER)
        token = auth.issue_token(user.id)
        resolved = auth.authenticate(token=token)
        assert resolved is not None
        assert resolved.id == user.id

    def test_tampered_token_rejected(self, tmp_storage):
        from praxia.auth import AuthManager, Role

        auth = AuthManager(storage_dir=tmp_storage, bootstrap_admin=None)
        user, _ = auth.create_user("alice", role=Role.MEMBER)
        token = auth.issue_token(user.id)
        # Flip the last char (which lives in the signature segment) to corrupt it
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
        assert auth.authenticate(token=tampered) is None


# --- RBAC -------------------------------------------------------------------

class TestRBAC:
    @pytest.mark.parametrize(
        "role,action,expected",
        [
            ("admin", "manage_users", True),
            ("operator", "manage_users", False),
            ("member", "run_flows", True),
            ("member", "manage_users", False),
            ("member", "promote_skills", False),
            ("viewer", "run_flows", False),  # viewer is read-only
            ("viewer", "promote_skills", False),
            ("viewer", "read_shared_memory", True),
            ("admin", "promote_skills", True),
            ("operator", "freeze_blocks", True),
            ("member", "freeze_blocks", False),
        ],
    )
    def test_role_action_matrix(self, tmp_storage, role, action, expected):
        from praxia.auth import AuthManager, Role

        auth = AuthManager(storage_dir=tmp_storage, bootstrap_admin=None)
        user, _ = auth.create_user(f"u_{role}", role=Role(role))
        assert auth.authorize(user, action) is expected

    def test_require_raises_on_deny(self, tmp_storage):
        from praxia.auth import AuthManager, Role

        auth = AuthManager(storage_dir=tmp_storage, bootstrap_admin=None)
        user, _ = auth.create_user("viewer1", role=Role.VIEWER)
        with pytest.raises(PermissionError):
            auth.require(user, "manage_users")

    def test_role_grant_changes_authorization(self, tmp_storage):
        from praxia.auth import AuthManager, Role

        auth = AuthManager(storage_dir=tmp_storage, bootstrap_admin=None)
        user, _ = auth.create_user("alice", role=Role.MEMBER)
        assert auth.authorize(user, "manage_users") is False

        auth.grant_role("alice", Role.ADMIN)
        admin = auth.users.get_by_username("alice")
        assert auth.authorize(admin, "manage_users") is True


# --- ACL (PolicyManager) ----------------------------------------------------

class TestACL:
    def test_default_allow_when_no_policies(self, tmp_storage):
        from praxia.auth import PolicyManager
        from praxia.auth.audit import AuditLog

        audit = AuditLog(storage_dir=tmp_storage)
        pm = PolicyManager(storage_dir=tmp_storage, default_decision="allow", audit_log=audit)
        d = pm.evaluate(
            user_id="alice", role="member",
            resource_type="connector", resource_id="box:0/foo", action="read",
        )  # type: ignore[call-arg]
        assert d.allowed is True

    def test_deny_specific_first_then_allow_general(self, tmp_storage):
        """First-match-wins — place specific deny first."""
        from praxia.auth import PolicyManager
        from praxia.auth.audit import AuditLog

        audit = AuditLog(storage_dir=tmp_storage)
        pm = PolicyManager(storage_dir=tmp_storage, default_decision="allow", audit_log=audit)

        # Add specific deny FIRST (specific patterns must precede general ones)
        deny = pm.add(
            effect="deny", resource_type="connector",
            resource_pattern="box:/Public/secret*", actions=["read"],
            principals=["role:member"],
        )
        pm.add(
            effect="allow", resource_type="connector",
            resource_pattern="box:/Public/*", actions=["read"],
            principals=["role:member"],
        )
        d = pm.evaluate(
            user_id="alice", role="member",
            resource_type="connector", resource_id="box:/Public/secret-q3.pdf",
            action="read",
        )
        assert d.allowed is False
        assert d.matched_policy_id == deny.id

    def test_glob_pattern_match(self, tmp_storage):
        from praxia.auth import PolicyManager
        from praxia.auth.audit import AuditLog

        audit = AuditLog(storage_dir=tmp_storage)
        pm = PolicyManager(storage_dir=tmp_storage, default_decision="allow", audit_log=audit)

        pm.add(
            effect="deny", resource_type="connector",
            resource_pattern="box:/Confidential/*", actions=["read", "write"],
            principals=["role:member"],
        )

        # Inside Confidential — denied
        assert pm.evaluate(
            user_id="alice", role="member",
            resource_type="connector",
            resource_id="box:/Confidential/anything.pdf",
            action="read",
        ).allowed is False

        # Outside Confidential — allowed (default)
        assert pm.evaluate(
            user_id="alice", role="member",
            resource_type="connector",
            resource_id="box:/Public/file.pdf",
            action="read",
        ).allowed is True

    def test_principal_filter_user_specific(self, tmp_storage):
        from praxia.auth import PolicyManager
        from praxia.auth.audit import AuditLog

        audit = AuditLog(storage_dir=tmp_storage)
        pm = PolicyManager(storage_dir=tmp_storage, default_decision="allow", audit_log=audit)

        # PolicyManager checks principals against {user_id, "role:<role>", "*"}
        # so user-specific entries use the bare user_id.
        pm.add(
            effect="deny", resource_type="connector",
            resource_pattern="box:*", actions=["write"],
            principals=["alice"],  # bare user_id
        )

        # alice — denied
        assert pm.evaluate(
            user_id="alice", role="member",
            resource_type="connector", resource_id="box:0", action="write",
        ).allowed is False

        # bob — allowed (different user, no match)
        assert pm.evaluate(
            user_id="bob", role="member",
            resource_type="connector", resource_id="box:0", action="write",
        ).allowed is True

    def test_action_filter(self, tmp_storage):
        from praxia.auth import PolicyManager
        from praxia.auth.audit import AuditLog

        audit = AuditLog(storage_dir=tmp_storage)
        pm = PolicyManager(storage_dir=tmp_storage, default_decision="allow", audit_log=audit)

        pm.add(
            effect="deny", resource_type="connector",
            resource_pattern="*", actions=["write"],  # write only
            principals=["role:viewer"],
        )

        # read — allowed (action not in deny list)
        assert pm.evaluate(
            user_id="v", role="viewer",
            resource_type="connector", resource_id="box:0", action="read",
        ).allowed is True

        # write — denied
        assert pm.evaluate(
            user_id="v", role="viewer",
            resource_type="connector", resource_id="box:0", action="write",
        ).allowed is False


# --- Audit log --------------------------------------------------------------

class TestAuditLog:
    def test_user_create_records_entry(self, tmp_storage):
        from praxia.auth import AuthManager, Role

        auth = AuthManager(storage_dir=tmp_storage, bootstrap_admin=None)
        before = len(auth.audit.tail())
        auth.create_user("alice", role=Role.MEMBER)
        after = auth.audit.tail()
        assert len(after) == before + 1
        assert any(e.action == "user.create" for e in after)

    def test_audit_export_strips_secrets(self, tmp_storage):
        import json as _json
        from praxia.auth import AdminExporter, AuthManager, Role

        auth = AuthManager(storage_dir=tmp_storage / "auth", bootstrap_admin=None)
        auth.create_user("alice", role=Role.MEMBER)
        auth.create_user("bob", role=Role.OPERATOR)

        exporter = AdminExporter(storage_dir=tmp_storage, audit_log=auth.audit)
        out = exporter.export_users(
            output_path=tmp_storage / "users.json", format="json"
        )

        data = _json.loads(out.read_text(encoding="utf-8"))
        for record in data:
            assert "api_key_hash" not in record
            assert "password_hash" not in record

    def test_audit_log_is_append_only(self, tmp_storage):
        """Writing N events should result in N records — never fewer."""
        from praxia.auth.audit import AuditLog

        log = AuditLog(storage_dir=tmp_storage)
        for i in range(20):
            log.record(
                actor_id="x", actor_role="admin",
                action=f"test.event_{i}", resource="test:res",
                outcome="success",
            )
        events = log.tail(limit=100)
        assert len(events) == 20
        # Events stay in insertion order
        for i, ev in enumerate(events[-20:]):
            assert ev.action == f"test.event_{i}"
