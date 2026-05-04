"""High-level AuthManager — facade over UserStore + RBAC + AuditLog.

Most callers should only ever interact with this class.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from praxia.auth.audit import AuditLog
from praxia.auth.rbac import Role, has_permission
from praxia.auth.sso import SSOProvider, SSOUserInfo
from praxia.auth.users import User, UserStore


class AuthManager:
    """One-stop shop for authentication, authorization, and auditing.

    Args:
        storage_dir: where users / api_keys / audit log are stored
        jwt_secret:  secret for signing session tokens. If None, falls back
                     to the env var `PRAXIA_JWT_SECRET`. SSO setups can
                     bypass JWT entirely.
        bootstrap_admin: when no users exist, create this admin on first use
                         so initial setup just works.
    """

    def __init__(
        self,
        *,
        storage_dir: Path | str = ".praxia/auth",
        jwt_secret: str | None = None,
        bootstrap_admin: str | None = "admin",
    ) -> None:
        self.users = UserStore(storage_dir)
        self.audit = AuditLog(storage_dir)
        self._jwt_secret = jwt_secret or os.getenv("PRAXIA_JWT_SECRET", "praxia-dev-only")
        self._sso_providers: dict[str, SSOProvider] = {}

        if bootstrap_admin and not self.users.list_all():
            user, raw_key = self.users.create(
                username=bootstrap_admin, role=Role.ADMIN.value
            )
            self._save_bootstrap_key(raw_key)

    # --- Authentication ----------------------------------------------------

    def authenticate(self, *, api_key: str | None = None, token: str | None = None) -> User | None:
        """Resolve a User from either an API key or a JWT.

        Returns None on failure (caller should treat as anonymous).
        """
        if api_key:
            user = self.users.get_by_api_key(api_key)
            if user:
                self.audit.record(
                    actor_id=user.id,
                    actor_role=user.role,
                    action="auth.api_key",
                    resource=f"user:{user.username}",
                )
            else:
                self.audit.record(
                    actor_id="unknown",
                    actor_role="anonymous",
                    action="auth.api_key",
                    resource="unknown",
                    outcome="denied",
                )
            return user

        if token:
            user_id = self._verify_jwt(token)
            if user_id:
                return self.users.get_by_id(user_id)
        return None

    def issue_token(self, user_id: str, *, ttl_seconds: int = 3600) -> str:
        """Issue a stateless JWT-style token. (HS256 minimal implementation.)

        For a production deployment, swap with PyJWT's `jwt.encode`.
        """
        import base64
        import hashlib
        import hmac
        import json

        header = {"alg": "HS256", "typ": "JWT"}
        payload = {"sub": user_id, "exp": int(time.time()) + ttl_seconds}
        h_b = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=")
        p_b = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=")
        sig = hmac.new(self._jwt_secret.encode(), h_b + b"." + p_b, hashlib.sha256).digest()
        s_b = base64.urlsafe_b64encode(sig).rstrip(b"=")
        return (h_b + b"." + p_b + b"." + s_b).decode()

    def _verify_jwt(self, token: str) -> str | None:
        import base64
        import hashlib
        import hmac
        import json

        try:
            h_b, p_b, s_b = token.split(".")
            expected_sig = hmac.new(
                self._jwt_secret.encode(),
                f"{h_b}.{p_b}".encode(),
                hashlib.sha256,
            ).digest()
            actual_sig = base64.urlsafe_b64decode(s_b + "==")
            if not hmac.compare_digest(expected_sig, actual_sig):
                return None
            payload = json.loads(base64.urlsafe_b64decode(p_b + "=="))
            if payload.get("exp", 0) < time.time():
                return None
            return payload.get("sub")
        except Exception:
            return None

    # --- Authorization -----------------------------------------------------

    def authorize(self, user: User | None, permission: str) -> bool:
        """Return True iff `user` is non-None, active, and has `permission`."""
        if not user or not user.is_active:
            return False
        return has_permission(user.role, permission)

    def require(self, user: User | None, permission: str, *, resource: str = "") -> None:
        """Raise PermissionError if `user` lacks `permission`. Records an
        audit event in either case.
        """
        if self.authorize(user, permission):
            self.audit.record(
                actor_id=user.id if user else "anonymous",
                actor_role=user.role if user else "anonymous",
                action=f"authz.{permission}",
                resource=resource,
            )
            return
        self.audit.record(
            actor_id=user.id if user else "anonymous",
            actor_role=user.role if user else "anonymous",
            action=f"authz.{permission}",
            resource=resource,
            outcome="denied",
        )
        raise PermissionError(
            f"User {user.username if user else '(anonymous)'} lacks permission '{permission}'"
        )

    # --- High-level user management ---------------------------------------

    def create_user(
        self,
        username: str,
        *,
        role: Role | str = Role.MEMBER,
        email: str | None = None,
    ) -> tuple[User, str]:
        role_value = role.value if isinstance(role, Role) else role
        user, raw_key = self.users.create(username=username, role=role_value, email=email)
        self.audit.record(
            actor_id="system",
            actor_role="admin",
            action="user.create",
            resource=f"user:{username}",
            metadata={"role": role_value},
        )
        return user, raw_key

    # --- SSO integration ---------------------------------------------------

    def attach_sso(self, provider: SSOProvider) -> None:
        """Register an SSO provider. Multiple providers can coexist."""
        self._sso_providers[provider.config.provider_name] = provider

    def get_sso(self, provider_name: str) -> SSOProvider | None:
        return self._sso_providers.get(provider_name)

    def list_sso_providers(self) -> list[str]:
        return list(self._sso_providers)

    def upsert_sso_user(self, info: SSOUserInfo, *, provider_name: str = "") -> User:
        """Create-or-update a user from SSO claims.

        Looks up by email; if not found, creates a new user with role
        derived from the IdP groups (via SSOConfig.role_mapping).
        """
        existing = next(
            (u for u in self.users.list_all() if u.email and u.email.lower() == info.email.lower()),
            None,
        )
        # Determine role
        role_str = Role.MEMBER.value
        if provider_name:
            sso = self.get_sso(provider_name)
            if sso:
                for grp in info.groups:
                    if grp in sso.config.role_mapping:
                        role_str = sso.config.role_mapping[grp]
                        break
                else:
                    role_str = sso.config.default_role

        if existing:
            existing.email = info.email
            existing.role = role_str
            existing.metadata["sso_sub"] = info.sub
            existing.metadata["sso_provider"] = provider_name
            self.users.update(existing)
            self.audit.record(
                actor_id=existing.id,
                actor_role=existing.role,
                action="sso.login",
                resource=f"user:{existing.username}",
                metadata={"provider": provider_name},
            )
            return existing

        # Create new SSO user — username derived from email local part
        username = info.email.split("@")[0]
        # Avoid collisions
        if self.users.get_by_username(username):
            username = f"{username}_{info.sub[:6]}"
        user, _raw_key = self.users.create(
            username=username, role=role_str, email=info.email
        )
        user.metadata["sso_sub"] = info.sub
        user.metadata["sso_provider"] = provider_name
        self.users.update(user)
        self.audit.record(
            actor_id=user.id,
            actor_role=user.role,
            action="sso.signup",
            resource=f"user:{user.username}",
            metadata={"provider": provider_name},
        )
        return user

    def update_user(
        self,
        username: str,
        *,
        new_username: str | None = None,
        email: str | None = None,
        role: Role | str | None = None,
        is_active: bool | None = None,
        metadata_updates: dict[str, str] | None = None,
    ) -> User:
        """Edit a user's profile. All fields optional."""
        u = self.users.get_by_username(username)
        if not u:
            raise ValueError(f"Unknown user: {username}")
        changes: dict[str, str] = {}
        if new_username and new_username != u.username:
            if self.users.get_by_username(new_username):
                raise ValueError(f"Username already in use: {new_username}")
            changes["username"] = f"{u.username} -> {new_username}"
            u.username = new_username
        if email is not None:
            changes["email"] = email
            u.email = email
        if role is not None:
            r = role.value if isinstance(role, Role) else role
            changes["role"] = r
            u.role = r
        if is_active is not None:
            changes["is_active"] = str(is_active)
            u.is_active = is_active
        if metadata_updates:
            u.metadata.update(metadata_updates)
            changes["metadata"] = ",".join(metadata_updates)
        self.users.update(u)
        self.audit.record(
            actor_id="system",
            actor_role="admin",
            action="user.update",
            resource=f"user:{u.username}",
            metadata=changes,
        )
        return u

    def delete_user(self, username: str) -> bool:
        """Hard-delete a user and audit the action."""
        u = self.users.get_by_username(username)
        if not u:
            return False
        ok = self.users.delete(u.id)
        if ok:
            self.audit.record(
                actor_id="system",
                actor_role="admin",
                action="user.delete",
                resource=f"user:{username}",
                metadata={"id": u.id},
            )
        return ok

    def deactivate_user(self, username: str) -> None:
        u = self.users.get_by_username(username)
        if not u:
            raise ValueError(f"Unknown user: {username}")
        self.users.deactivate(u.id)
        self.audit.record(
            actor_id="system",
            actor_role="admin",
            action="user.deactivate",
            resource=f"user:{username}",
        )

    def grant_role(self, username: str, role: Role | str) -> None:
        u = self.users.get_by_username(username)
        if not u:
            raise ValueError(f"Unknown user: {username}")
        u.role = role.value if isinstance(role, Role) else role
        self.users.update(u)
        self.audit.record(
            actor_id="system",
            actor_role="admin",
            action="user.grant_role",
            resource=f"user:{username}",
            metadata={"role": u.role},
        )

    # --- Internals ---------------------------------------------------------

    def _save_bootstrap_key(self, raw_key: str) -> None:
        path = self.users.dir / "BOOTSTRAP_API_KEY.txt"
        path.write_text(
            "# Praxia bootstrap admin API key\n"
            "# DELETE this file after copying the key to a secret manager.\n\n"
            f"{raw_key}\n",
            encoding="utf-8",
        )
        try:  # POSIX-only chmod, ignored on Windows
            os.chmod(path, 0o600)
        except Exception:
            pass


# Convenience singleton for simple deployments
_default_manager: AuthManager | None = None


def get_default_manager() -> AuthManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = AuthManager()
    return _default_manager


def authorize_or_raise(user: User | None, permission: str, **kwargs: Any) -> None:
    return get_default_manager().require(user, permission, **kwargs)
