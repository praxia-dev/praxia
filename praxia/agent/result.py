"""Result dataclasses returned by `AutonomousAgent.run()`."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCallTrace:
    """One tool invocation recorded during the loop.

    Attributes:
        name: tool name the LLM called (e.g., "search_personal_memory").
        arguments: parsed JSON arguments — `{}` if the model returned malformed JSON.
        arguments_text: raw arguments string from the model (for debugging).
        result: structured tool result (whatever the tool returned).
        result_text: serialized result that was fed back into the model.
        ok: True iff the tool ran without raising.
        error: error message if `ok=False`.
        step: 0-indexed step number within the run.
    """
    step: int
    name: str
    arguments: dict[str, Any]
    arguments_text: str
    result: Any = None
    result_text: str = ""
    ok: bool = True
    error: str = ""


@dataclass
class AgentResult:
    """Outcome of an `AutonomousAgent.run()` invocation."""
    final_text: str
    tool_calls: list[ToolCallTrace] = field(default_factory=list)
    steps: int = 0
    stopped_reason: str = "completed"   # completed | max_steps | error
    usage: dict[str, int] = field(default_factory=dict)

    def add_usage(self, more: dict[str, int]) -> None:
        for k, v in more.items():
            self.usage[k] = self.usage.get(k, 0) + int(v or 0)
