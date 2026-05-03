"""Base Agent class. An Agent is a single-purpose role that contributes to a Flow."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agentloom.core.llm import LLM


@dataclass
class AgentResult:
    """Output of a single Agent invocation."""

    agent_name: str
    output: str
    metadata: dict[str, Any] = field(default_factory=dict)


class Agent:
    """A single role inside a multi-agent flow.

    Subclass and override `system_prompt()` and (optionally) `format_user_input()`
    to define behavior. Or instantiate directly with `system_prompt=...`.
    """

    name: str = "agent"
    role: str = "generic"

    def __init__(
        self,
        name: str | None = None,
        *,
        role: str | None = None,
        system_prompt: str | None = None,
        llm: LLM | None = None,
        memory_keys: list[str] | None = None,
    ) -> None:
        if name:
            self.name = name
        if role:
            self.role = role
        self._system_prompt = system_prompt
        self.llm = llm or LLM()
        self.memory_keys = memory_keys or []

    def system_prompt(self) -> str:
        """Override in subclass to define agent personality and rules."""
        if self._system_prompt:
            return self._system_prompt
        return f"You are {self.name}. Role: {self.role}. Be concise and accurate."

    def format_user_input(self, inputs: dict[str, Any], context: dict[str, Any]) -> str:
        """Compose the user-message body. Override for custom prompting."""
        parts: list[str] = []
        for key, value in inputs.items():
            parts.append(f"## {key}\n{value}")
        if context:
            parts.append("## Prior context")
            for key, value in context.items():
                parts.append(f"### {key}\n{value}")
        return "\n\n".join(parts)

    def run(
        self,
        inputs: dict[str, Any],
        *,
        context: dict[str, Any] | None = None,
        memory_snippets: list[str] | None = None,
    ) -> AgentResult:
        """Execute one turn. Returns the agent's output."""
        system = self.system_prompt()
        if memory_snippets:
            system += "\n\n## Relevant memory\n" + "\n---\n".join(memory_snippets)

        user = self.format_user_input(inputs, context or {})
        response = self.llm.complete(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
        )
        return AgentResult(
            agent_name=self.name,
            output=response.text,
            metadata={
                "model": response.model,
                "usage": response.usage,
            },
        )
