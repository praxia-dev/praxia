"""AgentLoom — Specialized multi-agent orchestrator with cyclic memory.

Public API:
    AgentLoom         — main entry point
    Agent             — base class for individual agents
    Flow              — base class for multi-agent workflows
    LLM               — multi-provider LLM client (Qwen/ChatGPT/Gemini/Claude/local)
    PersonalMemory    — first-layer auto-extracting memory
    SharedMemory      — third-layer organizational memory blocks
"""
from agentloom.core.agent import Agent
from agentloom.core.flow import Flow, FlowStep
from agentloom.core.llm import LLM, ProviderConfig
from agentloom.core.orchestrator import AgentLoom
from agentloom.memory.personal import PersonalMemory
from agentloom.memory.shared import SharedMemory

__version__ = "0.1.0a0"

__all__ = [
    "AgentLoom",
    "Agent",
    "Flow",
    "FlowStep",
    "LLM",
    "ProviderConfig",
    "PersonalMemory",
    "SharedMemory",
    "__version__",
]
