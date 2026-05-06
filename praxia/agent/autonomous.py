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
        system_prompt: str | None = None,
    ) -> AgentResult:
        """Run the tool-use loop until completion or `max_steps`.

        Args:
            user_input: the initial user message.
            history: prior messages (will be prepended after the system prompt).
            system_prompt: per-call override of the agent's system prompt.

        Returns:
            `AgentResult` with `final_text`, `tool_calls`, and `usage`.
        """
        sys_prompt = system_prompt or self.system_prompt
        messages: list[dict[str, Any]] = [{"role": "system", "content": sys_prompt}]
        if history:
            messages.extend(history)
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
