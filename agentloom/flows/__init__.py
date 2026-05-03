"""Specialized multi-agent flows shipped out of the box.

| Flow                | Purpose                                                |
|---------------------|--------------------------------------------------------|
| SalesAgentFlow      | Pre-meeting research, proposal drafting, FAQ           |
| LogicCheckerFlow    | Logical consistency, contradiction & foreshadowing     |
| RAGOptimizationFlow | Self-correcting RAG: query → retrieve → eval → loop    |
"""
from agentloom.flows.sales_agent import SalesAgentFlow
from agentloom.flows.logic_checker import LogicCheckerFlow
from agentloom.flows.rag_optimizer import RAGOptimizationFlow

ALL_FLOWS = [SalesAgentFlow, LogicCheckerFlow, RAGOptimizationFlow]

__all__ = [
    "SalesAgentFlow",
    "LogicCheckerFlow",
    "RAGOptimizationFlow",
    "ALL_FLOWS",
]
