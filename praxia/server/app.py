"""FastAPI factory — wires the per-feature routers into one app.

The routes themselves live in `praxia.server.routers.*`. This file owns:
    - app construction + CORS
    - shared `current_user` dependency (auth)
    - mounting the routers under `/api/v1`
    - optional mounts: SCIM (`/scim/v2`) when `PRAXIA_SCIM_TOKEN` is set,
      MCP HTTP (`/api/v1/mcp*`) — always available

Endpoints exposed (versioned under `/api/v1` unless noted):

    POST /auth/login          → JWT for an API key
    GET  /me                  → current user info
    POST /skills/{name}       → run a skill
    POST /flows/{name}        → run a flow
    POST /memory/search       → semantic search
    PUT  /memory/mode         → switch accumulate / read_only
    GET  /memory/show         → effective resolved memory config
    POST /export              → render content to html/pptx/docx/json
    POST /oauth/{p}/start     → begin per-user OAuth
    GET  /oauth/{p}/callback  → IdP redirect handler
    GET  /oauth/{p}/status    → token presence + expiry
    DELETE /oauth/{p}         → revoke locally
    GET    /threads                       → list user's chat threads
    POST   /threads                       → create a new thread
    GET    /threads/{thread_id}           → full thread + messages
    POST   /threads/{thread_id}/messages  → append a message
    DELETE /threads/{thread_id}           → remove a thread
    POST /agent/run           → run autonomous (or commanded) agent
    POST   /documents/folder                       register a local folder
    GET    /documents/folders                      list user's registered folders
    GET    /documents/folder/{folder_id}           folder details + doc list
    DELETE /documents/folder/{folder_id}           remove a folder
    POST   /documents/folder/{folder_id}/upload    upload one parsed file
    POST   /documents/search                       keyword search across documents
    POST /mcp                 → MCP Streamable HTTP
    GET  /mcp                 → MCP SSE
    POST /mcp/messages        → MCP legacy HTTP+SSE messages
    GET  /mcp/sse             → MCP legacy HTTP+SSE event stream
    GET  /mcp/info            → MCP discovery
    GET  /scim/v2/Users (etc.) → SCIM 2.0 (only when PRAXIA_SCIM_TOKEN is set)

Install: `pip install 'praxia[server]'`.
"""
from __future__ import annotations

import os
from pathlib import Path


def create_app(
    *,
    storage_dir: Path | str = ".praxia",
    cors_origins: list[str] | None = None,
):
    """Build the FastAPI app. Lazily imports FastAPI to keep optional."""
    try:
        from fastapi import FastAPI, Header, HTTPException, status
        from fastapi.middleware.cors import CORSMiddleware
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "FastAPI is required for `praxia.server`. "
            "Install with: pip install 'praxia[server]'"
        ) from e

    from praxia.auth import AuthManager

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

    # --- Shared auth dependency --------------------------------------------

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

    # --- Per-feature routers under /api/v1 ---------------------------------

    from praxia.server.routers import agent as agent_router
    from praxia.server.routers import auth as auth_router
    from praxia.server.routers import documents as documents_router
    from praxia.server.routers import export_ as export_router
    from praxia.server.routers import flows as flows_router
    from praxia.server.routers import memory as memory_router
    from praxia.server.routers import oauth as oauth_router
    from praxia.server.routers import schedules as schedules_router
    from praxia.server.routers import skills as skills_router
    from praxia.server.routers import tasks as tasks_router
    from praxia.server.routers import threads as threads_router
    from praxia.server.routers import batch as batch_router

    app.include_router(
        auth_router.build_router(auth=auth, current_user=current_user),
        prefix="/api/v1",
    )
    app.include_router(
        skills_router.build_router(current_user=current_user),
        prefix="/api/v1",
    )
    app.include_router(
        flows_router.build_router(current_user=current_user),
        prefix="/api/v1",
    )
    app.include_router(
        memory_router.build_router(current_user=current_user, storage=storage),
        prefix="/api/v1",
    )
    app.include_router(
        export_router.build_router(current_user=current_user),
        prefix="/api/v1",
    )
    app.include_router(
        oauth_router.build_router(current_user=current_user, storage=storage),
        prefix="/api/v1",
    )
    app.include_router(
        threads_router.build_router(current_user=current_user, storage=storage),
        prefix="/api/v1",
    )
    app.include_router(
        agent_router.build_router(current_user=current_user, storage=storage),
        prefix="/api/v1",
    )
    app.include_router(
        documents_router.build_router(current_user=current_user, storage=storage),
        prefix="/api/v1",
    )
    app.include_router(
        tasks_router.build_router(current_user=current_user, storage=storage),
        prefix="/api/v1",
    )
    app.include_router(
        schedules_router.build_router(current_user=current_user, storage=storage),
        prefix="/api/v1",
    )
    app.include_router(
        batch_router.build_router(current_user=current_user, storage=storage),
        prefix="/api/v1",
    )

    # --- SCIM (optional, mounts only when token configured) ----------------

    if os.environ.get("PRAXIA_SCIM_TOKEN"):
        try:
            from praxia.scim import scim_router
            app.include_router(scim_router(auth=auth), prefix="/scim/v2")
        except ImportError:
            pass

    # --- MCP HTTP transport (always available) -----------------------------

    try:
        from praxia.mcp.http import mcp_router
        app.include_router(mcp_router(), prefix="/api/v1")
    except ImportError:
        pass

    return app
