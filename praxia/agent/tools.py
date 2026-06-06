"""Built-in tools exposed to the AutonomousAgent's LLM.

A "tool" here is a small adapter around an existing Praxia primitive. Each
tool has:

    - `name`               : matches what the LLM will call.
    - `description`        : tells the LLM when to use it.
    - `parameters_schema`  : OpenAI / LiteLLM function-calling JSON Schema.
    - `handler(agent, **kw)`: the actual Python implementation.

The tools intentionally favor *reading* the personal + organizational stack so
the agent can answer "what do I know about X" before reaching for connectors.
The single write tool (`record_fact`) silently no-ops when memory is in
`read_only` mode — required to honor admin policies in regulated deployments.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from praxia.agent.autonomous import AutonomousAgent


@dataclass
class AgentTool:
    name: str
    description: str
    parameters_schema: dict[str, Any]
    handler: Callable[..., Any]

    def to_litellm_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }


# --- Tool implementations ----------------------------------------------------


def _search_personal_memory(agent: AutonomousAgent, query: str, limit: int = 5) -> dict[str, Any]:
    pm = agent._personal_memory()
    hits = pm.search(query, limit=int(limit))
    return {"hits": hits, "count": len(hits)}


def _record_fact(agent: AutonomousAgent, text: str) -> dict[str, Any]:
    pm = agent._personal_memory()
    if pm.mode == "read_only":
        return {"recorded": False, "reason": "memory mode is read_only"}
    entry = pm.record_fact(text)
    return {"recorded": True, "id": entry.id}


def _list_personal_skills(agent: AutonomousAgent) -> dict[str, Any]:
    reg = agent._skill_registry()
    items = reg.list_personal(agent.user_id)
    return {
        "skills": [
            {"name": s.name, "scope": s.scope, "path": str(s.manifest_path)}
            for s in items
        ],
        "count": len(items),
    }


def _list_org_skills(agent: AutonomousAgent) -> dict[str, Any]:
    reg = agent._skill_registry()
    items = reg.list_for_user(user_id=agent.user_id, role=agent.role)
    return {
        "skills": [
            {"name": s.name, "scope": s.scope, "path": str(s.manifest_path)}
            for s in items
        ],
        "count": len(items),
    }


def _list_skills(agent: AutonomousAgent, domain: str | None = None) -> dict[str, Any]:
    """Built-in / entry-point business skills (in-process)."""
    from praxia.skills import SKILLS

    out = []
    for name, cls in SKILLS.items():
        manifest = getattr(cls, "manifest", None)
        if domain and manifest and manifest.domain != domain:
            continue
        out.append(
            {
                "name": name,
                "domain": getattr(manifest, "domain", "general"),
                "description": getattr(manifest, "description", ""),
            }
        )
    return {"skills": out, "count": len(out)}


def _run_skill(agent: AutonomousAgent, name: str, input: str) -> dict[str, Any]:
    from praxia.skills import SKILLS

    if not SKILLS.has(name):
        return {"ok": False, "error": f"skill not registered: {name!r}"}
    cls = SKILLS.get(name)
    try:
        skill = cls(llm=agent.llm)
        out = skill.run(input)
    except Exception as exc:  # pragma: no cover - defensive
        agent._audit("skill.run", f"skill:{name}", outcome="error", metadata={"error": str(exc)[:200]})
        return {"ok": False, "error": str(exc)[:500]}
    agent._audit("skill.run", f"skill:{name}", outcome="success")
    return {"ok": True, "output": out}


def _list_connectors(agent: AutonomousAgent) -> dict[str, Any]:
    from praxia.connectors import CONNECTORS  # type: ignore[attr-defined]

    return {"connectors": CONNECTORS.list()}


def _pull_from_connector(
    agent: AutonomousAgent, name: str, path: str, limit: int = 20
) -> dict[str, Any]:
    from praxia.connectors import get_connector

    resource_id = f"{name}:{path}"
    auth = agent.auth
    if auth is not None:
        try:
            auth.policies.require(
                user_id=agent.user_id,
                role=agent.role,
                resource_type="connector",
                resource_id=resource_id,
                action="read",
            )
        except PermissionError as exc:
            agent._audit(
                "connector.pull",
                resource_id,
                outcome="denied",
                metadata={"reason": str(exc)[:200]},
            )
            return {"ok": False, "error": "access denied"}

    config = (agent.connector_configs or {}).get(name, {})
    try:
        conn = get_connector(name, **config)
        items = conn.pull(path, limit=int(limit))
    except Exception as exc:
        agent._audit(
            "connector.pull",
            resource_id,
            outcome="error",
            metadata={"error": str(exc)[:200]},
        )
        return {"ok": False, "error": str(exc)[:500]}

    agent._audit("connector.pull", resource_id, metadata={"count": str(len(items))})
    summary = []
    for it in items[:limit]:
        body = getattr(it, "content", b"")
        if isinstance(body, (bytes, bytearray)):
            try:
                snippet = body[:400].decode("utf-8", errors="replace")
            except Exception:
                snippet = ""
        else:
            snippet = str(body)[:400]
        summary.append(
            {
                "id": getattr(it, "id", ""),
                "name": getattr(it, "name", ""),
                "preview": snippet,
                "metadata": getattr(it, "metadata", {}),
            }
        )
    return {"ok": True, "count": len(items), "items": summary}


def _search_org_memory(agent: AutonomousAgent, query: str, limit: int = 5) -> dict[str, Any]:
    from praxia.memory.shared import SharedMemory

    sm = SharedMemory(
        org_id=agent.org_id,
        storage_dir=Path(agent.memory_dir) / "shared",
    )
    hits = sm.search(query=query, limit=int(limit))
    return {"hits": hits, "count": len(hits)}


def _search_frozen_layer(agent: AutonomousAgent, query: str, limit: int = 5) -> dict[str, Any]:
    """Substring-search the frozen markdown store (Layer 4).

    No frontmatter dependency: walks `.praxia/frozen/**.md` directly so it
    works even when `python-frontmatter` isn't installed.
    """
    root = Path(agent.memory_dir) / "frozen"
    if not root.exists():
        return {"hits": [], "count": 0}
    terms = [t.lower() for t in query.split() if len(t) >= 2]
    hits: list[dict[str, Any]] = []
    for path in root.rglob("*.md"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        haystack = text.lower()
        score = sum(1 for t in terms if t in haystack)
        if not score:
            continue
        hits.append(
            {
                "path": str(path.relative_to(root)),
                "score": score,
                "preview": text[:400],
            }
        )
    hits.sort(key=lambda h: h["score"], reverse=True)
    return {"hits": hits[: int(limit)], "count": len(hits)}


def _search_documents(
    agent: AutonomousAgent,
    query: str,
    limit: int = 5,
    path_prefix: str | None = None,
    folder_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Search local-document chunks the user ingested via the desktop
    app's Documents tab.

    These are files the user dropped onto a Praxia folder — PDFs,
    Word docs, code, etc. — pre-parsed into searchable chunks and
    scoped to the user (no cross-user leakage). Distinct from the
    L1/L3/L4 memory layers in that the content is *the user's own
    files*, not promoted memory blocks or frozen org knowledge.

    Args:
        query: free-text query.
        limit: max hits returned.
        path_prefix: when the user asks about "the files under
            contracts/2024", pass ``"contracts/2024"`` here to narrow
            the search to that subtree. Matched against
            ``relative_path`` inside each registered folder.
        folder_ids: when set, restrict to these specific Documents
            folders. Use ``list_document_folders`` first if you need
            to choose by folder title.

    Returns up to ``limit`` hits, each with ``text``, ``relative_path``,
    ``doc_id``, ``folder_id``, and ``score``.
    """
    try:
        from praxia.server.routers.documents import search_for_user
    except ImportError:
        return {"hits": [], "count": 0, "note": "praxia[server] not installed"}
    try:
        hits = search_for_user(
            Path(agent.memory_dir),
            agent.user_id,
            query,
            limit=int(limit),
            folder_ids=folder_ids,
            path_prefix=path_prefix,
        ) or []
    except Exception:  # pragma: no cover
        return {"hits": [], "count": 0}
    return {"hits": list(hits), "count": len(hits)}


def _list_document_folders(agent: AutonomousAgent) -> dict[str, Any]:
    """List the user's registered Documents folders (id + title +
    path + doc_count).

    Useful when the user names a folder and the agent needs to find
    its ``folder_id`` to pass to ``search_documents``.
    """
    try:
        from praxia.server.routers.documents import load_user_folders
    except ImportError:
        return {"folders": [], "note": "praxia[server] not installed"}
    try:
        folders = load_user_folders(Path(agent.memory_dir), agent.user_id) or []
    except Exception:  # pragma: no cover
        return {"folders": []}
    return {
        "folders": [
            {
                "id": f.id,
                "title": f.title,
                "path": f.path,
                "doc_count": f.doc_count,
                "enabled": f.enabled,
            }
            for f in folders
        ],
        "count": len(folders),
    }


def _final_answer(agent: AutonomousAgent, answer: str) -> dict[str, Any]:
    """Sentinel tool — its presence in the loop signals "done, here is my answer"."""
    return {"answer": answer}


# --- Registration ------------------------------------------------------------


def builtin_tools() -> dict[str, AgentTool]:
    """All tools shipped with `praxia.agent`."""
    tools = [
        AgentTool(
            name="search_personal_memory",
            description=(
                "Search the user's personal memory (Layer 1). Use this FIRST "
                "when the user asks about prior decisions, preferences, or any "
                "context that may have been recorded in earlier conversations."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "free-text query"},
                    "limit": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20},
                },
                "required": ["query"],
            },
            handler=_search_personal_memory,
        ),
        AgentTool(
            name="search_org_memory",
            description=(
                "Search organizational shared memory (Layer 3 — promoted blocks "
                "of team-wide knowledge). Use after personal memory when the "
                "question seems org-relevant (policies, conventions, contacts)."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20},
                },
                "required": ["query"],
            },
            handler=_search_org_memory,
        ),
        AgentTool(
            name="search_frozen_layer",
            description=(
                "Search the frozen markdown store (Layer 4 — version-controlled "
                "instructions and playbooks). Use for stable policy/procedural "
                "content that has been formally curated."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20},
                },
                "required": ["query"],
            },
            handler=_search_frozen_layer,
        ),
        AgentTool(
            name="list_skills",
            description=(
                "List built-in / entry-point business skills available in this "
                "process (e.g. investment_analyst, sales_assistant). Optionally "
                "filter by `domain`."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "optional domain filter"},
                },
            },
            handler=_list_skills,
        ),
        AgentTool(
            name="list_personal_skills",
            description="List skills the user has personally registered.",
            parameters_schema={"type": "object", "properties": {}},
            handler=_list_personal_skills,
        ),
        AgentTool(
            name="list_org_skills",
            description=(
                "List the user's effective skill catalog (org + distributed + "
                "personal — personal overrides distributed overrides org)."
            ),
            parameters_schema={"type": "object", "properties": {}},
            handler=_list_org_skills,
        ),
        AgentTool(
            name="run_skill",
            description=(
                "Invoke a registered skill by name. Use after `list_skills` to "
                "pick one. Returns the skill's textual output."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "input": {"type": "string", "description": "user input passed to the skill"},
                },
                "required": ["name", "input"],
            },
            handler=_run_skill,
        ),
        AgentTool(
            name="list_connectors",
            description="List connector names available in this deployment.",
            parameters_schema={"type": "object", "properties": {}},
            handler=_list_connectors,
        ),
        AgentTool(
            name="pull_from_connector",
            description=(
                "Pull data from an external connector (Box / SharePoint / "
                "kintone / Salesforce / ...). ACL-checked and audited. Use only "
                "when memory and frozen layers don't have what you need."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "connector name"},
                    "path": {"type": "string", "description": "connector-specific path"},
                    "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100},
                },
                "required": ["name", "path"],
            },
            handler=_pull_from_connector,
        ),
        AgentTool(
            name="record_fact",
            description=(
                "Record a durable fact into the user's personal memory. Use "
                "sparingly — only for stable facts the user has explicitly "
                "stated. No-op when memory is in read_only mode."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                },
                "required": ["text"],
            },
            handler=_record_fact,
        ),
        AgentTool(
            name="search_documents",
            description=(
                "Search the user's ingested LOCAL DOCUMENTS — the files "
                "they dropped onto the Praxia desktop app's Documents "
                "tab (PDFs, Word docs, code, manuals…). Use this when "
                "the user's question is about content they own / "
                "imported, NOT the agent's memory layers. Often the "
                "right first call for 'what does my contract say about "
                "X' / 'find the section in those PDFs about Y'. "
                "Use `path_prefix` to narrow to a subfolder (e.g. "
                "`contracts/2024`) — the user's directory structure is "
                "preserved in `relative_path` on every hit."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20},
                    "path_prefix": {
                        "type": "string",
                        "description": (
                            "Restrict to documents whose relative_path "
                            "starts with this prefix. e.g. 'contracts/2024'."
                        ),
                    },
                    "folder_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Restrict to specific Documents folder ids. "
                            "Call list_document_folders first to find ids."
                        ),
                    },
                },
                "required": ["query"],
            },
            handler=_search_documents,
        ),
        AgentTool(
            name="list_document_folders",
            description=(
                "List the user's registered Documents folders (id, "
                "title, path, doc_count). Use this when the user "
                "names a folder ('search the contracts folder') and "
                "you need to find the matching folder_id to pass to "
                "search_documents."
            ),
            parameters_schema={
                "type": "object",
                "properties": {},
            },
            handler=_list_document_folders,
        ),
        AgentTool(
            name="final_answer",
            description=(
                "Return the final answer to the user. Call this when you have "
                "enough information — the loop terminates immediately and "
                "`answer` is shown verbatim to the user."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "answer": {"type": "string"},
                },
                "required": ["answer"],
            },
            handler=_final_answer,
        ),
    ]
    return {t.name: t for t in tools}


def serialize_tool_result(value: Any) -> str:
    """Return a model-readable string for arbitrary tool results."""
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(value)
