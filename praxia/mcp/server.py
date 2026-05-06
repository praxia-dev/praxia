"""Minimal MCP server (JSON-RPC 2.0 over stdio).

The full spec covers tools / resources / prompts / sampling. We implement
the subset that Claude Desktop and similar clients exercise:

    - initialize
    - tools/list
    - tools/call
    - resources/list
    - resources/read

Tool handlers wrap each registered Praxia skill + flow. Resource handlers
wrap shared memory + frozen Markdown.
"""
from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass, field
from typing import Any, Callable

_log = logging.getLogger(__name__)

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "praxia-mcp"
SERVER_VERSION = "1.0.0"


# --- Tool descriptor ------------------------------------------------------

@dataclass
class MCPTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], str]


# --- Tool factory ---------------------------------------------------------

def build_tools(*, llm: Any = None) -> list[MCPTool]:
    """Materialize tools from registered skills + flows."""
    from praxia.skills import SKILLS
    from praxia.flows import FLOWS

    tools: list[MCPTool] = []

    # 1. Every registered skill → one tool
    for name, cls in SKILLS.items():
        manifest = cls.manifest
        tools.append(MCPTool(
            name=f"skill_{name}",
            description=f"[{manifest.domain}] {manifest.description}",
            input_schema={
                "type": "object",
                "properties": {
                    "input": {"type": "string", "description": "user input / task description"},
                },
                "required": ["input"],
            },
            handler=lambda args, _cls=cls: _cls(llm=llm).run(args["input"]),
        ))

    # 2. Every registered flow → one tool
    for name in FLOWS.list():
        cls = FLOWS.get(name)
        tools.append(MCPTool(
            name=f"flow_{name}",
            description=f"Multi-agent flow: {getattr(cls, 'description', name)}",
            input_schema={
                "type": "object",
                "properties": {
                    "inputs": {
                        "type": "object",
                        "description": "Flow inputs (key/value)",
                    },
                },
                "required": ["inputs"],
            },
            handler=lambda args, _cls=cls: _run_flow(_cls, args.get("inputs", {})),
        ))

    # 3. Utility tools
    tools.extend([
        MCPTool(
            name="search_memory",
            description="Search the user's personal memory for relevant context.",
            input_schema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 5},
                },
                "required": ["user_id", "query"],
            },
            handler=_search_memory,
        ),
        MCPTool(
            name="autonomous_agent",
            description=(
                "Run a Claude-Code-style autonomous agent that can search "
                "personal/org memory, run skills, and pull from connectors "
                "on its own. Use this for open-ended tasks where you don't "
                "want to orchestrate individual tools."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "task": {"type": "string", "description": "task / question for the agent"},
                    "role": {"type": "string", "default": "member"},
                    "org_id": {"type": "string", "default": "default-org"},
                    "max_steps": {"type": "integer", "default": 10},
                },
                "required": ["user_id", "task"],
            },
            handler=lambda args, _llm=llm: _run_autonomous_agent(args, _llm),
        ),
        MCPTool(
            name="export_as",
            description="Render Markdown content to html/pptx/docx/json.",
            input_schema={
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "format": {"type": "string", "enum": ["md", "html", "pptx", "docx", "json"]},
                    "title": {"type": "string"},
                },
                "required": ["content", "format"],
            },
            handler=_export_as,
        ),
    ])
    return tools


def _run_flow(flow_cls: Any, inputs: dict[str, Any]) -> str:
    """Run a flow and return final_output."""
    result = flow_cls().run(inputs)
    return getattr(result, "final_output", str(result))


def _search_memory(args: dict[str, Any]) -> str:
    from praxia import PersonalMemory
    pm = PersonalMemory(user_id=args["user_id"])
    hits = pm.search(args["query"], limit=int(args.get("limit", 5)))
    return "\n---\n".join(hits) if hits else "(no relevant memories)"


def _run_autonomous_agent(args: dict[str, Any], llm: Any) -> str:
    """Invoke the AutonomousAgent and return its final answer.

    Surfacing it as a single MCP tool lets a remote client (Claude Desktop,
    Cursor) delegate an entire investigation rather than orchestrating the
    individual memory/skill/connector tools by hand.
    """
    from praxia.agent import AutonomousAgent
    from praxia.core.llm import LLM

    agent = AutonomousAgent(
        user_id=args["user_id"],
        role=args.get("role", "member"),
        org_id=args.get("org_id", "default-org"),
        llm=llm or LLM(),
        max_steps=int(args.get("max_steps", 10)),
    )
    result = agent.run(args["task"])
    return result.final_text


def _export_as(args: dict[str, Any]) -> str:
    """Returns base64-encoded bytes for binary formats; raw for text."""
    import base64
    from praxia.io.exporters import export_as
    kwargs = {"title": args["title"]} if args.get("title") else {}
    result = export_as(args["content"], format=args["format"], **kwargs)
    if args["format"] in ("md", "html", "json"):
        return result.bytes.decode("utf-8")
    return base64.b64encode(result.bytes).decode("ascii")


# --- Server loop ---------------------------------------------------------

class MCPServer:
    """Minimal MCP server speaking JSON-RPC 2.0 over a (read, write) pair."""

    def __init__(self, tools: list[MCPTool] | None = None) -> None:
        self.tools = {t.name: t for t in (tools or build_tools())}

    def handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        method = message.get("method")
        msg_id = message.get("id")
        params = message.get("params") or {}

        if method == "initialize":
            return self._respond(msg_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"listChanged": False, "subscribe": False},
                },
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            })

        if method == "tools/list":
            return self._respond(msg_id, {
                "tools": [
                    {
                        "name": t.name,
                        "description": t.description,
                        "inputSchema": t.input_schema,
                    }
                    for t in self.tools.values()
                ],
            })

        if method == "tools/call":
            tool_name = params.get("name")
            args = params.get("arguments") or {}
            tool = self.tools.get(tool_name)
            if tool is None:
                return self._error(msg_id, -32602, f"Unknown tool: {tool_name}")
            try:
                result = tool.handler(args)
            except Exception as e:
                return self._error(msg_id, -32000, f"{type(e).__name__}: {e}")
            return self._respond(msg_id, {
                "content": [{"type": "text", "text": str(result)}],
                "isError": False,
            })

        if method == "resources/list":
            from praxia import SharedMemory
            try:
                sm = SharedMemory(org_id="default-org")
                blocks = sm.list()
                resources = [{
                    "uri": f"praxia://shared/{b.label}",
                    "name": b.label,
                    "description": b.description or "",
                    "mimeType": "text/markdown",
                } for b in blocks]
            except Exception:
                resources = []
            return self._respond(msg_id, {"resources": resources})

        if method == "resources/read":
            uri = params.get("uri", "")
            from praxia import SharedMemory
            if uri.startswith("praxia://shared/"):
                label = uri[len("praxia://shared/"):]
                try:
                    sm = SharedMemory(org_id="default-org")
                    blk = sm.get_by_label(label)
                    if blk:
                        return self._respond(msg_id, {
                            "contents": [{
                                "uri": uri,
                                "mimeType": "text/markdown",
                                "text": blk.value,
                            }],
                        })
                except Exception:
                    pass
            return self._error(msg_id, -32602, f"Unknown resource: {uri}")

        # Unknown methods
        if msg_id is not None:
            return self._error(msg_id, -32601, f"Method not found: {method}")
        return None  # notifications: no response

    @staticmethod
    def _respond(msg_id: Any, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    @staticmethod
    def _error(msg_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def serve_stdio(server: MCPServer | None = None) -> None:
    """Read JSON-RPC messages from stdin, write responses to stdout."""
    server = server or MCPServer()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = server.handle(msg)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
