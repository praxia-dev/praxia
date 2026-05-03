"""Base Skill class — Claude Skills / MCP-compatible capability bundle.

A Skill packages: a system prompt, a small set of tools, and (optionally)
attached reference files. Inspired by Anthropic's Claude Skills format.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from agentloom.core.agent import Agent
from agentloom.core.llm import LLM


@dataclass
class SkillManifest:
    """Metadata that mirrors Claude-Skills SKILL.md frontmatter."""
    name: str
    description: str
    version: str = "0.1.0"
    domain: str = "general"
    tags: list[str] = field(default_factory=list)
    author: str | None = None


class Skill:
    """A self-contained capability backed by an Agent.

    Subclasses set `manifest`, `system_prompt`, and (optionally) `tools`.
    Use `as_agent()` to embed in a Flow, or `run()` for one-shot calls.
    """

    manifest: SkillManifest
    system_prompt: str = ""
    tools: list[Callable[..., Any]] = []
    reference_files: list[Path] = []

    def __init__(self, llm: LLM | None = None) -> None:
        self.llm = llm or LLM()

    def as_agent(self) -> Agent:
        return Agent(
            name=self.manifest.name,
            role=self.manifest.domain,
            system_prompt=self.system_prompt,
            llm=self.llm,
        )

    def run(self, user_input: str, **inputs: Any) -> str:
        agent = self.as_agent()
        result = agent.run({"input": user_input, **inputs})
        return result.output

    def to_skill_md(self) -> str:
        """Serialize to Claude-Skills compatible SKILL.md format."""
        m = self.manifest
        tags = ", ".join(m.tags)
        return (
            f"---\n"
            f"name: {m.name}\n"
            f"description: {m.description}\n"
            f"version: {m.version}\n"
            f"domain: {m.domain}\n"
            f"tags: [{tags}]\n"
            f"---\n\n"
            f"{self.system_prompt}"
        )
