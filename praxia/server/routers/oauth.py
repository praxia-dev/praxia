"""OAuth web handler: /oauth/{provider}/{start,callback,status} + DELETE."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def build_router(*, current_user: Any, storage: Path):
    from fastapi import APIRouter, Depends, HTTPException, Request
    from fastapi.responses import HTMLResponse, RedirectResponse

    router = APIRouter()

    def _build_oauth_flow(provider_name: str, base_url: str):
        from praxia.connectors.oauth import (
            OAuthFlow,
            OAuthTokenStore,
            PersistentStateStore,
        )
        from praxia.connectors.oauth.providers import PROVIDERS_BY_NAME

        if provider_name not in PROVIDERS_BY_NAME:
            raise HTTPException(404, f"Unknown OAuth provider: {provider_name}")
        cid = os.environ.get(f"PRAXIA_OAUTH_{provider_name.upper()}_CLIENT_ID")
        csec = os.environ.get(f"PRAXIA_OAUTH_{provider_name.upper()}_CLIENT_SECRET")
        if not (cid and csec):
            raise HTTPException(
                503,
                f"OAuth client not configured for {provider_name}. "
                f"Set PRAXIA_OAUTH_{provider_name.upper()}_CLIENT_ID and _CLIENT_SECRET.",
            )
        redirect_uri = f"{base_url}/api/v1/oauth/{provider_name}/callback"
        return OAuthFlow(
            PROVIDERS_BY_NAME[provider_name],
            client_id=cid,
            client_secret=csec,
            redirect_uri=redirect_uri,
            token_store=OAuthTokenStore(storage_dir=storage / "auth"),
            state_store=PersistentStateStore(storage_dir=storage / "auth"),
        )

    def _base_url(request: Request) -> str:
        return os.environ.get("PRAXIA_PUBLIC_URL") or (
            f"{request.url.scheme}://{request.url.netloc}"
        )

    @router.post("/oauth/{provider}/start")
    def oauth_start(provider: str, request: Request, user=Depends(current_user)):
        """Build the IdP authorization URL for the current user."""
        flow = _build_oauth_flow(provider, _base_url(request))
        url, state = flow.authorization_url(user_id=user.id)
        return {"authorize_url": url, "state": state, "provider": provider}

    @router.get("/oauth/{provider}/callback")
    def oauth_callback(
        provider: str,
        request: Request,
        code: str | None = None,
        state: str | None = None,
        error: str | None = None,
    ):
        """Handle the IdP redirect → exchange code → save token."""
        if error:
            return HTMLResponse(
                f"<h1>Authorization failed</h1><p>{error}</p>", status_code=400,
            )
        if not (code and state):
            return HTMLResponse(
                "<h1>Authorization failed</h1><p>missing code or state</p>",
                status_code=400,
            )
        flow = _build_oauth_flow(provider, _base_url(request))
        try:
            token = flow.exchange_code(code=code, state=state)
        except Exception as e:
            return HTMLResponse(
                f"<h1>Authorization failed</h1><p>{type(e).__name__}: {e}</p>",
                status_code=400,
            )
        redirect_to = os.environ.get("PRAXIA_OAUTH_SUCCESS_REDIRECT")
        if redirect_to:
            return RedirectResponse(redirect_to, status_code=302)
        return HTMLResponse(
            f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Authorized</title></head>
<body style="font-family:sans-serif;padding:2rem">
  <h1>✅ Authorized</h1>
  <p>{token.user_id} can now use the {provider} connector.</p>
  <p>You can close this tab.</p>
</body></html>""",
            status_code=200,
        )

    @router.get("/oauth/{provider}/status")
    def oauth_status(provider: str, user=Depends(current_user)):
        from praxia.connectors.oauth import OAuthTokenStore
        from praxia.connectors.oauth.providers import PROVIDERS_BY_NAME

        if provider not in PROVIDERS_BY_NAME:
            raise HTTPException(404, f"Unknown provider: {provider}")
        token_store = OAuthTokenStore(storage_dir=storage / "auth")
        token = token_store.get(user.id, provider)
        if token is None:
            return {"authorized": False, "expires_at": None}
        return {
            "authorized": True,
            "expires_at": token.expires_at,
            "is_expired": token.is_expired(),
            "scope": token.scope,
        }

    @router.delete("/oauth/{provider}")
    def oauth_revoke(provider: str, user=Depends(current_user)):
        from praxia.connectors.oauth import OAuthTokenStore

        token_store = OAuthTokenStore(storage_dir=storage / "auth")
        deleted = token_store.delete(user.id, provider)
        return {"deleted": deleted}

    return router
