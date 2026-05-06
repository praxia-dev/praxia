"""OAuth 2.0 Authorization Code (with optional PKCE) flow.

Step 1: Build authorization URL → redirect user to provider
Step 2: Provider redirects back with `code` + `state`
Step 3: Exchange `code` for access_token + refresh_token, store

Web servers integrate by handling two endpoints:
    GET  /oauth/<provider>/start    → return authorization_url
    GET  /oauth/<provider>/callback → exchange code, save token, redirect
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from praxia.connectors.oauth.providers import OAuthProviderConfig, PROVIDERS_BY_NAME
from praxia.connectors.oauth.token_store import OAuthToken, OAuthTokenStore


@dataclass
class OAuthState:
    """Per-flow state — opaque token tying the redirect back to the user."""

    user_id: str
    provider: str
    pkce_verifier: str
    redirect_uri: str
    issued_at: float


class OAuthFlow:
    """Authorization Code flow with PKCE + state handling.

    Usage in a web handler:

        flow = OAuthFlow(BOX_OAUTH, client_id=..., client_secret=...,
                        redirect_uri="https://praxia.example.com/oauth/box/callback")

        # Step 1
        auth_url, state = flow.authorization_url(user_id="alice")
        # Save `state` keyed by `state.user_id + provider` somewhere
        # (e.g., a short-TTL store) and 302 the user to auth_url.

        # Step 2 (callback handler receives ?code=...&state=...)
        token = flow.exchange_code(code=request.query["code"],
                                   state=loaded_state_object)
        # Token is saved automatically; the user's connector calls now use it.
    """

    def __init__(
        self,
        provider: OAuthProviderConfig,
        *,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        token_store: OAuthTokenStore | None = None,
        state_store: Any = None,
    ) -> None:
        self.provider = provider
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.store = token_store or OAuthTokenStore()
        # State cache — defaults to in-memory dict (single process).
        # Pass a `PersistentStateStore` for multi-process / multi-host.
        self._state_store = state_store
        self._states: dict[str, OAuthState] = {}

    @classmethod
    def for_provider(cls, name: str, **kwargs: Any) -> "OAuthFlow":
        if name not in PROVIDERS_BY_NAME:
            raise ValueError(f"Unknown OAuth provider: {name}")
        return cls(provider=PROVIDERS_BY_NAME[name], **kwargs)

    # --- Step 1: authorization URL ----------------------------------------

    def authorization_url(
        self,
        *,
        user_id: str,
        scopes: list[str] | None = None,
    ) -> tuple[str, str]:
        """Return (auth_url, state_token). Save the state for Step 2."""
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )

        state_obj = OAuthState(
            user_id=user_id,
            provider=self.provider.name,
            pkce_verifier=verifier,
            redirect_uri=self.redirect_uri,
            issued_at=time.time(),
        )
        if self._state_store is not None:
            self._state_store.put(state, state_obj)
        else:
            self._states[state] = state_obj

        params: dict[str, str] = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(scopes or self.provider.default_scopes),
            "state": state,
        }
        if self.provider.pkce:
            params["code_challenge"] = challenge
            params["code_challenge_method"] = "S256"
        params.update(self.provider.extra_authorize_params)

        url = (
            self.provider.authorize_url
            + "?"
            + urllib.parse.urlencode(params)
        )
        return url, state

    # --- Step 2: exchange code → token ------------------------------------

    def exchange_code(self, *, code: str, state: str) -> OAuthToken:
        """Validate state, exchange code, persist token, return it."""
        if self._state_store is not None:
            flow_state = self._state_store.pop(state)
        else:
            flow_state = self._states.pop(state, None)
        if not flow_state:
            raise ValueError("Unknown or expired state — possible CSRF")
        if flow_state.provider != self.provider.name:
            raise ValueError(
                f"State/provider mismatch: state was for {flow_state.provider} "
                f"but flow is for {self.provider.name}"
            )

        body_params: dict[str, str] = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": flow_state.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        if self.provider.pkce:
            body_params["code_verifier"] = flow_state.pkce_verifier

        body = urllib.parse.urlencode(body_params).encode()
        req = urllib.request.Request(
            self.provider.token_url,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())

        access_token = data["access_token"]
        refresh_token = data.get("refresh_token")
        expires_in = int(data.get(self.provider.expires_in_field, 0) or 0)

        token = OAuthToken(
            user_id=flow_state.user_id,
            provider=self.provider.name,
            access_token=access_token,
            token_type=data.get("token_type", "Bearer"),
            refresh_token=refresh_token,
            expires_at=(time.time() + expires_in) if expires_in else 0.0,
            scope=data.get("scope", ""),
            extra={
                k: v
                for k, v in data.items()
                if k not in ("access_token", "refresh_token", "expires_in", "token_type", "scope")
            },
        )
        self.store.save(token)
        return token

    # --- Optional: revoke -------------------------------------------------

    def revoke(self, token: OAuthToken) -> None:
        """Revoke at the provider and delete locally."""
        if self.provider.revoke_url:
            try:
                body = urllib.parse.urlencode(
                    {"token": token.access_token, "client_id": self.client_id}
                ).encode()
                req = urllib.request.Request(
                    self.provider.revoke_url,
                    data=body,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                urllib.request.urlopen(req, timeout=10)
            except Exception:
                pass  # local cleanup still proceeds
        self.store.delete(token.user_id, token.provider)
