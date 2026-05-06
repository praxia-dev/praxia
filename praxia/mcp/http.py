"""MCP HTTP transport — connect remote MCP clients over HTTP + SSE.

MCP supports two HTTP-based transports per the spec:

    1. Streamable HTTP (recommended)
       POST /mcp     — client sends JSON-RPC; server replies with either
                       a single JSON-RPC response OR an event-stream
                       (Content-Type: text/event-stream) for streaming
                       responses.
       GET  /mcp     — client opens a long-poll SSE for server-initiated
                       notifications (sampling, progress, etc.).

    2. Legacy HTTP+SSE (still supported by older clients)
       POST /mcp/messages — client → server
       GET  /mcp/sse      — server → client (always SSE)

We implement BOTH so any MCP-compliant client can connect.

Auth:
    Same as the rest of `praxia.server`: X-API-Key header or
    Authorization: Bearer <jwt>. An additional shared MCP token is
    accepted via X-MCP-Token (set PRAXIA_MCP_TOKEN to enable).

CORS: configured by the parent app's CORS middleware.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from typing import Any

_log = logging.getLogger(__name__)


def mcp_router(server: Any | None = None):
    """Build a FastAPI APIRouter mounting MCP HTTP + SSE endpoints.

    Args:
        server: a `praxia.mcp.MCPServer` instance. If None, creates a fresh
                one via `MCPServer()` (lazy tool discovery).
    """
    try:
        from fastapi import APIRouter, Depends, Header, HTTPException, Request
        from fastapi.responses import JSONResponse, StreamingResponse
    except ImportError as e:
        raise ImportError(
            "FastAPI is required for the MCP HTTP transport. "
            "Install with: pip install 'praxia[server]'"
        ) from e

    from praxia.mcp.server import MCPServer

    server = server or MCPServer()
    router = APIRouter()

    # In-memory subscription channels for SSE clients. Each connected client
    # gets a Queue that the server pushes notifications onto. A single Praxia
    # process is the assumed deployment unit; for multi-host, replace the
    # in-memory queue with Redis Pub/Sub.
    _channels: dict[str, asyncio.Queue] = {}

    def _verify_auth(
        x_api_key: str | None,
        authorization: str | None,
        x_mcp_token: str | None,
    ) -> None:
        """Accept any of: X-API-Key, Authorization Bearer, or X-MCP-Token."""
        from praxia.auth import AuthManager

        # Optional shared MCP token (operators set PRAXIA_MCP_TOKEN)
        mcp_token = os.getenv("PRAXIA_MCP_TOKEN", "")
        if mcp_token and x_mcp_token:
            from hmac import compare_digest
            if compare_digest(x_mcp_token, mcp_token):
                return

        # Standard Praxia auth
        token = None
        if authorization and authorization.lower().startswith("bearer "):
            token = authorization.split(" ", 1)[1].strip()
        auth = AuthManager()
        if auth.authenticate(api_key=x_api_key, token=token):
            return
        raise HTTPException(401, "Invalid MCP credentials")

    # --- Streamable HTTP (POST /mcp) -----------------------------------

    @router.post("/mcp")
    async def streamable_post(
        request: Request,
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
        authorization: str | None = Header(default=None),
        x_mcp_token: str | None = Header(default=None, alias="X-MCP-Token"),
        accept: str | None = Header(default=None),
    ):
        """JSON-RPC over HTTP. Returns JSON or an SSE event stream."""
        _verify_auth(x_api_key, authorization, x_mcp_token)

        body = await request.body()
        try:
            message = json.loads(body)
        except json.JSONDecodeError:
            raise HTTPException(400, "Invalid JSON body")

        # Notifications (no `id`) → 202 Accepted, no response body
        if message.get("id") is None:
            server.handle(message)  # fire and forget
            return JSONResponse(content={}, status_code=202)

        response = server.handle(message)

        # If the client prefers SSE (and we wanted to stream), return SSE.
        # Praxia tools currently return synchronously; we keep this as JSON.
        if accept and "text/event-stream" in accept:
            async def gen():
                yield f"data: {json.dumps(response, ensure_ascii=False)}\n\n"
            return StreamingResponse(
                gen(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )
        return JSONResponse(content=response)

    # --- Streamable HTTP (GET /mcp) — long-poll for server notifications

    @router.get("/mcp")
    async def streamable_sse(
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
        authorization: str | None = Header(default=None),
        x_mcp_token: str | None = Header(default=None, alias="X-MCP-Token"),
    ):
        _verify_auth(x_api_key, authorization, x_mcp_token)
        return StreamingResponse(
            _sse_event_stream(_channels),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # --- Legacy HTTP+SSE -----------------------------------------------

    @router.post("/mcp/messages")
    async def legacy_messages(
        request: Request,
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
        authorization: str | None = Header(default=None),
        x_mcp_token: str | None = Header(default=None, alias="X-MCP-Token"),
    ):
        _verify_auth(x_api_key, authorization, x_mcp_token)
        body = await request.body()
        try:
            message = json.loads(body)
        except json.JSONDecodeError:
            raise HTTPException(400, "Invalid JSON body")
        if message.get("id") is None:
            server.handle(message)
            return JSONResponse(content={}, status_code=202)
        return JSONResponse(content=server.handle(message))

    @router.get("/mcp/sse")
    async def legacy_sse(
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
        authorization: str | None = Header(default=None),
        x_mcp_token: str | None = Header(default=None, alias="X-MCP-Token"),
    ):
        _verify_auth(x_api_key, authorization, x_mcp_token)
        return StreamingResponse(
            _sse_event_stream(_channels),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # --- Discovery / health -------------------------------------------

    @router.get("/mcp/info")
    async def mcp_info(
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
        authorization: str | None = Header(default=None),
        x_mcp_token: str | None = Header(default=None, alias="X-MCP-Token"),
    ):
        """Public-ish endpoint listing available MCP tools (auth required)."""
        _verify_auth(x_api_key, authorization, x_mcp_token)
        return {
            "name": "praxia-mcp",
            "version": "1.0.0",
            "transports": {
                "http": "/api/v1/mcp",
                "http_sse_legacy": {
                    "messages": "/api/v1/mcp/messages",
                    "sse": "/api/v1/mcp/sse",
                },
            },
            "tools": [
                {"name": t.name, "description": t.description}
                for t in server.tools.values()
            ],
        }

    return router


async def _sse_event_stream(channels: dict[str, asyncio.Queue]):
    """Server-Sent Events generator.

    Each connection gets a fresh Queue. Operators can push events by
    placing dicts on `channels[<id>]` from elsewhere in the app (not
    currently used — Praxia tools are request/response).
    """
    sub_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue(maxsize=64)
    channels[sub_id] = queue
    try:
        # Initial comment to flush headers
        yield ": connected\n\n"
        # Periodic heartbeat keeps proxies from closing the connection
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except asyncio.TimeoutError:
                yield ": ping\n\n"
    finally:
        channels.pop(sub_id, None)


__all__ = ["mcp_router"]
