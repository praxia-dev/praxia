"""SSO (Single Sign-On) adapter — OIDC / OAuth2.

Provides the connection point for enterprise identity providers:
    - Google Workspace
    - Microsoft Entra ID (Azure AD)
    - Okta
    - GitHub Enterprise
    - Any OIDC-compliant IdP (Keycloak, Auth0, Ping, etc.)

SAML 2.0 is **not** shipped here. If you need SAML, integrate
`python3-saml` directly inside your own redirect handler — Praxia's
`AuthManager.upsert_sso_user(...)` accepts the resulting `SSOUserInfo`
without caring how you obtained it.

Usage:
    from praxia.auth import AuthManager
    from praxia.auth.sso import OIDCProvider, SSOConfig

    sso = OIDCProvider(SSOConfig(
        provider_name="google",
        issuer_url="https://accounts.google.com",
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        redirect_uri="https://praxia.example.com/auth/callback",
        scopes=["openid", "email", "profile"],
    ))

    auth = AuthManager()
    auth.attach_sso(sso)

    # In a web handler:
    auth_url = sso.authorization_url(state=session_state)
    # ... user logs in at the IdP, hits the redirect_uri ...
    user_info = sso.exchange_code(code, state=session_state)
    user = auth.upsert_sso_user(user_info)
    token = auth.issue_token(user.id)
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class SSOConfig:
    """Configuration for an OIDC/OAuth2 provider."""

    provider_name: str  # "google" | "microsoft" | "okta" | "github" | custom
    issuer_url: str  # OIDC issuer URL (used to derive .well-known endpoints)
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: list[str] = field(default_factory=lambda: ["openid", "email", "profile"])
    # Optional: explicit endpoints (override discovery)
    authorization_endpoint: str | None = None
    token_endpoint: str | None = None
    userinfo_endpoint: str | None = None
    jwks_uri: str | None = None
    # Role mapping: claim name → role attribute on the IdP side
    role_claim: str = "groups"
    # Default role for SSO users without explicit mapping
    default_role: str = "member"
    # Map IdP groups to Praxia roles, e.g. {"praxia-admins": "admin"}
    role_mapping: dict[str, str] = field(default_factory=dict)


@dataclass
class SSOUserInfo:
    """Normalized user identity returned by the SSO provider."""

    sub: str  # subject identifier (stable across logins)
    email: str
    name: str | None = None
    picture_url: str | None = None
    groups: list[str] = field(default_factory=list)
    raw_claims: dict[str, Any] = field(default_factory=dict)


class SSOProvider(Protocol):
    """Protocol that any SSO provider adapter must satisfy."""

    config: SSOConfig

    def authorization_url(self, state: str, *, nonce: str | None = None) -> str: ...

    def exchange_code(self, code: str, *, state: str) -> SSOUserInfo: ...


class OIDCProvider:
    """Generic OIDC provider — works with Google, Microsoft, Okta, Keycloak, etc.

    Implements the standard `authorization_code + PKCE` flow. No external SDK
    required: uses urllib for HTTP and the provider's discovery document.
    """

    def __init__(self, config: SSOConfig) -> None:
        self.config = config
        self._discovery_cache: dict[str, Any] | None = None
        # PKCE verifier persistence (for stateless web servers, cache per state)
        self._pkce_store: dict[str, str] = {}

    # --- Discovery ---------------------------------------------------------

    def _discover(self) -> dict[str, Any]:
        if self._discovery_cache is None:
            url = self.config.issuer_url.rstrip("/") + "/.well-known/openid-configuration"
            try:
                with urllib.request.urlopen(url, timeout=5) as resp:
                    self._discovery_cache = json.loads(resp.read())
            except Exception:
                self._discovery_cache = {}
        return self._discovery_cache

    def _endpoint(self, name: str) -> str:
        # Prefer explicit config; else derive from discovery
        explicit = getattr(self.config, f"{name.replace('_endpoint', '')}_endpoint", None)
        if explicit:
            return explicit
        d = self._discover()
        if name in d:
            return d[name]
        raise ValueError(f"OIDC endpoint '{name}' not configured and not in discovery")

    # --- Authorization (step 1) --------------------------------------------

    def authorization_url(self, state: str, *, nonce: str | None = None) -> str:
        verifier = secrets.token_urlsafe(64)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        self._pkce_store[state] = verifier
        params = {
            "response_type": "code",
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "scope": " ".join(self.config.scopes),
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        if nonce:
            params["nonce"] = nonce
        return self._endpoint("authorization_endpoint") + "?" + urllib.parse.urlencode(params)

    # --- Token exchange (step 2) -------------------------------------------

    def exchange_code(self, code: str, *, state: str) -> SSOUserInfo:
        verifier = self._pkce_store.pop(state, None)
        if not verifier:
            raise ValueError("Unknown/expired state — possible CSRF attack")

        body = urllib.parse.urlencode(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.config.redirect_uri,
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "code_verifier": verifier,
            }
        ).encode()
        req = urllib.request.Request(
            self._endpoint("token_endpoint"),
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            tokens = json.loads(resp.read())

        id_token = tokens.get("id_token")
        access_token = tokens.get("access_token")
        if not (id_token or access_token):
            raise ValueError("Token response missing id_token and access_token")

        # Get userinfo. Prefer userinfo endpoint over decoding id_token, since
        # signature verification of id_token requires JWKS — we keep it
        # lightweight here and let production deploys plug in PyJWT/Authlib.
        userinfo: dict[str, Any] = {}
        if access_token:
            try:
                req = urllib.request.Request(
                    self._endpoint("userinfo_endpoint"),
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    userinfo = json.loads(resp.read())
            except Exception:
                pass
        if not userinfo and id_token:
            userinfo = self._decode_jwt_payload_unsafe(id_token)

        return SSOUserInfo(
            sub=str(userinfo.get("sub", "")),
            email=str(userinfo.get("email", "")),
            name=userinfo.get("name"),
            picture_url=userinfo.get("picture"),
            groups=list(userinfo.get(self.config.role_claim, []) or []),
            raw_claims=userinfo,
        )

    @staticmethod
    def _decode_jwt_payload_unsafe(token: str) -> dict[str, Any]:
        """Decode without signature verification.

        Production deployments MUST verify against JWKS. This helper exists
        only as a fallback when the userinfo endpoint is unreachable.
        """
        try:
            _, payload, _ = token.split(".")
            return json.loads(base64.urlsafe_b64decode(payload + "==="))
        except Exception:
            return {}


# --- Provider presets --------------------------------------------------------

def google_provider(client_id: str, client_secret: str, redirect_uri: str) -> OIDCProvider:
    return OIDCProvider(
        SSOConfig(
            provider_name="google",
            issuer_url="https://accounts.google.com",
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            role_claim="groups",
        )
    )


def microsoft_provider(
    tenant_id: str, client_id: str, client_secret: str, redirect_uri: str
) -> OIDCProvider:
    return OIDCProvider(
        SSOConfig(
            provider_name="microsoft",
            issuer_url=f"https://login.microsoftonline.com/{tenant_id}/v2.0",
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            role_claim="roles",
        )
    )


def okta_provider(
    okta_domain: str, client_id: str, client_secret: str, redirect_uri: str
) -> OIDCProvider:
    return OIDCProvider(
        SSOConfig(
            provider_name="okta",
            issuer_url=f"https://{okta_domain}",
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            role_claim="groups",
        )
    )


def github_provider(client_id: str, client_secret: str, redirect_uri: str) -> OIDCProvider:
    """GitHub uses OAuth2 (not strict OIDC). Endpoints supplied explicitly."""
    return OIDCProvider(
        SSOConfig(
            provider_name="github",
            issuer_url="https://github.com",
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scopes=["read:user", "user:email", "read:org"],
            authorization_endpoint="https://github.com/login/oauth/authorize",
            token_endpoint="https://github.com/login/oauth/access_token",
            userinfo_endpoint="https://api.github.com/user",
        )
    )


def keycloak_provider(
    base_url: str, realm: str, client_id: str, client_secret: str, redirect_uri: str
) -> OIDCProvider:
    return OIDCProvider(
        SSOConfig(
            provider_name="keycloak",
            issuer_url=f"{base_url.rstrip('/')}/realms/{realm}",
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
        )
    )


# --- SAML (skeleton) ---------------------------------------------------------

# --- Provider factory --------------------------------------------------------

def provider_from_env(prefix: str = "PRAXIA_SSO") -> SSOProvider:
    """Build a provider from environment variables.

    Required vars (named based on prefix):
        {prefix}_PROVIDER     google|microsoft|okta|github|keycloak|custom_oidc
        {prefix}_CLIENT_ID
        {prefix}_CLIENT_SECRET
        {prefix}_REDIRECT_URI

    Provider-specific vars:
        {prefix}_TENANT_ID    (microsoft)
        {prefix}_OKTA_DOMAIN  (okta)
        {prefix}_KEYCLOAK_BASE_URL + _KEYCLOAK_REALM
        {prefix}_ISSUER_URL   (custom_oidc)
    """
    p = (os.getenv(f"{prefix}_PROVIDER") or "").lower()
    cid = os.environ[f"{prefix}_CLIENT_ID"]
    secret = os.environ[f"{prefix}_CLIENT_SECRET"]
    redirect = os.environ[f"{prefix}_REDIRECT_URI"]
    if p == "google":
        return google_provider(cid, secret, redirect)
    if p == "microsoft":
        tenant = os.environ[f"{prefix}_TENANT_ID"]
        return microsoft_provider(tenant, cid, secret, redirect)
    if p == "okta":
        domain = os.environ[f"{prefix}_OKTA_DOMAIN"]
        return okta_provider(domain, cid, secret, redirect)
    if p == "github":
        return github_provider(cid, secret, redirect)
    if p == "keycloak":
        base = os.environ[f"{prefix}_KEYCLOAK_BASE_URL"]
        realm = os.environ[f"{prefix}_KEYCLOAK_REALM"]
        return keycloak_provider(base, realm, cid, secret, redirect)
    if p in ("custom_oidc", "oidc", ""):
        issuer = os.environ[f"{prefix}_ISSUER_URL"]
        return OIDCProvider(
            SSOConfig(
                provider_name="custom_oidc",
                issuer_url=issuer,
                client_id=cid,
                client_secret=secret,
                redirect_uri=redirect,
            )
        )
    raise ValueError(f"Unknown SSO provider: {p}")
