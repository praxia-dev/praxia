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

    return app
