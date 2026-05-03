"""Authentication, authorization, and audit (Phase 5).

Provides:
    - User model with role-based access control (RBAC)
    - API-key + JWT authentication
    - Audit log for every memory read/write and skill invocation
    - OIDC adapter for enterprise SSO (skeleton)

Usage:
    from praxia.auth import AuthManager, Role

    auth = AuthManager(storage_dir=".praxia/auth")
    auth.create_user("alice", role=Role.MEMBER)
    token = auth.issue_token("alice")
    user = auth.authenticate(token)
    if auth.authorize(user, "promote_skills"):
        ...
"""
from praxia.auth.audit import AuditLog, AuditEvent
from praxia.auth.manager import AuthManager
from praxia.auth.rbac import PERMISSIONS_BY_ROLE, Role
from praxia.auth.users import User

__all__ = [
    "AuthManager",
    "AuditLog",
    "AuditEvent",
    "Role",
    "User",
    "PERMISSIONS_BY_ROLE",
]
