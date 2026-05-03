"""Flow — a declarative multi-agent workflow definition.

A Flow is an ordered sequence of `FlowStep`s. Each step invokes one Agent
and writes its output back to the shared context dict, where downstream steps
reference it by name.

Specialized flows (sales / logic / rag) live in `praxia.flows`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from praxia.core.agent import Agent, AgentResult


@dataclass
class FlowStep:
    """One step in a flow.

    Attributes:
        name: identifier used to reference this step's output in later steps.
        agent: the Agent to invoke.
        inputs: mapping of input-name -> source. A source may be:
            * a literal value
            * a string template referencing prior outputs as `${step_name}`
            * a callable taking the running context dict
        condition: optional predicate `(context) -> bool`. Step skipped if False.
    """

    name: str
    agent: Agent
    inputs: dict[str, Any] = field(default_factory=dict)
    condition: Callable[[dict[str, Any]], bool] | None = None


@dataclass
class FlowResult:
    """Aggregate output of a complete flow run."""

    final_output: str
    step_outputs: dict[str, AgentResult]
    total_usage: dict[str, int]


class Flow:
    """Base class for multi-agent flows.

    Subclass and define `steps`. The framework wires inputs/outputs and
    invokes each agent in order.
    """

    name: str = "flow"
    description: str = ""
    steps: list[FlowStep] = []

    def __init__(self, steps: list[FlowStep] | None = None) -> None:
        if steps is not None:
            self.steps = steps

    def _resolve_inputs(
        self,
        spec: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        resolved: dict[str, Any] = {}
        for key, source in spec.items():
            if callable(source):
                resolved[key] = source(context)
            elif isinstance(source, str) and "${" in source:
                # naive `${step_name}` template substitution
                value = source
                for ctx_key, ctx_value in context.items():
                    value = value.replace(f"${{{ctx_key}}}", str(ctx_value))
                resolved[key] = value
            else:
                resolved[key] = source
        return resolved

    def run(
        self,
        inputs: dict[str, Any],
        *,
        memory_snippets: list[str] | None = None,
    ) -> FlowResult:
        """Execute the flow. `inputs` are made available as context entries."""
        context: dict[str, Any] = dict(inputs)
        step_outputs: dict[str, AgentResult] = {}
        total_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

        for step in self.steps:
            if step.condition and not step.condition(context):
                continue

            resolved = self._resolve_inputs(step.inputs, context) if step.inputs else dict(inputs)
            result = step.agent.run(
                resolved,
                context=context,
                memory_snippets=memory_snippets,
            )
            step_outputs[step.name] = result
            context[step.name] = result.output

            usage = result.metadata.get("usage", {})
            for k in total_usage:
                total_usage[k] += usage.get(k, 0)

        # Default: the last step's output is the final result.
        final = list(step_outputs.values())[-1].output if step_outputs else ""
        return FlowResult(
            final_output=final,
            step_outputs=step_outputs,
            total_usage=total_usage,
        )
