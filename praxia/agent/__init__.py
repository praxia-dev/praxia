"""Autonomous agent — LLM-driven tool-use loop over Praxia primitives.

`praxia.core.agent.Agent` is a single-shot prompt-then-respond agent. The
**autonomous** agent in this module runs a multi-step decision loop where the
LLM picks tools (memory search, skill invocation, connector pull, etc.) on its
own — no flow author needs to wire each step.

Built-in tools cover the personal + organizational layers:

    Personal:
        - search_personal_memory  (Layer 1)
        - record_fact             (writes — skipped in read_only mode)
        - list_personal_skills

    Organizational:
        - search_org_memory       (Layer 3 shared blocks)
        - search_frozen_layer     (Layer 4 markdown store)
        - list_org_skills
        - list_skills             (built-in business skills + entry points)
        - run_skill

    External:
        - list_connectors
        - pull_from_connector     (ACL-checked + audited)

Every tool call is recorded via `auth.audit.record(...)` and connector access
is gated through `auth.policies.require(...)`.

Example:

    from praxia.agent import AutonomousAgent
    from praxia.core.llm import LLM

    agent = AutonomousAgent(
        user_id="alice",
        role="member",
        org_id="acme",
        llm=LLM("claude"),
        max_steps=10,
    )
    result = agent.run("Acme との今四半期の営業活動を整理して提案書ドラフトを作成して")
    print(result.final_text)
    for tc in result.tool_calls:
        print(tc.name, tc.arguments_text[:100], "->", tc.result_text[:100])
"""
from praxia.agent.autonomous import AutonomousAgent
from praxia.agent.commander import (
    CommandedAgent,
    CommandedResult,
    CommandedRound,
    DEFAULT_ABSTAIN_MESSAGE,
    DefaultMemoryRetriever,
    LLMTaskClassifier,
    Retriever,
    TaskClassifier,
    default_task_classifier,
)
from praxia.agent.result import AgentResult, ToolCallTrace
from praxia.agent.verifier import (
    ClaimScore,
    LLMGroundingVerifier,
    Source,
    Verdict,
    Verifier,
)

__all__ = [
    # Inner agent (bare tool-use loop)
    "AutonomousAgent",
    "AgentResult",
    "ToolCallTrace",
    # Commanded agent (outer verification + retrieval loop)
    "CommandedAgent",
    "CommandedResult",
    "CommandedRound",
    "DEFAULT_ABSTAIN_MESSAGE",
    "DefaultMemoryRetriever",
    "Retriever",
    # Task classifier — LLM-based + keyword fallback
    "TaskClassifier",
    "default_task_classifier",
    "LLMTaskClassifier",
    # Verifier protocol + default impl + dataclasses
    "Verifier",
    "LLMGroundingVerifier",
    "Verdict",
    "ClaimScore",
    "Source",
]
