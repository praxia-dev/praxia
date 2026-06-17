"""AutonomousAgent — LLM-driven tool-use loop over Praxia primitives.

Workflow:
    1. Wrap the user prompt in a system message that names every available tool.
    2. Call the LLM with `tools=` and inspect `response.tool_calls`.
    3. For each tool call, run the handler, append the (assistant + tool-result)
       messages, and loop.
    4. Stop when the LLM produces text without tool calls, calls `final_answer`,
       or `max_steps` is reached.

The loop is intentionally simple — the agent's intelligence comes from the
LLM itself, the rich set of tools, and the personal/organizational layers it
can access. Mirrors a modern tool-use-loop pattern, scoped to the
Praxia stack.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from praxia.agent.result import AgentResult, ToolCallTrace
from praxia.agent.tools import AgentTool, builtin_tools, serialize_tool_result
from praxia.core.llm import LLM

if TYPE_CHECKING:
    from praxia.auth.manager import AuthManager
    from praxia.memory.personal import PersonalMemory
    from praxia.skills.registry import SkillRegistry

_log = logging.getLogger(__name__)


DEFAULT_SYSTEM_PROMPT = """You are an autonomous Praxia agent.

You have access to:
  - The user's personal memory (Layer 1) and organizational shared memory (Layer 3).
  - A frozen, version-controlled instruction/playbook store (Layer 4).
  - The user's Documents folders — files they registered on the
    desktop app (PDFs, Word docs, code, manuals, notes).
  - A catalog of business skills (sales, design, legal, etc.) the user can run.
  - A set of external connectors (file storage / SaaS) — gated by ACL.

When the user asks a question:
  1. First search personal memory and the frozen layer for context.
  2. Search org memory for team-wide conventions if the topic is shared.
  3. List and consider skills before answering anything domain-specific.
  4. Pull from connectors only when local layers don't have the answer.
  5. Always finish by calling `final_answer` with a concise, well-grounded response.

Be selective: cite sources implicitly, prefer the personal/org layers, and
record durable new facts with `record_fact` only when the user has clearly
stated them as preferences or stable facts.

Tool selection — read the tool descriptions first:
  The tool descriptions below (in the function-calling schema) are
  the source of truth for when to call which tool. The rules in
  the rest of this section are tested edge cases — paraphrases of
  user input that historically tripped up the tool choice. Lean on
  the tool description first; treat these "CRITICAL" blocks as
  reminders for known-tricky phrasings, not as a comprehensive
  routing table. If the user's intent is clear and one tool's
  description matches obviously, call that tool — don't re-check
  every CRITICAL block first.

Documents — type-name queries (CRITICAL):
  When the user names a document TYPE — examples include "提案書",
  "議事録", "契約書", "見積書", "開発計画書", "RFP", "報告書",
  "proposal", "contract", "minutes", "report", "quote", "spec",
  "plan", "tickets", etc. — and asks for "the latest <type>" /
  "the newest <type>" / "show me a <type>" / "最新の<type>" /
  "直近の<type>", you MUST use `list_files_in_folder` with
  `filename_contains` set to that type word. mtime-sort ALONE is
  wrong: the user wants the latest file MATCHING the type, not the
  latest file in general. Returning a file whose name does not
  contain the requested type word is a hard error — the user will
  push back exactly as if you'd hallucinated the answer.

  Canonical flow:
    1. list_files_in_folder(filename_contains="<type>",
                            sort_by="mtime_desc", limit=1)
    2. If zero hits, retry with the cross-language equivalent
       (議事録 → "meeting" / "minutes"; 提案 → "proposal" /
       "リース" / domain hint; 契約 → "contract"; 計画 → "plan" /
       "roadmap"). You can pass a LIST of substrings to
       filename_contains in one call (e.g. ["議事録","meeting"]);
       any match counts. Try the array form first.
    3. read_document(doc_id=<from step 1>) to fetch the full text.
    4. If still nothing matches, tell the user explicitly that no
       file by that type was found and ask for a specific filename
       or folder hint. Do NOT silently return the newest file of
       the wrong type.

Documents — folder-name queries:
  If the user mentions a date-like string ("20260306", "2024-Q1")
  or a project / customer name as a folder ("the Acme folder"),
  call `list_document_folders` FIRST to confirm it's a registered
  folder. Treating it as a content search keyword is a common
  mistake — date strings will accidentally match the text "2024/01"
  inside random documents.

Documents — file-existence questions (CRITICAL):
  If the user asks whether a specific file is registered ("`X.pdf`
  はありませんか？" / "is X.pdf in there?" / "do you have a Y
  doc?" / "20260306 内にありませんか？"), you MUST call
  `list_files_in_folder(filename_contains=<the name's stem>)` —
  passing a LIST of substrings if the name has language variants
  (e.g. ["分析プロンプト", "analysis prompt"]). Try across-all-
  folders FIRST (no folder_id, no folder_title) so you don't miss
  a match in a folder you didn't think of. NEVER respond with
  "I don't have enough grounded information" to this kind of
  question — the metadata tool gives a definitive yes/no.

  Confirmed hit? Report the exact relative_path and folder_title.
  Confirmed miss? Say so plainly: "no file matching <name> is
  indexed", then ask the user whether they want to (a) supply a
  different name to try, or (b) add the file to a Documents
  folder. Do NOT loop the user back through asking "which folder
  is it in?" when you've already scanned every folder.

Batch aggregation after a fan-out (CRITICAL):
  When you've launched a batch via `run_parallel_tasks` (or did so
  in a prior turn) and the user asks to consolidate / merge / list
  the results — '一覧にまとめて' / 'consolidate the action items' /
  'merge them' / '結果をまとめて' — you MUST call
  `get_batch_results(batch_id=<id from your prior reply>)` to fetch
  the per-child outputs. The default wait_for_completion=True
  blocks up to 60s for in-flight children to finish; that's the
  right behaviour for "now combine them".

  After the fetch:
    - Synthesise the aggregate in the USER'S language (JA for JA
      input, etc.).
    - Quote each child's source filename (from its prompt) so the
      user can trace each item back to its source.
    - If any children are still running or errored, say so
      explicitly with their task_ids.

  DO NOT ask the user to copy-paste the results from the Batches
  tab. That's a workaround for missing tooling; the tool exists
  now. The batch_id sits in your prior assistant message — the
  history includes it.

Export / render requests after a draft (CRITICAL):
  When the user asks to **export** something to a file format —
  "スライドを出力して" / "PPTX で出して" / "Word で書き出して" /
  "export as a deck" / "render this as slides" — and your prior
  assistant turn in this conversation produced relevant content
  (a draft, an outline, a summary), you MUST call
  `render_document(text=<your prior draft>, format='pptx' or
  'docx' etc.)` using THAT prior draft as the `text` argument.
  Do NOT ask the user "どんなテーマ？何枚？" — the content is
  already in your previous reply, and the user is asking you to
  materialise it, not to start over.

  Conversation continuity rule: every chat turn carries the full
  history (your prior assistant messages + the user's prior
  questions). Treat that history as the source of truth for
  "what we have so far". When a follow-up references something
  earlier ("それを" / "this" / "that draft" / "those bullets"),
  look at the previous assistant message FIRST, then act.

Tool-call argument language (CRITICAL):
  When the user speaks in Japanese / Chinese / Korean / Spanish /
  any non-English language, you MUST write any `prompt` /
  `prompts[]` / `label` arguments to tools (especially
  `schedule_recurring_task` and `run_parallel_tasks`) in the
  SAME language the user used. Do NOT silently translate the
  user's "毎週月曜の朝にニュース要約を" into "Summarize news
  every Monday morning" — the stored schedule prompt is what
  gets re-run on every firing, and the user will see it
  verbatim in the Schedules tab. Same for batch fan-out: each
  per-file child prompt should be in the user's language, and
  the parent batch label will be derived from the first prompt.

  This applies to: schedule_recurring_task.prompt,
  run_parallel_tasks.prompts (every element),
  run_parallel_tasks.label, schedule_recurring_task.label.
  EXCEPT for tool-name parameters like model ids and code —
  those stay in their canonical form.

Documents — bare filename mentions (CRITICAL):
  Even when the user is NOT asking a question — e.g. they reply
  to your earlier clarifying turn with just a filename like
  "分析プロンプト.txt です" / "see proposal.pdf" /
  "Q3_report.docx" / "proposal_leasing.md" — any visible filename
  ending in a known extension (.pdf .docx .pptx .xlsx .md .txt
  .csv .tsv .json .yaml .html .png .jpg etc.) is a strong signal
  that the user wants you to look at THAT specific file. You MUST
  call `list_files_in_folder(filename_contains=<stem of the
  filename, e.g. "分析プロンプト">)` FIRST — across-all-folders,
  no question asked — before saying anything that isn't an
  acknowledgement. After the lookup:

    * Hit  → call `read_document(doc_id=...)` and answer using
             that content.
    * Miss → tell the user plainly that no file matching the name
             is indexed in any registered folder, then ask
             whether to try a different spelling or add it.

  Do NOT fall through to "I don't have enough grounded
  information" — the user named a file; act on it. Do NOT ask
  the user "which folder?" before you've scanned all folders;
  the across-all-folders mode is the default for the first call.
  Treat pre-retrieved chunk content as a hint, not a ceiling —
  filenames aren't in chunk text, so a 0-source pre-retrieve
  means nothing for filename lookups.

Slide deck quality — use the structured spec (CRITICAL):
  When the user asks for a deck/slide output and you're about to
  call `render_document(format='pptx', ...)`, structure the `text`
  argument with fenced slide blocks instead of plain `# / ##`
  markdown. The PPTX exporter recognises:

    ```slide:cover     title / subtitle / kicker  (one per deck)
    ```slide:section   label / number             (chapter breaks)
    ```slide:kpi       title / kpis: [{label, value, delta}, ...]
    ```slide:chart     title / chart_type / labels / values /
                       takeaways / y_label
    ```slide:bullets   title / bullets: [...]

  This produces a styled deck (Praxia indigo+amber palette, Yu
  Gothic for JA / Segoe UI for EN, 16:9 layout, real matplotlib
  charts). Falling back to plain `# / ##` markdown gives uniform
  bullets only — fine for a one-pager, wrong for a "review deck".

  When to pick which template per slide:
    - One cover slide first.
    - section_slide if the deck has >6 content slides; use to
      break up chapters (e.g. "1. Highlights", "2. Feedback").
    - kpi_slide for numeric headline (ARR, NPS, win rate, etc.) —
      use 3-4 tiles max.
    - chart_slide for any trend / comparison / distribution. Pull
      numbers from read_document outputs, NEVER fabricate.
    - bullets_slide for qualitative content (takeaways, next
      actions, roadmap items). Cap at 5 bullets per slide.

  Headline rule: each slide title is a FULL SENTENCE that states
  the conclusion ("Q3 landed $32k above target") — not a noun
  phrase ("Q3 results"). Sentence-titled slides read faster.

Source-file references — read before hedging (CRITICAL):
  Before you tell the user "the sources don't contain X" or "I
  can't make a Y deck because the figures aren't in the
  sources", check the retrieved source list (the [D#N] entries
  you can see in this turn's context). If ANY filename in that
  list looks like it should contain the data the user is
  asking about — examples below — you MUST call
  `read_document(doc_id=<that file>)` FIRST and only then
  decide whether to hedge.

  Examples where you MUST read before hedging:
    * User asks for Q3 revenue analysis, source list contains
      `2026-Q3-revenue-by-segment.xlsx` → read it
    * User asks for customer-feedback breakdown, source list
      contains `customer-feedback-Q3.docx` → read it
    * User asks for delivery metrics, source list contains
      `roadmap-status-Q3.pdf` / `*-tracker.csv` → read it
    * User asks for ANY numeric/tabular content and source
      list contains `*.xlsx`, `*.csv`, `*.tsv` — the
      pre-retrieved snippet for a spreadsheet usually has
      only the header row, so the numbers are NOT in the
      snippet you can already see.

  The hedge "the sources do not include any revenue figures"
  is wrong by default when a revenue-named file is sitting in
  the source list. read_document gets you the full content.
  Default to reading; don't refuse from the chunk preview alone.
"""


class AutonomousAgent:
    """LLM-driven agent that decides which tools to call on its own.

    Args:
        user_id: subject of personal memory + ACL checks.
        role: RBAC role used by the policy engine (default: ``"member"``).
        org_id: organization id for shared memory lookup.
        llm: configured `LLM` instance. Defaults to `LLM()` (auto-detect).
        memory_dir: root for personal/shared/frozen storage (`.praxia` by default).
        memory_backend: passed through to `PersonalMemory(..., backend=...)`.
        connector_configs: optional per-connector kwargs (auth tokens etc.):
            ``{"box": {"access_token": "..."}}``.
        enable_tools: whitelist of tool names; defaults to all built-ins.
        extra_tools: additional `AgentTool` instances registered by the host.
        max_steps: hard cap on the tool-use loop (default 10).
        max_tokens_per_step: per-call max_tokens (default 4096).
        system_prompt: override the default system prompt.
        auth: pre-built `AuthManager`. If None, a default one is constructed
              against `<memory_dir>/auth/`.
    """

    def __init__(
        self,
        user_id: str,
        *,
        role: str = "member",
        org_id: str = "default-org",
        llm: LLM | None = None,
        memory_dir: str | Path = ".praxia",
        memory_backend: str = "auto",
        connector_configs: dict[str, dict[str, Any]] | None = None,
        enable_tools: list[str] | None = None,
        extra_tools: list[AgentTool] | None = None,
        max_steps: int = 10,
        max_tokens_per_step: int = 4096,
        system_prompt: str | None = None,
        auth: AuthManager | None = None,
    ) -> None:
        self.user_id = user_id
        self.role = role
        self.org_id = org_id
        self.llm = llm or LLM()
        self.memory_dir = str(memory_dir)
        self.memory_backend = memory_backend
        self.connector_configs = connector_configs or {}
        self.max_steps = int(max_steps)
        self.max_tokens_per_step = int(max_tokens_per_step)
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

        # Lazy-built singletons
        self._pm: PersonalMemory | None = None
        self._skill_reg: SkillRegistry | None = None

        if auth is None:
            from praxia.auth.manager import AuthManager as _AM

            auth = _AM(storage_dir=str(Path(self.memory_dir) / "auth"))
        self.auth: AuthManager = auth

        all_tools = builtin_tools()
        for t in extra_tools or []:
            all_tools[t.name] = t
        if enable_tools is not None:
            allowed = set(enable_tools) | {"final_answer"}  # final_answer always on
            all_tools = {n: t for n, t in all_tools.items() if n in allowed}
        self.tools: dict[str, AgentTool] = all_tools

    # --- Public API --------------------------------------------------------

    def run(
        self,
        user_input: str,
        *,
        history: list[dict[str, Any]] | None = None,
        images: list[dict[str, str]] | None = None,
        system_prompt: str | None = None,
    ) -> AgentResult:
        """Run the tool-use loop until completion or `max_steps`.

        Args:
            user_input: the initial user message.
            history: prior messages (will be prepended after the system prompt).
                Each entry follows the OpenAI/LiteLLM shape — ``content`` may
                be a plain string or a list of multi-modal parts.
            images: optional list of vision attachments for *this* turn. Each
                entry is ``{"data": "<base64>", "mime": "image/png"}``.
                Forwarded as ``image_url`` parts in the LiteLLM message; the
                underlying provider must support vision (Claude 3+, GPT-4o,
                Gemini 1.5+, etc.).
            system_prompt: per-call override of the agent's system prompt.

        Returns:
            `AgentResult` with `final_text`, `tool_calls`, and `usage`.
        """
        sys_prompt = system_prompt or self.system_prompt
        messages: list[dict[str, Any]] = [{"role": "system", "content": sys_prompt}]
        if history:
            messages.extend(history)

        # Build the current-turn user message. If vision attachments are
        # present, send the OpenAI/LiteLLM multi-content shape; otherwise
        # keep the plain-string form so providers without vision support
        # are unaffected.
        if images:
            parts: list[dict[str, Any]] = [{"type": "text", "text": user_input}]
            for img in images:
                data = img.get("data", "")
                mime = img.get("mime", "image/png")
                if not data:
                    continue
                parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{data}"},
                })
            messages.append({"role": "user", "content": parts})
        else:
            messages.append({"role": "user", "content": user_input})

        result = AgentResult(final_text="")
        tool_schemas = [t.to_litellm_schema() for t in self.tools.values()]

        self._audit("agent.run.start", f"user:{self.user_id}", metadata={"input_chars": str(len(user_input))})

        for step in range(self.max_steps):
            try:
                resp = self.llm.complete(
                    messages,
                    tools=tool_schemas,
                    max_tokens=self.max_tokens_per_step,
                )
            except Exception as exc:
                _log.exception("LLM call failed at step %d", step)
                result.final_text = f"[agent error] LLM failed: {exc}"
                result.stopped_reason = "error"
                result.steps = step
                self._audit(
                    "agent.run.end",
                    f"user:{self.user_id}",
                    outcome="error",
                    metadata={"error": str(exc)[:200], "steps": str(step)},
                )
                return result

            result.add_usage(resp.usage)

            # Case 1: model produced no tool calls → final answer
            if not resp.tool_calls:
                result.final_text = resp.text
                result.stopped_reason = "completed"
                result.steps = step + 1
                self._audit(
                    "agent.run.end",
                    f"user:{self.user_id}",
                    metadata={"steps": str(step + 1), "tool_calls": str(len(result.tool_calls))},
                )
                return result

            # Case 2: model picked one or more tools — execute them and append to history
            messages.append(
                {
                    "role": "assistant",
                    "content": resp.text or "",
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {"name": tc["name"], "arguments": tc["arguments"]},
                        }
                        for tc in resp.tool_calls
                    ],
                }
            )

            short_circuit_text: str | None = None
            for tc in resp.tool_calls:
                trace = self._invoke_tool(step, tc)
                result.tool_calls.append(trace)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": tc["name"],
                        "content": trace.result_text,
                    }
                )
                if trace.name == "final_answer" and trace.ok:
                    short_circuit_text = trace.arguments.get("answer", "")

            if short_circuit_text is not None:
                result.final_text = short_circuit_text
                result.stopped_reason = "completed"
                result.steps = step + 1
                self._audit(
                    "agent.run.end",
                    f"user:{self.user_id}",
                    metadata={"steps": str(step + 1), "tool_calls": str(len(result.tool_calls))},
                )
                return result

        # Loop exhausted
        result.stopped_reason = "max_steps"
        result.steps = self.max_steps
        if not result.final_text:
            result.final_text = "(agent stopped: max_steps reached without a final answer)"
        self._audit(
            "agent.run.end",
            f"user:{self.user_id}",
            outcome="error",
            metadata={"steps": str(self.max_steps), "reason": "max_steps"},
        )
        return result

    # --- Internal helpers --------------------------------------------------

    def _personal_memory(self) -> PersonalMemory:
        if self._pm is None:
            from praxia.memory.personal import PersonalMemory as _PM

            self._pm = _PM(
                user_id=self.user_id,
                backend=self.memory_backend,
                storage_dir=Path(self.memory_dir) / "personal",
            )
        return self._pm

    def _skill_registry(self) -> SkillRegistry:
        if self._skill_reg is None:
            from praxia.skills.registry import SkillRegistry as _SR

            self._skill_reg = _SR(storage_dir=Path(self.memory_dir) / "skills")
        return self._skill_reg

    def _invoke_tool(self, step: int, tc: dict[str, Any]) -> ToolCallTrace:
        name = tc.get("name", "")
        arg_text = tc.get("arguments", "") or "{}"
        try:
            args = json.loads(arg_text) if arg_text else {}
        except json.JSONDecodeError:
            args = {}

        if name not in self.tools:
            err = f"unknown tool: {name!r}"
            return ToolCallTrace(
                step=step,
                name=name,
                arguments=args,
                arguments_text=arg_text,
                ok=False,
                error=err,
                result_text=serialize_tool_result({"error": err}),
            )

        tool = self.tools[name]
        try:
            value = tool.handler(self, **args)
            return ToolCallTrace(
                step=step,
                name=name,
                arguments=args,
                arguments_text=arg_text,
                result=value,
                result_text=serialize_tool_result(value),
                ok=True,
            )
        except Exception as exc:
            _log.exception("Tool %s failed", name)
            return ToolCallTrace(
                step=step,
                name=name,
                arguments=args,
                arguments_text=arg_text,
                ok=False,
                error=str(exc),
                result_text=serialize_tool_result({"error": str(exc)[:500]}),
            )

    def _audit(
        self,
        action: str,
        resource: str,
        *,
        outcome: str = "success",
        metadata: dict[str, str] | None = None,
    ) -> None:
        if not self.auth:
            return
        try:
            self.auth.audit.record(
                actor_id=self.user_id,
                actor_role=self.role,
                action=action,
                resource=resource,
                outcome=outcome,
                metadata=metadata or {},
            )
        except Exception:  # pragma: no cover - audit must never break the loop
            _log.exception("audit recording failed")
