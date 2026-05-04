"""Specialized multi-agent flows shipped out of the box.

| Flow                | Purpose                                                |
|---------------------|--------------------------------------------------------|
| SalesAgentFlow      | Pre-meeting research, proposal drafting, FAQ           |
| LogicCheckerFlow    | Logical consistency, contradiction & foreshadowing     |
| RAGOptimizationFlow | Self-correcting RAG: query → retrieve → eval → loop    |

To add a custom flow:

    1. Subclass `Flow` (see existing flows for the pattern).
    2. Either:
       a. `@FLOWS.register_decorator("my_flow")` for in-tree flows
       b. Declare an entry-point in your package's pyproject.toml:
          [project.entry-points."praxia.flows"]
          incident_response = "my_pkg.incident_response:IncidentResponseFlow"

The framework auto-discovers entry-points; **no edit to this file**.
"""
from __future__ import annotations

from praxia.core.flow import Flow
from praxia.extensions import Registry
from praxia.flows.sales_agent import SalesAgentFlow
from praxia.flows.logic_checker import LogicCheckerFlow
from praxia.flows.rag_optimizer import RAGOptimizationFlow

FLOWS: Registry[Flow] = Registry(name="flow", entry_point_group="praxia.flows")


def _register_builtins() -> None:
    """Register the three built-in flows by their `name` attribute."""
    for cls in (SalesAgentFlow, LogicCheckerFlow, RAGOptimizationFlow):
        if not FLOWS.has(cls.name):
            FLOWS.register(cls.name, cls)


_register_builtins()


def get_flow(name: str) -> type[Flow]:
    """Look up a Flow class by its `name`. Includes entry-points."""
    try:
        return FLOWS.get(name)
    except KeyError:
        raise ValueError(
            f"Unknown flow: {name!r}. Available: {FLOWS.list()}"
        )


# Legacy convenience list — derived from the registry rather than hard-coded.
ALL_FLOWS = [SalesAgentFlow, LogicCheckerFlow, RAGOptimizationFlow]


__all__ = [
    "SalesAgentFlow",
    "LogicCheckerFlow",
    "RAGOptimizationFlow",
    "FLOWS",
    "ALL_FLOWS",
    "get_flow",
]
