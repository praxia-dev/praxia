"""Praxia — Specialized multi-agent orchestrator with cyclic memory.

Public API:
    Praxia         — main entry point
    Agent             — base class for individual agents
    Flow              — base class for multi-agent workflows
    LLM               — multi-provider LLM client (Qwen/ChatGPT/Gemini/Claude/local)
    PersonalMemory    — first-layer auto-extracting memory
    SharedMemory      — third-layer organizational memory blocks
"""
from praxia.core.agent import Agent
from praxia.core.flow import Flow, FlowStep
from praxia.core.llm import LLM, ProviderConfig
from praxia.core.orchestrator import Praxia
from praxia.memory.personal import PersonalMemory
from praxia.memory.shared import SharedMemory

__version__ = "0.1.0a0"

__all__ = [
    "Praxia",
    "Agent",
    "Flow",
    "FlowStep",
    "LLM",
    "ProviderConfig",
    "PersonalMemory",
    "SharedMemory",
    "__version__",
]
