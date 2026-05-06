"""Minimal FastAPI app exposing Praxia's SDK over HTTP.

Versioned under `/api/v1`. Authenticates via API key (`X-API-Key`) or JWT
(`Authorization: Bearer <jwt>`). Both are issued by the same `AuthManager`
that the SDK / Streamlit UI use, so RBAC and audit logging are unified.

Endpoints (intentionally small — extend in your own subclass if needed):

    POST /api/v1/auth/login          → JWT for an API key
    GET  /api/v1/me                  → current user info
    POST /api/v1/skills/{name}       → run a skill
    POST /api/v1/flows/{name}        → run a flow
    POST /api/v1/memory/search       → semantic search
    PUT  /api/v1/memory/mode         → switch accumulate / read_only
    GET  /api/v1/memory/show         → effective resolved config
    POST /api/v1/export              → render content to html/pptx/docx/json

The server module is optional — install with `pip install 'praxia[server]'`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def create_app(
    *,
    storage_dir: Path | str = ".praxia",
    cors_origins: list[str] | None = None,
):
    """Build the FastAPI app. Lazily imports FastAPI to keep optional."""
    try:
        from fastapi import Depends, FastAPI, Header, HTTPException, status
        from fastapi.middleware.cors import CORSMiddleware
        from pydantic import BaseModel
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "FastAPI is required for `praxia.server`. "
            "Install with: pip install 'praxia[server]'"
        ) from e

    from praxia.auth import AuthManager
    from praxia.io.exporters import export_as
    from praxia.memory import (
        PersonalMemory,
        resolve_memory_config,
        MemoryUserPreference,
    )

    storage = Path(storage_dir)
    auth = AuthManager(storage_dir=storage / "auth")

    app = FastAPI(title="Praxia", version="1.0.0")

    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # --- Auth dependency ----------------------------------------------------

    def current_user(
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
        authorization: str | None = Header(default=None),
    ):
        token = None
        if authorization and authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1].strip()
        user = auth.authenticate(api_key=x_api_key, token=token)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )
        return user

    # --- Schemas ------------------------------------------------------------

    class LoginRequest(BaseModel):
        api_key: str

    class SkillCallRequest(BaseModel):
        input: str
        kwargs: dict[str, Any] = {}

    class FlowCallRequest(BaseModel):
        inputs: dict[str, Any]

    class MemorySearchRequest(BaseModel):
        query: str
        limit: int = 5

    class MemoryModeRequest(BaseModel):
        mode: str  # "accumulate" | "read_only"

    class ExportRequest(BaseModel):
        content: str
        format: str
        title: str | None = None

    # --- Routes -------------------------------------------------------------

    @app.post("/api/v1/auth/login")
    def login(req: LoginRequest):
        user = auth.authenticate(api_key=req.api_key)
        if user is None:
            raise HTTPException(401, "Invalid API key")
        token = auth.issue_token(user.id)
        return {"token": token, "user_id": user.id, "role": user.role}

    @app.get("/api/v1/me")
    def me(user=Depends(current_user)):
        return {"id": user.id, "username": user.username, "role": user.role}

    @app.post("/api/v1/skills/{name}")
    def run_skill(name: str, req: SkillCallRequest, user=Depends(current_user)):
        from praxia.skills import SKILLS

        if not SKILLS.has(name):
            raise HTTPException(404, f"Unknown skill: {name}")
        skill = SKILLS.get(name)()
        output = skill.run(req.input, **req.kwargs)
        return {"output": output, "skill": name}

    @app.post("/api/v1/flows/{name}")
    def run_flow(name: str, req: FlowCallRequest, user=Depends(current_user)):
        from praxia.flows import get_flow

        try:
            flow_cls = get_flow(name)
        except KeyError:
            raise HTTPException(404, f"Unknown flow: {name}")
        flow = flow_cls()
        result = flow.run(req.inputs)
        return {
            "output": result.final_output,
            "step_outputs": result.step_outputs,
            "usage": result.total_usage,
        }

    @app.post("/api/v1/memory/search")
    def memory_search(req: MemorySearchRequest, user=Depends(current_user)):
        cfg = resolve_memory_config(
            user_id=user.id, storage_dir=storage, user_role=user.role
        )
        pm = PersonalMemory(
            user_id=user.id,
            backend=cfg.backend,
            storage_dir=storage / "personal",
            mode=cfg.mode,
        )
        return {"results": pm.search(req.query, limit=req.limit)}

    @app.put("/api/v1/memory/mode")
    def memory_set_mode(req: MemoryModeRequest, user=Depends(current_user)):
        if req.mode not in ("accumulate", "read_only"):
            raise HTTPException(400, "mode must be 'accumulate' or 'read_only'")
        pref = MemoryUserPreference.load(storage, user.id)
        pref.mode = req.mode  # type: ignore[assignment]
        pref.save(storage)
        return {"ok": True, "mode": req.mode}

    @app.get("/api/v1/memory/show")
    def memory_show(user=Depends(current_user)):
        cfg = resolve_memory_config(
            user_id=user.id, storage_dir=storage, user_role=user.role
        )
        return {
            "backend": cfg.backend,
            "mode": cfg.mode,
            "locked_by_admin": cfg.locked_by_admin,
            "reason": cfg.reason,
        }

    @app.post("/api/v1/export")
    def export(req: ExportRequest, user=Depends(current_user)):
        from fastapi.responses import Response

        kwargs = {"title": req.title} if req.title else {}
        result = export_as(req.content, format=req.format, **kwargs)
        media_type = {
            "html": "text/html",
            "md": "text/markdown",
            "json": "application/json",
            "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }.get(req.format, "application/octet-stream")
        return Response(content=result.bytes, media_type=media_type)

    # --- OAuth web handler -------------------------------------------------
    # OAuth-related imports are deferred so server users without OAuth
    # configured don't pay the startup cost.

    from fastapi import HTTPException, Request
    from fastapi.responses import HTMLResponse, RedirectResponse

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

    @app.post("/api/v1/oauth/{provider}/start")
    def oauth_start(
        provider: str, request: Request, user=Depends(current_user)
    ):
        """Build the IdP authorization URL for the current user.

        Returns the URL — the caller (frontend) issues the redirect.
        Set `PRAXIA_PUBLIC_URL` in production so the redirect URI is
        stable regardless of which worker handled this request.
        """
        base_url = os.environ.get("PRAXIA_PUBLIC_URL") or (
            f"{request.url.scheme}://{request.url.netloc}"
        )
        flow = _build_oauth_flow(provider, base_url)
        url, state = flow.authorization_url(user_id=user.id)
        return {"authorize_url": url, "state": state, "provider": provider}

    @app.get("/api/v1/oauth/{provider}/callback")
    def oauth_callback(
        provider: str,
        request: Request,
        code: str | None = None,
        state: str | None = None,
        error: str | None = None,
    ):
        """Handle the IdP redirect: exchange code → token, then redirect back.

        Note this endpoint does NOT require an authenticated user — the
        IdP sends the redirect directly. Authentication is implicit via
        the `state` token, which is single-use and tied to a user_id at
        `/start` time.
        """
        if error:
            return HTMLResponse(
                f"<h1>Authorization failed</h1><p>{error}</p>",
                status_code=400,
            )
        if not (code and state):
            return HTMLResponse(
                "<h1>Authorization failed</h1><p>missing code or state</p>",
                status_code=400,
            )

        base_url = os.environ.get("PRAXIA_PUBLIC_URL") or (
            f"{request.url.scheme}://{request.url.netloc}"
        )
        flow = _build_oauth_flow(provider, base_url)
        try:
            token = flow.exchange_code(code=code, state=state)
        except Exception as e:  # CSRF / IdP error / network
            return HTMLResponse(
                f"<h1>Authorization failed</h1><p>{type(e).__name__}: {e}</p>",
                status_code=400,
            )

        # Optional redirect back to the frontend after success
        redirect_to = os.environ.get("PRAXIA_OAUTH_SUCCESS_REDIRECT")
        if redirect_to:
            return RedirectResponse(redirect_to, status_code=302)
        # Default: a tiny success page so the browser tab can be closed
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

    @app.get("/api/v1/oauth/{provider}/status")
    def oauth_status(provider: str, user=Depends(current_user)):
        """Whether the current user has a valid token for this provider."""
        from praxia.connectors.oauth import OAuthTokenStore
        from praxia.connectors.oauth.providers import PROVIDERS_BY_NAME

        if provider not in PROVIDERS_BY_NAME:
            from fastapi import HTTPException
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

    @app.delete("/api/v1/oauth/{provider}")
    def oauth_revoke(provider: str, user=Depends(current_user)):
        """Revoke (locally) the user's token for `provider`."""
        from praxia.connectors.oauth import OAuthTokenStore

        token_store = OAuthTokenStore(storage_dir=storage / "auth")
        deleted = token_store.delete(user.id, provider)
        return {"deleted": deleted}

    # --- SCIM provisioning (optional) ---------------------------------------
    # Mount only if PRAXIA_SCIM_TOKEN is set — keeps the surface area minimal
    # for operators who don't need it.
    if os.environ.get("PRAXIA_SCIM_TOKEN"):
        try:
            from praxia.scim import scim_router
            app.include_router(scim_router(auth=auth), prefix="/scim/v2")
        except ImportError:
            pass  # SCIM module imports cleanly even without FastAPI

    return app
