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
from praxia.auth.sso import (
    OIDCProvider,
    SAMLConfig,
    SAMLProvider,
    SSOConfig,
    SSOProvider,
    SSOUserInfo,
    github_provider,
    google_provider,
    keycloak_provider,
    microsoft_provider,
    okta_provider,
    provider_from_env,
)
from praxia.auth.users import User

__all__ = [
    "AuthManager",
    "AuditLog",
    "AuditEvent",
    "Role",
    "User",
    "PERMISSIONS_BY_ROLE",
    # SSO
    "SSOConfig",
    "SSOProvider",
    "SSOUserInfo",
    "OIDCProvider",
    "SAMLConfig",
    "SAMLProvider",
    "google_provider",
    "microsoft_provider",
    "okta_provider",
    "github_provider",
    "keycloak_provider",
    "provider_from_env",
]
