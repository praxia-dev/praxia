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
            # alpha27+: pass the parent agent's LLM so the no-embedding
            # fallback path can expand the query (synonyms + cross-
            # language) instead of degrading to pure keyword.
            llm=getattr(agent, "llm", None),
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


def _web_search(
    agent: AutonomousAgent,
    query: str,
    max_results: int = 5,
) -> dict[str, Any]:
    """Search the open web via the configured provider.

    Praxia ships no web index — the agent uses this tool when the
    user asks about current events, breaking news, prices, or
    anything else outside the local Documents / memory layers.
    Returns up to ``max_results`` results with title + url + snippet,
    plus (for Tavily) a one-paragraph synthesised answer.

    Errors are returned as a structured ``error`` field rather than
    raised so the LLM can relay them to the user (most common: no
    provider key configured).
    """
    try:
        from praxia.agent.web_search import search, is_available
    except ImportError as e:
        return {"results": [], "count": 0, "error": f"web_search module not available: {e}"}
    if not is_available():
        return {
            "results": [],
            "count": 0,
            "error": (
                "No web search provider configured. Tell the user to "
                "add TAVILY_API_KEY (https://tavily.com) or "
                "BRAVE_SEARCH_API_KEY (https://brave.com/search/api/) "
                "in Settings → Choose your provider → Advanced."
            ),
        }
    try:
        return search(query, max_results=int(max_results))
    except Exception as e:  # pragma: no cover
        return {"results": [], "count": 0, "error": str(e)}


_VALID_SORTS = {"name", "mtime_desc", "mtime_asc", "size_desc", "size_asc"}


def _doc_mtime(doc) -> float:
    """Best-effort modification time for a Document.

    The router stores ``mtime`` (file's mtime at ingest) and
    ``indexed_at`` (when Praxia processed it). For "what's the latest
    doc?" queries the file's own mtime is the right answer; we fall
    back to indexed_at when mtime is missing or zero (some pre-alpha22
    docs).
    """
    mt = getattr(doc, "mtime", 0.0) or 0.0
    if mt <= 0.0:
        mt = getattr(doc, "indexed_at", 0.0) or 0.0
    return float(mt)


def _list_files_in_folder(
    agent: AutonomousAgent,
    folder_id: str | None = None,
    folder_title: str | None = None,
    path_prefix: str | None = None,
    sort_by: str = "name",
    limit: int | None = None,
) -> dict[str, Any]:
    """Enumerate files in the user's Documents.

    alpha22+ added this to support ``run_parallel_tasks`` (fan-out per
    file). alpha28+ generalises it: pass ``folder_id=None`` AND
    ``folder_title=None`` to enumerate across EVERY enabled folder,
    and use ``sort_by="mtime_desc"`` + ``limit=N`` for "find the
    latest N documents" queries — which is the right path when the
    user asks for "the most recent proposal" / "latest update" /
    "新しい順" and content-keyword search isn't a match.

    Each entry now also reports ``mtime`` (Unix seconds) and
    ``mtime_iso`` (ISO-8601 in UTC), so the LLM can reason about
    recency without a separate metadata fetch.

    Returns ``files: [{doc_id, folder_id, folder_title,
    relative_path, extension, chunk_count, size_bytes, mtime,
    mtime_iso}, ...]`` plus ``count`` and (when scoped) ``folder_id``
    / ``folder_title``.
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

    sort_key = sort_by if sort_by in _VALID_SORTS else "name"

    # Resolve target folder(s).
    # - folder_id given → that single folder
    # - folder_title given → case-insensitive match on title
    # - neither given → ALL enabled folders (alpha28+ new mode)
    targets: list = []
    if folder_id:
        match = next((f for f in folders if f.id == folder_id), None)
        if match is None:
            return {
                "files": [], "count": 0,
                "note": (
                    f"No folder matched folder_id={folder_id!r}. "
                    "Call list_document_folders to see what exists."
                ),
            }
        targets = [match]
    elif folder_title:
        wanted = folder_title.strip().lower()
        match = next((f for f in folders if (f.title or "").lower() == wanted), None)
        if match is None:
            return {
                "files": [], "count": 0,
                "note": (
                    f"No folder matched folder_title={folder_title!r}. "
                    "Call list_document_folders to see what exists."
                ),
            }
        targets = [match]
    else:
        # Across-all-folders mode. Filter to enabled so we don't
        # leak files the user has explicitly disabled.
        targets = [f for f in folders if getattr(f, "enabled", True)]

    if not targets:
        return {"files": [], "count": 0, "note": "No enabled folders to scan."}

    norm_prefix = None
    if path_prefix:
        norm_prefix = path_prefix.replace("\\", "/").strip("/")

    out: list[dict[str, Any]] = []
    storage_path = Path(agent.memory_dir)
    for target in targets:
        try:
            docs = load_docs_in_folder(storage_path, agent.user_id, target.id) or []
        except Exception:  # pragma: no cover
            continue
        for doc in docs:
            rel = doc.relative_path.replace("\\", "/")
            if norm_prefix is not None and not (
                rel == norm_prefix or rel.startswith(norm_prefix + "/")
            ):
                continue
            # Extension without instantiating a pathlib object per doc.
            dot = rel.rfind(".")
            ext = rel[dot + 1:].lower() if dot >= 0 and dot < len(rel) - 1 else ""
            mt = _doc_mtime(doc)
            # ISO 8601 in UTC, no microseconds — easy for the LLM to
            # paraphrase as a human-readable date.
            from datetime import datetime as _dt, timezone as _tz
            try:
                iso = _dt.fromtimestamp(mt, _tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if mt > 0 else ""
            except (OverflowError, OSError, ValueError):
                iso = ""
            out.append({
                "doc_id": doc.id,
                "folder_id": target.id,
                "folder_title": target.title,
                "relative_path": rel,
                "extension": ext,
                "chunk_count": len(doc.chunks or []),
                "size_bytes": getattr(doc, "size", 0) or 0,
                "mtime": mt,
                "mtime_iso": iso,
            })

    # Sort. "name" is the default backwards-compatible behaviour.
    if sort_key == "mtime_desc":
        out.sort(key=lambda r: r["mtime"], reverse=True)
    elif sort_key == "mtime_asc":
        out.sort(key=lambda r: r["mtime"])
    elif sort_key == "size_desc":
        out.sort(key=lambda r: r["size_bytes"], reverse=True)
    elif sort_key == "size_asc":
        out.sort(key=lambda r: r["size_bytes"])
    else:
        out.sort(key=lambda r: r["relative_path"].lower())

    if limit is not None and limit > 0:
        out = out[: int(limit)]

    result: dict[str, Any] = {
        "files": out,
        "count": len(out),
        "sort_by": sort_key,
        "scope": (
            "single_folder"
            if (folder_id or folder_title)
            else "all_enabled_folders"
        ),
    }
    # Surface the resolved folder id/title only when we narrowed to one.
    if len(targets) == 1:
        result["folder_id"] = targets[0].id
        result["folder_title"] = targets[0].title
    return result


def _read_document(
    agent: AutonomousAgent,
    doc_id: str | None = None,
    relative_path: str | None = None,
    folder_id: str | None = None,
    folder_title: str | None = None,
    max_chars: int = 20000,
) -> dict[str, Any]:
    """Return the full text of one Document.

    Pair with ``list_files_in_folder`` for "find and read" flows:
    list files (e.g. ``sort_by="mtime_desc", limit=1`` for "the latest
    one"), then call this with the returned ``doc_id`` to read the
    content. The content is the concatenation of every chunk in the
    document, truncated to ``max_chars`` (default 20 000) — the LLM
    can ask for more by raising the limit, but most use cases fit.

    Resolution precedence: ``doc_id`` > (``folder_id`` |
    ``folder_title``) + ``relative_path``. If only ``relative_path``
    is given without a folder, we scan every enabled folder for a
    match — convenient when the LLM kept the path string from a
    prior ``list_files_in_folder`` reply but lost the folder_id.
    """
    try:
        from praxia.server.routers.documents import (
            load_docs_in_folder, load_user_folders,
        )
    except ImportError:
        return {"text": "", "found": False, "note": "praxia[server] not installed"}

    try:
        folders = load_user_folders(Path(agent.memory_dir), agent.user_id) or []
    except Exception:  # pragma: no cover
        return {"text": "", "found": False}

    # Narrow the folder pool early.
    if folder_id:
        folders = [f for f in folders if f.id == folder_id]
    elif folder_title:
        wanted = folder_title.strip().lower()
        folders = [f for f in folders if (f.title or "").lower() == wanted]
    else:
        folders = [f for f in folders if getattr(f, "enabled", True)]

    target_doc = None
    target_folder = None
    storage = Path(agent.memory_dir)
    norm_path = relative_path.replace("\\", "/").strip("/") if relative_path else None
    for f in folders:
        try:
            docs = load_docs_in_folder(storage, agent.user_id, f.id) or []
        except Exception:
            continue
        for d in docs:
            if doc_id and d.id == doc_id:
                target_doc, target_folder = d, f
                break
            if norm_path and d.relative_path.replace("\\", "/").strip("/") == norm_path:
                target_doc, target_folder = d, f
                break
        if target_doc is not None:
            break

    if target_doc is None:
        return {
            "text": "",
            "found": False,
            "note": (
                f"No document matched doc_id={doc_id!r} "
                f"relative_path={relative_path!r}. "
                "Call list_files_in_folder to confirm what exists."
            ),
        }

    # Concatenate chunks in index order. We use newlines as the
    # separator — chunk boundaries are an indexing artifact, not a
    # semantic one, and most parsers already include trailing blank
    # lines, so single \n keeps the text close to the original layout.
    parts = sorted(target_doc.chunks or [], key=lambda c: c.index)
    full = "\n".join(c.text for c in parts)

    cap = max(500, min(int(max_chars), 200_000))
    truncated = False
    if len(full) > cap:
        full = full[:cap]
        truncated = True

    mt = _doc_mtime(target_doc)
    from datetime import datetime as _dt, timezone as _tz
    try:
        iso = _dt.fromtimestamp(mt, _tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if mt > 0 else ""
    except (OverflowError, OSError, ValueError):
        iso = ""

    return {
        "found": True,
        "doc_id": target_doc.id,
        "folder_id": target_folder.id,
        "folder_title": target_folder.title,
        "relative_path": target_doc.relative_path,
        "extension": (
            target_doc.relative_path.rsplit(".", 1)[1].lower()
            if "." in target_doc.relative_path else ""
        ),
        "size_bytes": getattr(target_doc, "size", 0) or 0,
        "mtime": mt,
        "mtime_iso": iso,
        "chunk_count": len(parts),
        "char_count": len(full),
        "truncated": truncated,
        "text": full,
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
    # alpha23+: synthesise a friendlier auto-label when the LLM didn't
    # pass one. Without this the Batches sidebar showed the bare UUID
    # fragment (e.g. "a3f9c2b1") which reads as random English hex to
    # JA / ZH / KO users. Take the first prompt's first 40 chars as a
    # quick description — good enough for skim-reading the recent list.
    effective_label = label
    if not effective_label and filtered:
        first_line = filtered[0].splitlines()[0].strip()
        if first_line:
            effective_label = first_line[:40] + ("…" if len(first_line) > 40 else "")
    batch = BatchRecord(
        id=batch_id,
        user_id=user_id,
        task_ids=[t.id for t in children],
        created_at=now,
        label=effective_label,
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
                "**Content** search over the user's ingested LOCAL "
                "DOCUMENTS — the files they dropped onto the Praxia "
                "desktop app's Documents tab (PDFs, Word docs, code, "
                "manuals…). Use this when the user's question is "
                "about content they own / imported, NOT the agent's "
                "memory layers. Often the right first call for 'what "
                "does my contract say about X' / 'find the section "
                "in those PDFs about Y'. "
                "Use `path_prefix` to narrow to a subfolder (e.g. "
                "`contracts/2024`) — the user's directory structure "
                "is preserved in `relative_path` on every hit.\n"
                "\n"
                "**When this returns 0 hits**, the right next step is "
                "almost always `list_files_in_folder` — the user may "
                "have asked about a doc by its METADATA (date, name, "
                "size) rather than its contents. For example "
                "'最新の提案を見せて' / 'show me the latest proposal' "
                "is a recency query, not a content query: call "
                "list_files_in_folder(sort_by='mtime_desc', limit=1) "
                "then read_document on the result."
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
            name="web_search",
            description=(
                "Search the open web for current information. Praxia "
                "has no web index of its own — use this tool whenever "
                "the user asks about: breaking news, today's events, "
                "current prices / stock quotes / exchange rates, "
                "recent regulatory or policy changes, anything time-"
                "sensitive that wouldn't be in their Documents or "
                "memory layers. Returns a list of {title, url, snippet} "
                "results plus (for Tavily) a one-paragraph synthesised "
                "answer. NOT a substitute for search_documents (which "
                "is for the user's own ingested files) or "
                "search_personal_memory (which is for things the user "
                "told you previously). Caveat: requires the user to "
                "have a Tavily or Brave Search API key configured; if "
                "the tool returns an `error` field, relay it verbatim "
                "so the user knows what to add in Settings."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Free-text search query. Phrase it as a "
                            "self-contained question or noun phrase — "
                            "the LLM will write it, the search engine "
                            "consumes it. e.g. 'OpenAI o4 release "
                            "date', 'USD to JPY today', 'EU AI Act "
                            "Article 5 deadline 2026'."
                        ),
                    },
                    "max_results": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10,
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
            handler=_web_search,
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
                "Enumerate files in the user's Documents folders, with "
                "sort + filter + recency metadata. Two use cases:\n"
                "\n"
                "  (1) **Per-file batch fan-out** — 'summarise each PDF "
                "in folder X', 'extract action items from every doc'. "
                "List, then build one prompt per file and hand to "
                "run_parallel_tasks.\n"
                "\n"
                "  (2) **Find by recency / size** — '最新の提案を出して' "
                "/ 'the most recently updated contract' / 'biggest file "
                "in here'. Pass sort_by='mtime_desc' + limit=1 (or N) "
                "and the newest file(s) come back with mtime + "
                "mtime_iso filled in. Use **this** path when content-"
                "keyword search via search_documents returns nothing "
                "or the user asked about a *specific document by "
                "metadata* (date / size / name) rather than its "
                "contents.\n"
                "\n"
                "Folder selection: pass folder_id (from "
                "list_document_folders) OR folder_title (case-"
                "insensitive). Pass NEITHER to scan EVERY enabled "
                "folder — useful when the user said 'in Documents' "
                "without naming a folder. Each entry carries doc_id, "
                "folder_id, folder_title, relative_path, extension, "
                "chunk_count, size_bytes, mtime (Unix sec), and "
                "mtime_iso (ISO-8601 UTC string). Use the doc_id with "
                "read_document to fetch full content."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "folder_id": {
                        "type": "string",
                        "description": (
                            "Documents folder id (from list_document_"
                            "folders). Preferred over folder_title. "
                            "Omit (with folder_title also omitted) to "
                            "scan every enabled folder."
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
                    "sort_by": {
                        "type": "string",
                        "enum": [
                            "name", "mtime_desc", "mtime_asc",
                            "size_desc", "size_asc",
                        ],
                        "default": "name",
                        "description": (
                            "Sort order. Use 'mtime_desc' for "
                            "'latest/most recent', 'mtime_asc' for "
                            "'oldest', 'size_desc' for 'biggest'. "
                            "Default 'name' is alphabetical by "
                            "relative_path."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "description": (
                            "Cap the result count. Pair with "
                            "sort_by='mtime_desc' + limit=1 for 'the "
                            "single latest file'."
                        ),
                    },
                },
            },
            handler=_list_files_in_folder,
        ),
        AgentTool(
            name="read_document",
            description=(
                "Read the full text of ONE Document by doc_id (or by "
                "relative_path + folder). Pair with "
                "list_files_in_folder for 'find-then-read' flows: "
                "list_files_in_folder(sort_by='mtime_desc', limit=1) "
                "→ read_document(doc_id=…) is the canonical answer to "
                "'tell me what the latest proposal says'. The returned "
                "text is the concatenation of all chunks in order, "
                "capped at max_chars (default 20 000) — raise it for "
                "longer docs. Also returns mtime / mtime_iso / size "
                "so the LLM can cite the document's metadata in its "
                "reply. NOT for grep-style content search — use "
                "search_documents for 'find chunks mentioning X'."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "doc_id": {
                        "type": "string",
                        "description": (
                            "Document id (from list_files_in_folder). "
                            "Preferred resolution path."
                        ),
                    },
                    "relative_path": {
                        "type": "string",
                        "description": (
                            "Document relative_path (forward-slashed). "
                            "Use when only the path is known. Combine "
                            "with folder_id / folder_title to "
                            "disambiguate across folders."
                        ),
                    },
                    "folder_id": {
                        "type": "string",
                        "description": (
                            "Optional folder scope (from "
                            "list_document_folders)."
                        ),
                    },
                    "folder_title": {
                        "type": "string",
                        "description": (
                            "Optional folder scope by user-visible "
                            "name. Case-insensitive."
                        ),
                    },
                    "max_chars": {
                        "type": "integer",
                        "minimum": 500,
                        "maximum": 200000,
                        "default": 20000,
                        "description": (
                            "Truncate the returned text to this many "
                            "characters. Set higher for long PDFs."
                        ),
                    },
                },
            },
            handler=_read_document,
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
