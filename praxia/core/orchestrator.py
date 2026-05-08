"""Praxia — main orchestrator that wires Flows + Memory + Skills together.

This is the user-facing entry point. Most users only ever instantiate this and
call `.run(flow_class, inputs={...})`.

Responsibilities:
    1. Pull relevant memory snippets from the personal layer before running.
    2. Execute the requested Flow.
    3. Auto-record the run as an episode in personal memory (no explicit save).
    4. Optionally fetch skill suggestions from the registry.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from praxia.core.flow import Flow, FlowResult
from praxia.core.llm import LLM
from praxia.memory.personal import PersonalMemory
from praxia.memory.shared import SharedMemory
from praxia.skills.registry import SkillRegistry


@dataclass
class LoomConfig:
    user_id: str = "default-user"
    org_id: str = "default-org"
    default_model: str = "auto"  # resolves via LLM.auto_detect()
    memory_dir: Path = field(default_factory=lambda: Path(".praxia"))
    enable_personal_memory: bool = True
    enable_shared_memory: bool = True
    enable_skill_registry: bool = True
    consolidation_threshold: float = 0.7  # for auto-promotion


class Praxia:
    """The main entry point.

    Example:
        from praxia import Praxia
        from praxia.flows import SalesAgentFlow

        loom = Praxia(user_id="alice", default_model="claude")
        result = loom.run(SalesAgentFlow, inputs={
            "customer_name": "Acme Corp",
            "product": "BizFlow",
        })
        print(result.final_output)
    """

    def __init__(
        self,
        user_id: str = "default-user",
        *,
        org_id: str = "default-org",
        default_model: str = "auto",
        memory_dir: Path | str = ".praxia",
        config: LoomConfig | None = None,
    ) -> None:
        self.config = config or LoomConfig(
            user_id=user_id,
            org_id=org_id,
            default_model=default_model,
            memory_dir=Path(memory_dir),
        )

        resolved_model = (
            LLM.auto_detect() if self.config.default_model == "auto" else self.config.default_model
        )
        self.llm = LLM(resolved_model)
        self.config.memory_dir.mkdir(parents=True, exist_ok=True)

        # Build the Layer-1 backend per the admin MemoryAdminPolicy.
        # For 'single' mode this is just a backend name string;
        # 'composite' / 'routed' return a fully-built MemoryBackend
        # instance. PersonalMemory accepts both shapes.
        try:
            from praxia.memory.policy import build_personal_backend
            _resolved_backend = build_personal_backend(
                self.config.memory_dir, user_id=self.config.user_id
            )
        except Exception:
            _resolved_backend = "auto"
        self.personal_memory: PersonalMemory | None = (
            PersonalMemory(
                user_id=self.config.user_id,
                backend=_resolved_backend,
                storage_dir=self.config.memory_dir / "personal",
            )
            if self.config.enable_personal_memory
            else None
        )
        self.shared_memory: SharedMemory | None = (
            SharedMemory(
                org_id=self.config.org_id,
                storage_dir=self.config.memory_dir / "shared",
            )
            if self.config.enable_shared_memory
            else None
        )
        self.skill_registry: SkillRegistry | None = (
            SkillRegistry(storage_dir=self.config.memory_dir / "skills")
            if self.config.enable_skill_registry
            else None
        )

    def run(
        self,
        flow_class: type[Flow] | Flow,
        inputs: dict[str, Any],
        *,
        record_episode: bool = True,
    ) -> FlowResult:
        """Execute a flow with memory-augmented context."""
        flow = flow_class() if isinstance(flow_class, type) else flow_class

        memory_snippets: list[str] = []
        if self.personal_memory:
            query = " ".join(str(v) for v in inputs.values())
            memory_snippets.extend(self.personal_memory.search(query, limit=3))
        if self.shared_memory:
            memory_snippets.extend(self.shared_memory.search(query=" ".join(str(v) for v in inputs.values()), limit=3))

        result = flow.run(inputs, memory_snippets=memory_snippets)

        if record_episode and self.personal_memory:
            self.personal_memory.record_episode(
                flow_name=flow.name,
                inputs=inputs,
                output=result.final_output,
                metadata={"usage": result.total_usage},
            )

        return result

    def consolidate(self, *, dry_run: bool = False) -> dict[str, Any]:
        """Run the sleep-time consolidator (personal -> shared promotion).

        Delegated to `praxia.memory.consolidator.SleepTimeConsolidator` to
        keep this class slim.
        """
        from praxia.memory.consolidator import SleepTimeConsolidator

        consolidator = SleepTimeConsolidator(
            personal=self.personal_memory,
            shared=self.shared_memory,
            llm=self.llm,
            threshold=self.config.consolidation_threshold,
        )
        return consolidator.run(dry_run=dry_run)
