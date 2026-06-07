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


def _lift_llm_args_from_agent(agent: "AutonomousAgent") -> dict[str, Any]:
    """Pull LLM-related fields off the parent agent so child TaskRecords
    can re-instantiate the same configuration.

    Why this exists: when run_parallel_tasks or schedule_recurring_task
    spawn child Tasks, the worker (_invoke_agent in tasks.py) defaults
    to ``model="claude"`` if args has none. That alias resolves to
    Anthropic and dies with ``Missing ANTHROPIC_API_KEY`` for any user
    running OpenAI / Azure / Gemini / Ollama. This helper looks up the
    parent's actual model + scout + workspace + org and emits a dict
    safe to merge into child args.

    Only concrete strings are forwarded — MagicMocks in tests (and
    similarly any None / int / dict from a misconfigured agent) are
    skipped so child args remain JSON-serialisable.
    """
    out: dict[str, Any] = {}
    parent_llm = getattr(agent, "llm", None)
    parent_cfg = getattr(parent_llm, "config", None)
    parent_model = getattr(parent_cfg, "model", None) if parent_cfg else None
    if isinstance(parent_model, str) and parent_model:
        out["model"] = parent_model
    scout = getattr(agent, "_scout_model", None)
    if isinstance(scout, str) and scout:
        out["scout_model"] = scout
    workspace = getattr(agent, "_workspace_root", None)
    if isinstance(workspace, str) and workspace:
        out["workspace_root"] = workspace
    org = getattr(agent, "org_id", None)
    if isinstance(org, str) and org and org != "default-org":
        out["org_id"] = org
    return out


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


def _list_files_in_folder(
    agent: AutonomousAgent,
    folder_id: str | None = None,
    folder_title: str | None = None,
    path_prefix: str | None = None,
) -> dict[str, Any]:
    """Enumerate every file inside a Documents folder. The agent calls
    this before ``run_parallel_tasks`` so it knows what items to fan
    out over: each child gets one file's ``relative_path``.

    Pass exactly one of ``folder_id`` or ``folder_title``. When the
    user said "fan out across the contracts folder" the LLM should
    first call this tool (folder_title="contracts"), then build one
    prompt per file in the returned list.

    Returns one entry per registered doc with ``relative_path``,
    ``doc_id``, ``folder_id``, ``size_bytes`` (best effort, may be 0
    for legacy docs), ``chunk_count``, and ``extension``.
    """
    try:
        from praxia.server.routers.documents import (
            load_docs_in_folder, load_user_folders,
        )
    except ImportError:
        return {"files": [], "count": 0, "note": "praxia[server] not installed"}

    try:
        folders = load_user_folders(Path(agent.memory_dir), agent.user_id) or []
    except Exception:  # pragma: no cover
        return {"files": [], "count": 0}

    # Resolve the target folder. folder_id wins; otherwise match by
    # title (case-insensitive). Errors are returned as a `note` rather
    # than raising — the LLM can recover by listing folders first.
    target = None
    if folder_id:
        target = next((f for f in folders if f.id == folder_id), None)
    elif folder_title:
        wanted = folder_title.strip().lower()
        target = next((f for f in folders if (f.title or "").lower() == wanted), None)
    if target is None:
        return {
            "files": [],
            "count": 0,
            "note": (
                f"No folder matched folder_id={folder_id!r} "
                f"folder_title={folder_title!r}. Call "
                "list_document_folders to see what exists."
            ),
        }

    try:
        docs = load_docs_in_folder(
            Path(agent.memory_dir), agent.user_id, target.id,
        ) or []
    except Exception:  # pragma: no cover
        return {"files": [], "count": 0, "folder_id": target.id}

    norm_prefix = None
    if path_prefix:
        norm_prefix = path_prefix.replace("\\", "/").strip("/")

    out = []
    for doc in docs:
        rel = doc.relative_path.replace("\\", "/")
        if norm_prefix is not None and not (
            rel == norm_prefix or rel.startswith(norm_prefix + "/")
        ):
            continue
        # Extension extraction without pulling pathlib for every doc.
        dot = rel.rfind(".")
        ext = rel[dot + 1:].lower() if dot >= 0 and dot < len(rel) - 1 else ""
        out.append({
            "doc_id": doc.id,
            "folder_id": target.id,
            "relative_path": rel,
            "extension": ext,
            "chunk_count": len(doc.chunks or []),
            # `size_bytes` is best-effort — pre-alpha22 docs may not
            # carry it, in which case we report 0.
            "size_bytes": getattr(doc, "size_bytes", 0) or 0,
        })

    return {
        "folder_id": target.id,
        "folder_title": target.title,
        "files": out,
        "count": len(out),
    }


def _schedule_recurring_task(
    agent: AutonomousAgent,
    cron: str,
    prompt: str,
    label: str | None = None,
) -> dict[str, Any]:
    """Create a cron-style recurring schedule that fires the given prompt.

    The agent invokes this tool when the user expresses a recurring
    intent ("every weekday at 9", "毎週月曜", "alle 4 Stunden"). The
    LLM is responsible for translating that intent to a POSIX 5-field
    cron expression — we just validate + persist.

    Writes to the same on-disk store the /schedules router reads from,
    so the schedule shows up in the Schedules tab immediately and is
    picked up by the ticker on its next 60s sweep.
    """
    if not prompt.strip():
        return {"created": False, "error": "prompt is required"}
    if not cron.strip():
        return {"created": False, "error": "cron is required"}
    try:
        from praxia.server.routers.schedules import (
            ScheduleRecord,
            _save as _save_sched,
            next_run,
            parse_cron,
        )
    except ImportError as e:
        return {"created": False, "error": f"schedules module not available: {e}"}
    try:
        parse_cron(cron)
    except ValueError as e:
        return {
            "created": False,
            "error": f"invalid cron {cron!r}: {e}. Expected 5 fields: "
                     f"'minute hour day-of-month month day-of-week' "
                     f"with * / N / ranges / lists / steps. "
                     f"Examples: '0 9 * * 1-5' = weekdays 9am; "
                     f"'*/30 * * * *' = every 30 min; "
                     f"'0 0 1 * *' = first of every month at midnight.",
        }
    import time
    import uuid
    from datetime import datetime
    # alpha22+: propagate the parent's LLM config so every cron firing
    # creates a TaskRecord with the right model. Without this, every
    # schedule fires with the worker's default model='claude' regardless
    # of which provider the user chose, and dies with
    # 'Missing ANTHROPIC_API_KEY' for non-Anthropic users.
    sched_args: dict[str, Any] = {}
    if label:
        sched_args["label"] = label
    sched_args.update(_lift_llm_args_from_agent(agent))
    rec = ScheduleRecord(
        id=uuid.uuid4().hex,
        user_id=str(agent.user_id),
        cron=cron,
        prompt=prompt,
        args=sched_args,
        enabled=True,
        created_at=time.time(),
    )
    nr = next_run(cron, datetime.now())
    rec.next_run_at = nr.timestamp() if nr else None
    _save_sched(Path(agent.memory_dir), rec)
    return {
        "created": True,
        "schedule_id": rec.id,
        "cron": rec.cron,
        "prompt": rec.prompt,
        "next_run_iso": nr.isoformat() if nr else None,
        "note": (
            "The schedule is active. The user can view / pause / delete "
            "it from the Schedules tab. Each firing creates a Task they "
            "can inspect in the Tasks tab."
        ),
    }


def _run_parallel_tasks(
    agent: AutonomousAgent,
    prompts: list[str],
    label: str | None = None,
    max_concurrency: int = 4,
) -> dict[str, Any]:
    """Fan out N agent runs in parallel, one per prompt.

    The agent invokes this when the user has a list of items that all
    need the same treatment ("for each of these 5 files, summarise…",
    "これらの 10 件のチケットを分類して"). Each child is a normal
    background Task — visible in /tasks, cancellable per-item — bundled
    under a single Batch id for composite progress.

    The handler is intentionally synchronous-from-the-agent's-view: it
    queues the work + returns immediately. The child tasks run in
    daemon threads. The user polls the Batches tab.
    """
    if not prompts:
        return {"created": False, "error": "prompts must be a non-empty list"}
    filtered = [p for p in prompts if isinstance(p, str) and p.strip()]
    if not filtered:
        return {"created": False, "error": "no non-empty prompts after filtering"}
    if len(filtered) > 100:
        return {
            "created": False,
            "error": f"too many prompts ({len(filtered)}); cap is 100",
        }
    try:
        from praxia.server.routers.batch import (
            BatchRecord,
            _run_batch,
            _save as _save_batch,
        )
        from praxia.server.routers.tasks import TaskRecord, _save as _save_task
    except ImportError as e:
        return {"created": False, "error": f"batch module not available: {e}"}
    import time
    import uuid
    now = time.time()
    batch_id = uuid.uuid4().hex
    user_id = str(agent.user_id)
    children: list[TaskRecord] = []
    storage = Path(agent.memory_dir)
    # Propagate the parent agent's LLM configuration into each child
    # task's args. Without this the worker's _invoke_agent defaults to
    # ``model="claude"`` (alias → anthropic/claude-opus-4-7), which
    # breaks every batch for users running OpenAI / Azure / Gemini /
    # Ollama — they don't have ANTHROPIC_API_KEY in their env and the
    # litellm.completion call dies with "Missing Anthropic API Key".
    # Pull the *unresolved* model string (alias before resolve_model)
    # so the worker rebuilds the exact same LLM instance.
    base_args: dict[str, Any] = {"_batch_id": batch_id}
    base_args.update(_lift_llm_args_from_agent(agent))
    for p in filtered:
        t = TaskRecord(
            id=uuid.uuid4().hex,
            user_id=user_id,
            kind="agent_run",
            args={"prompt": p, **base_args},
            created_at=now,
        )
        _save_task(storage, t)
        children.append(t)
    batch = BatchRecord(
        id=batch_id,
        user_id=user_id,
        task_ids=[t.id for t in children],
        created_at=now,
        label=label,
    )
    _save_batch(storage, batch)
    # We need a "user-like" object for _run_agent_task_threaded. The
    # agent only carries user_id + role; build a tiny stand-in matching
    # the shape that the worker expects (just .id + .role attributes).
    class _AgentUser:
        def __init__(self, uid: str, role: str) -> None:
            self.id = uid
            self.role = role
    user_obj = _AgentUser(user_id, getattr(agent, "role", "member"))
    _run_batch(storage, user_obj, children, int(max_concurrency))
    return {
        "created": True,
        "batch_id": batch_id,
        "task_count": len(children),
        "task_ids": [t.id for t in children],
        "note": (
            "The batch is running in the background. The user can view "
            "live progress + per-item results in the Batches tab. Each "
            "child is also visible in the Tasks tab."
        ),
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
            name="list_files_in_folder",
            description=(
                "Enumerate every file the user has indexed inside ONE "
                "Documents folder. This is the right first call for any "
                "per-file batch fan-out ('summarise each PDF in folder X', "
                "'extract action items from every doc in pdfs'): list the "
                "files here, then build one self-contained prompt per "
                "file and hand them all to run_parallel_tasks. Pass "
                "EITHER folder_id (preferred, from list_document_folders) "
                "OR folder_title (case-insensitive match by user-visible "
                "name). Returns one entry per file with relative_path "
                "(use this in the per-file prompt so each child knows "
                "which doc to work on), doc_id, extension, and "
                "chunk_count."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "folder_id": {
                        "type": "string",
                        "description": (
                            "Documents folder id (from list_document_"
                            "folders). Preferred over folder_title."
                        ),
                    },
                    "folder_title": {
                        "type": "string",
                        "description": (
                            "User-visible folder name. Matched case-"
                            "insensitively. Use when the user named the "
                            "folder verbally."
                        ),
                    },
                    "path_prefix": {
                        "type": "string",
                        "description": (
                            "Optional subpath filter (e.g. '2024/Q1') — "
                            "only returns files whose relative_path "
                            "starts with this prefix."
                        ),
                    },
                },
            },
            handler=_list_files_in_folder,
        ),
        AgentTool(
            name="schedule_recurring_task",
            description=(
                "Create a recurring scheduled agent run. Call this when "
                "the user expresses a RECURRING intent: 'every weekday at "
                "9am, summarise yesterday's docs', '毎週月曜の朝にニュー"
                "ス要約を', 'jeden Montag um 8 Uhr'. NOT for one-shot "
                "requests ('do X now') — those are handled directly. "
                "You are responsible for translating the user's natural-"
                "language schedule into a POSIX 5-field cron expression "
                "(minute hour day-of-month month day-of-week). Examples: "
                "'0 9 * * 1-5' = weekdays 9am · '*/30 * * * *' = every "
                "30 min · '0 8 * * 1' = Mondays 8am · '0 0 1 * *' = first "
                "of every month at midnight. After successful creation, "
                "tell the user when the next run will fire and remind "
                "them they can manage it from the Schedules tab."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "cron": {
                        "type": "string",
                        "description": (
                            "POSIX 5-field cron expression. Required."
                        ),
                    },
                    "prompt": {
                        "type": "string",
                        "description": (
                            "The prompt to run on each firing. Make it "
                            "self-contained — the LLM will see this with "
                            "no surrounding conversation context."
                        ),
                    },
                    "label": {
                        "type": "string",
                        "description": (
                            "Optional short label for the user-facing "
                            "Schedules list."
                        ),
                    },
                },
                "required": ["cron", "prompt"],
            },
            handler=_schedule_recurring_task,
        ),
        AgentTool(
            name="run_parallel_tasks",
            description=(
                "Fan out N agent runs in parallel, one per prompt. Call "
                "this WHENEVER the user wants the SAME treatment applied "
                "to multiple items in their Documents folder or to an "
                "enumerable list. Trigger phrases include but are not "
                "limited to: 'each of these N files', 'all of the PDFs', "
                "'for every document in', 'classify these N tickets', "
                "'これらの N 件をそれぞれ要約して', 'Documents の全 PDF "
                "から〇〇を抽出して', '全件', 'すべての ファイルから', "
                "'各 PDF から', '一つずつ', 'jede dieser N Dateien', "
                "'tous ces PDF'. If the user mentions 'all' / '全件' / "
                "'全部' / '各' / 'every' / 'each' together with a folder "
                "or a doc-type plural, this is your tool. Workflow: "
                "(1) call list_document_folders to find the folder_id, "
                "(2) call list_files_in_folder(folder_id=...) to get "
                "the actual file list (NOT search_documents — that "
                "returns chunks not files), (3) call this tool with one "
                "self-contained prompt per file mentioning the file's "
                "relative_path explicitly so each child agent knows "
                "which doc to work on. NOT for a single complex request and "
                "NOT for recurring work (use schedule_recurring_task). "
                "Returns a batch_id the user tracks in the Batches tab. "
                "Hard cap of 100 items per call. After success, tell "
                "the user the count and point to the Batches tab."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "prompts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "One prompt per item the user wants processed. "
                            "Each prompt must be self-contained — the LLM "
                            "running each child sees only that prompt."
                        ),
                    },
                    "label": {
                        "type": "string",
                        "description": (
                            "Optional short label for the user-facing "
                            "Batches list."
                        ),
                    },
                    "max_concurrency": {
                        "type": "integer",
                        "default": 4,
                        "minimum": 1,
                        "maximum": 16,
                        "description": (
                            "How many children to run at once. Default 4 "
                            "is friendly to provider rate-limits."
                        ),
                    },
                },
                "required": ["prompts"],
            },
            handler=_run_parallel_tasks,
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
