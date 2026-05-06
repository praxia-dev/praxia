"""Model Context Protocol (MCP) server — expose Praxia as an MCP server.

Praxia already imports / exports skills in the Claude Skills format. This
module turns the running Praxia install into an **MCP server** so that
Claude Desktop, Cursor, Continue.dev, or any MCP client can discover and
invoke Praxia capabilities.

Exposed surface:
    - resources/  : Praxia memory entries, shared blocks, frozen Markdown
    - tools/      : Each business skill becomes one MCP tool
                    Each multi-agent flow becomes one MCP tool
                    Plus utility tools: search_memory, export_as

Transport modes:
    - **stdio** (default for desktop clients)  —  `praxia mcp serve`
    - **HTTP+SSE** (for remote clients)        —  `praxia mcp serve --http --port 9000`

Auth:
    - stdio mode runs as the local user; no auth (process boundary is enough).
    - HTTP mode requires either an API key (X-API-Key header) or a
      pre-shared MCP token (PRAXIA_MCP_TOKEN env).

Spec: https://modelcontextprotocol.io/
"""
from praxia.mcp.server import (
    MCPServer,
    build_tools,
    serve_stdio,
)


def mcp_router(*args, **kwargs):
    """Lazy factory — defers FastAPI import until actually mounted."""
    from praxia.mcp.http import mcp_router as _impl
    return _impl(*args, **kwargs)


__all__ = [
    "MCPServer",
    "build_tools",
    "serve_stdio",
    "mcp_router",
]
