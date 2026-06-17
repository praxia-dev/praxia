"""Autonomous-agent endpoint: POST /agent/run.

Synchronous wrapper around :class:`praxia.agent.AutonomousAgent` and
:class:`praxia.agent.CommandedAgent` so a thin client (desktop / mobile)
can ask the server to "do this task" and get back the final answer + tool
trace without orchestrating Python locally.

This is the data-plane companion to :mod:`praxia.server.routers.threads`:
when a client posts a user message into a thread and wants an agent
reply, it calls this endpoint, then appends the returned text as an
assistant message (or passes ``thread_id`` so the server does both in
one round trip).

Streaming + WebSocket variants land in a later phase.
"""
from __future__ import annotations

import io
import logging
import time
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel

_log = logging.getLogger(__name__)


# Module-level models so FastAPI / Pydantic introspection works cleanly
class AgentRunRequest(BaseModel):
    prompt: str
    thread_id: str | None = None      # if set, append both user msg + reply
    org_id: str = "default-org"
    model: str = "claude"
    # Optional: a smaller / cheaper LLM used for "scout" sub-calls —
    # query decomposition, grounding-verifier claim extraction, task
    # classification. Defaults to `model` (one LLM for everything).
    # Picking a smaller model here saves cost and latency on the
    # exploratory steps without hurting final-answer quality.
    scout_model: str | None = None
    # Optional: absolute path to a workspace directory. When set, the
    # agent gets Codex-style file tools (read_file / write_file /
    # edit_file / list_files / delete_file) scoped strictly to that
    # directory. The desktop app supplies this when the user picks a
    # Workspace folder. Path-traversal escapes are rejected inside
    # praxia.agent.file_tools.
    workspace_root: str | None = None
    max_steps: int = 8
    verified: bool = False            # use CommandedAgent if True
    max_verify_rounds: int = 3
    memory_dir: str | None = None     # override server's default
    # Optional inline image attachments for this turn. Each entry must
    # be {"mime": "image/png", "data": "<base64>"} — the same shape
    # AutonomousAgent.run accepts. Forwarded straight through to the
    # LLM as image_url content parts. Vision-capable model required
    # (Claude 3+ / GPT-4o / Gemini 1.5+) — non-vision models will
    # error from the provider, not silently drop the image.
    images: list[dict[str, str]] | None = None
    # Optional non-image document attachments for this turn (alpha20+).
    # Each entry: {filename, mime, data (base64)}. Server-side, each is
    # parsed via praxia.io.parsers and the extracted text gets injected
    # as a system-style preamble before the user's prompt. Embedded
    # images that the parsers find (e.g. DOCX media, PDF page renders)
    # additionally get fed into the same images path so the vision LLM
    # sees them. Cap: 6 attachments per turn, 50 MB per file, matching
    # the Documents folder upload cap.
    attachments: list[dict[str, str]] | None = None


class AgentRunResponse(BaseModel):
    text: str
    tool_calls: list[dict[str, Any]] = []
    usage: dict[str, int] = {}
    steps: int = 0
    stopped_reason: str = "completed"
    # Commander-only:
    verdict_decision: str | None = None
    verdict_groundedness: float | None = None
    # alpha39+ advisory mode: when the verifier didn't fully ground
    # the answer, the inner draft is still returned in `text` and this
    # field carries the verifier's short rationale. The UI renders it
    # as a soft warning badge above the message — earlier alphas just
    # replaced the message with a generic abstention text, which threw
    # away tool-call results when the classifier misrouted intent to
    # the knowledge path. See commander._advisory_note for format.
    advisory_note: str | None = None
    citations: list[str] = []
    rounds: int | None = None
    # Full source records the commander retrieved before drafting. Each
    # entry has id (matches what citations references — e.g. "D#0"),
    # kind ("local_document" / "memory" / "frozen" / …), a 500-char
    # preview of the chunk text, and metadata (doc_id, folder_id,
    # relative_path, chunk_index, score for local_document sources).
    # The UI uses this to render a clickable "Sources" panel under
    # answers so the user can verify where each [D#N] citation came
    # from without spelunking through DevTools.
    sources: list[dict[str, Any]] = []
    # If thread_id was supplied, the new message ids
    user_message_id: str | None = None
    assistant_message_id: str | None = None
    # Workspace-scoped file writes the agent wants to do but hasn't —
    # the host must show these to the user and call /workspace/apply
    # for each approved op.
    pending_file_operations: list[dict[str, Any]] = []


class ApplyFileOpRequest(BaseModel):
    """Body for POST /workspace/apply — execute one previously-queued
    file operation after the user approved it."""
    workspace_root: str
    op: dict[str, Any]


# ---------------------------------------------------------------------------
# alpha20+: one-shot attachments on /agent/run
# ---------------------------------------------------------------------------

# Per-attachment cap matches the Documents folder upload route so the
# limits are predictable regardless of which path the user uses.
_ATTACH_MAX_BYTES = 50 * 1024 * 1024
_ATTACH_MAX_COUNT = 6
# Truncate parsed text injected as preamble. Larger docs land in the
# normal Documents folder route; one-shot attachments are meant for
# "answer about THIS file, right now" — a few thousand chars is enough.
_ATTACH_TEXT_PREAMBLE_LIMIT = 12_000

_IMAGE_MIMES = {
    "image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp",
}


def _absorb_attachments(
    prompt: str,
    *,
    attachments: list[dict[str, str]],
    user_images: list[dict[str, str]],
) -> tuple[str, list[dict[str, str]]]:
    """Parse attachments → build prompt preamble + merged images list.

    Returns (augmented_prompt, merged_images). The augmented_prompt
    prepends a "Attached files:" block listing each non-image
    attachment's parsed text (truncated). The merged_images list
    extends the user-supplied images with:
      - the raw bytes of image-MIME attachments
      - PDF page renders + DOCX/PPTX embedded media that fall out of
        the parser metadata
    """
    if not attachments:
        return prompt, user_images

    # Reject runaway batches at the boundary instead of inside the
    # agent loop where errors are noisier. Lazy-import HTTPException
    # so this module stays importable from agents that don't have
    # FastAPI installed.
    if len(attachments) > _ATTACH_MAX_COUNT:
        from fastapi import HTTPException as _HE
        raise _HE(
            400,
            f"Too many attachments ({len(attachments)}); cap is {_ATTACH_MAX_COUNT}",
        )

    import base64 as _b64
    from pathlib import Path as _P

    text_blocks: list[str] = []
    images_out: list[dict[str, str]] = list(user_images)

    for i, att in enumerate(attachments):
        filename = (att.get("filename") or f"attachment_{i}").strip()
        mime = (att.get("mime") or "").strip().lower()
        data_b64 = att.get("data") or ""
        if not data_b64:
            continue

        # Decode + size-check
        try:
            raw = _b64.b64decode(data_b64, validate=False)
        except Exception:
            continue
        if len(raw) > _ATTACH_MAX_BYTES:
            text_blocks.append(
                f"[attachment {filename!r} skipped: {len(raw)} bytes > "
                f"{_ATTACH_MAX_BYTES} cap]"
            )
            continue

        # Image-MIME → straight into the images list, no parsing
        if mime in _IMAGE_MIMES:
            images_out.append({"mime": mime, "data": data_b64})
            continue

        # Everything else → parse via the file_parsers registry
        try:
            from praxia.io.parsers import parse_file, supported_extensions
        except ImportError as e:
            text_blocks.append(
                f"--- {filename} (parser unavailable: {e}) ---\n"
                f"(could not parse this attachment)"
            )
            continue

        ext = _P(filename).suffix.lower().lstrip(".")
        if ext not in supported_extensions():
            text_blocks.append(
                f"--- {filename} (unsupported extension .{ext}) ---\n"
                f"(no parser registered for this file type)"
            )
            continue

        try:
            parsed = parse_file(io.BytesIO(raw), filename=filename)
        except Exception as e:
            text_blocks.append(
                f"--- {filename} (parse error: {str(e)[:120]}) ---"
            )
            continue

        # Pull out parser-discovered images (DOCX/PPTX embedded media,
        # PDF page renders) and add them to the vision stream.
        for ei in (parsed.metadata.get("embedded_images") or []):
            if isinstance(ei, dict) and ei.get("mime") and ei.get("data"):
                images_out.append({"mime": ei["mime"], "data": ei["data"]})
        for pi in (parsed.metadata.get("page_images") or []):
            if isinstance(pi, dict) and pi.get("mime") and pi.get("data"):
                images_out.append({"mime": pi["mime"], "data": pi["data"]})

        # And the parsed text as a system-style preamble block
        text = parsed.content or ""
        truncated_note = ""
        if len(text) > _ATTACH_TEXT_PREAMBLE_LIMIT:
            text = text[:_ATTACH_TEXT_PREAMBLE_LIMIT]
            truncated_note = (
                f"\n[...truncated at {_ATTACH_TEXT_PREAMBLE_LIMIT} chars — "
                f"add this file to a Documents folder for full-text retrieval]"
            )
        text_blocks.append(f"--- {filename} ---\n{text}{truncated_note}")

    if not text_blocks:
        return prompt, images_out

    preamble = (
        "The user attached the following file(s) inline with this turn. "
        "Read them first, then answer the question below.\n\n"
        + "\n\n".join(text_blocks)
        + "\n\n---\n\n"
    )
    return preamble + prompt, images_out


def build_router(*, current_user: Any, storage: Path):
    from fastapi import APIRouter, Depends, HTTPException

    chats_root = Path(storage) / "chats"

    # --- thread persistence (lightweight clone — keeps this router self-contained) ----

    def _load_thread_history(
        user_id: str,
        thread_id: str,
        *,
        max_messages: int = 30,
    ) -> list[dict[str, str]]:
        """Read the thread's last ``max_messages`` user+assistant turns
        so the agent can see the prior conversation context.

        alpha33+ fix for a long-standing latent bug: previously the
        agent router persisted every message but never loaded the
        history back into ``agent.run(history=...)``. Every chat turn
        ran statelessly, so follow-ups like "スライドを出力して"
        (referring to a draft in the previous assistant turn) couldn't
        use the prior content. The UI showed a conversation but the
        LLM didn't see one.

        Returns a list of ``{role, content}`` dicts in chronological
        order — what AutonomousAgent expects as ``history``. Returns
        an empty list when the thread doesn't exist (so callers don't
        crash on a brand-new conversation).
        """
        import json
        p = chats_root / user_id / f"{thread_id}.json"
        if not p.exists():
            return []
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        msgs = data.get("messages") or []
        # Keep only the trailing window — long threads otherwise
        # blow the prompt budget on weaker models.
        msgs = msgs[-int(max_messages):]
        out: list[dict[str, str]] = []
        for m in msgs:
            role = m.get("role")
            content = m.get("content")
            if role in ("user", "assistant") and isinstance(content, str):
                out.append({"role": role, "content": content})
        return out

    def _append_to_thread(
        user_id: str,
        thread_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        import json
        d = chats_root / user_id
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{thread_id}.json"
        if not p.exists():
            raise HTTPException(404, f"Thread not found: {thread_id}")
        data = json.loads(p.read_text(encoding="utf-8"))
        msg_id = uuid.uuid4().hex
        data["messages"].append({
            "id": msg_id,
            "role": role,
            "content": content,
            "timestamp": time.time(),
            "metadata": metadata or {},
        })
        data["updated_at"] = time.time()
        if not data.get("title") and role == "user":
            data["title"] = content[:80].replace("\n", " ").strip()
        p.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return msg_id

    # --- routes --------------------------------------------------------

    router = APIRouter()

    @router.post("/agent/run", response_model=AgentRunResponse)
    def run_agent(req: AgentRunRequest, user=Depends(current_user)):
        if not req.prompt.strip():
            raise HTTPException(400, "Empty prompt")

        # Lazy imports — keeps server router cheap when agent isn't called
        try:
            from praxia.agent import AutonomousAgent, CommandedAgent
            from praxia.core.llm import LLM
        except ImportError as e:  # pragma: no cover
            raise HTTPException(500, f"Praxia agent not available: {e}")

        memory_dir = req.memory_dir or str(Path(storage))

        try:
            llm = LLM(req.model)
        except Exception as e:
            raise HTTPException(500, f"LLM init failed: {e}")

        # Optional scout LLM — used by the decomposer + verifier when
        # CommandedAgent is enabled below. If not provided (or set to the
        # same string as `model`), the main LLM doubles as scout.
        scout_llm = None
        if req.scout_model and req.scout_model != req.model:
            try:
                scout_llm = LLM(req.scout_model)
            except Exception as e:  # pragma: no cover
                # Soft-fail: a bad scout_model shouldn't kill the request,
                # just fall back to the main LLM for sub-calls.
                _log.warning("scout LLM init failed (%s); using main LLM", e)
                scout_llm = None

        # Workspace-scoped file tools — opt-in via workspace_root.
        # Resolved + validated inside praxia.agent.file_tools so a
        # malformed path returns HTTP 400 here rather than blowing up
        # inside the agent loop later.
        extra_tools = []
        pending_file_ops: list[dict[str, Any]] = []
        if req.workspace_root:
            try:
                from praxia.agent.file_tools import workspace_tools
                # Default to require_confirmation=True — file writes
                # never touch disk during the agent run; they queue
                # into pending_file_ops for the user to approve.
                tools_dict = workspace_tools(
                    req.workspace_root,
                    require_confirmation=True,
                    pending_sink=pending_file_ops,
                )
                extra_tools = list(tools_dict.values())
            except Exception as e:
                raise HTTPException(400, f"Invalid workspace_root: {e}")

        inner = AutonomousAgent(
            user_id=user.id,
            role=user.role,
            org_id=req.org_id,
            llm=llm,
            memory_dir=memory_dir,
            max_steps=max(1, int(req.max_steps)),
            extra_tools=extra_tools or None,
        )
        # alpha22+: tag fields the agent tools (run_parallel_tasks,
        # schedule_recurring_task) need so they can propagate the
        # caller's LLM config into child TaskRecords. Without these,
        # every fan-out / cron-fired task defaults to model='claude'
        # in the worker, which crashes any non-Anthropic user with
        # "Missing ANTHROPIC_API_KEY". scout_model + workspace_root
        # aren't on AutonomousAgent's __init__ contract (they belong
        # to the route and CommandedAgent respectively), so we attach
        # them as underscore-prefixed attributes.
        inner._scout_model = req.scout_model
        inner._workspace_root = req.workspace_root

        # alpha20+: one-shot document attachments. Each non-image
        # attachment is parsed server-side; its text is prepended to
        # the prompt as a system-style preamble, and any embedded /
        # page images the parser found are merged into req.images so
        # the vision LLM sees figures inside PDFs / Office docs too.
        # Image-MIME attachments short-circuit straight to req.images.
        augmented_prompt, merged_images = _absorb_attachments(
            req.prompt,
            attachments=req.attachments or [],
            user_images=list(req.images or []),
        )

        # alpha33+: load prior turns BEFORE appending the new user
        # message — otherwise the new message would appear twice in
        # the agent's view (once in history, once in the prompt).
        thread_history: list[dict[str, str]] = []
        if req.thread_id:
            thread_history = _load_thread_history(user.id, req.thread_id)

        # If thread_id supplied, persist user message first (so the agent
        # sees it as user-said, and so retries pick it up).
        user_msg_id = None
        if req.thread_id:
            user_msg_id = _append_to_thread(
                user.id, req.thread_id, "user", req.prompt,
            )

        # Execute
        try:
            if req.verified:
                agent = CommandedAgent(
                    inner,
                    scout_llm=scout_llm,
                    max_verify_rounds=max(1, int(req.max_verify_rounds)),
                    require_citations=True,
                )
                cresult = agent.run(
                    augmented_prompt,
                    history=thread_history or None,
                    images=merged_images or None,
                )
                final_text = cresult.answer
                # Serialise the retrieved sources so the UI can render a
                # "where did [D#N] come from" panel. We cap the preview
                # at 500 chars per source to keep the JSON body sane —
                # the full chunk text is already on disk under the
                # user's Documents folder if they want to inspect more.
                sources_payload: list[dict[str, Any]] = []
                for s in cresult.sources:
                    sources_payload.append({
                        "id": s.id,
                        "kind": s.kind,
                        "text_preview": (s.text or "")[:500],
                        "text_truncated": len(s.text or "") > 500,
                        "metadata": dict(s.metadata or {}),
                    })
                resp = AgentRunResponse(
                    text=final_text,
                    tool_calls=[],
                    usage=cresult.usage,
                    steps=sum((r.inner_result.steps if r.inner_result else 0) for r in cresult.rounds),
                    stopped_reason=cresult.stopped_reason,
                    verdict_decision=cresult.verdict.decision,
                    verdict_groundedness=cresult.verdict.groundedness,
                    advisory_note=(cresult.advisory_note or None),
                    citations=list(cresult.citations),
                    sources=sources_payload,
                    rounds=len(cresult.rounds),
                    pending_file_operations=list(pending_file_ops),
                )
            else:
                result = inner.run(
                    augmented_prompt,
                    history=thread_history or None,
                    images=merged_images or None,
                )
                resp = AgentRunResponse(
                    text=result.final_text,
                    tool_calls=[
                        {
                            "name": tc.name,
                            "ok": tc.ok,
                            "arguments_preview": tc.arguments_text[:200],
                            "result_preview": tc.result_text[:200],
                        }
                        for tc in result.tool_calls
                    ],
                    usage=result.usage,
                    steps=result.steps,
                    stopped_reason=result.stopped_reason,
                    pending_file_operations=list(pending_file_ops),
                )
                final_text = result.final_text
        except Exception as e:
            _log.exception("Agent run failed")
            raise HTTPException(500, f"Agent run failed: {e}")

        # Persist assistant reply
        if req.thread_id:
            asst_metadata: dict[str, Any] = {
                "verified": req.verified,
                "model": req.model,
            }
            if resp.advisory_note:
                # alpha39+: surface advisory mode in the persisted thread
                # so the warning badge survives reloads.
                asst_metadata["advisory_note"] = resp.advisory_note
                asst_metadata["verdict_decision"] = resp.verdict_decision
                asst_metadata["verdict_groundedness"] = resp.verdict_groundedness
            asst_msg_id = _append_to_thread(
                user.id, req.thread_id, "assistant", final_text,
                metadata=asst_metadata,
            )
            resp.user_message_id = user_msg_id
            resp.assistant_message_id = asst_msg_id

        return resp

    @router.post("/workspace/apply")
    def apply_workspace_op(req: ApplyFileOpRequest, user=Depends(current_user)):
        """Execute one previously-queued file operation.

        The agent run produced a ``pending_file_operations`` list. The
        frontend showed each one to the user with a diff preview. For
        every op the user clicked "Apply" on, the frontend calls this
        endpoint. Path scope is re-validated here — the user's
        approval doesn't override the workspace boundary, and
        ``apply_pending_op`` rejects anything that resolves outside.
        """
        try:
            from praxia.agent.file_tools import apply_pending_op
        except ImportError as e:  # pragma: no cover
            raise HTTPException(500, f"file_tools unavailable: {e}")

        auth_audit = getattr(user, "_audit_channel", None)
        try:
            # AuthManager's audit channel — pass through if reachable.
            from praxia.auth.manager import AuthManager  # noqa: F401
            # The audit instance lives on the request-scoped auth
            # manager. We approximate by importing the storage path.
        except Exception:  # pragma: no cover
            auth_audit = None

        result = apply_pending_op(
            req.workspace_root,
            req.op,
            actor_id=user.id,
            audit_record=auth_audit,
        )
        if "error" in result:
            raise HTTPException(400, result["error"])
        return result

    return router
