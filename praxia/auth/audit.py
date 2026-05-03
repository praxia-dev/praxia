"""Audit log — append-only record of every privileged action.

Production deployments should also forward these events to SIEM (Splunk /
Datadog / etc.) via a streaming exporter. The on-disk JSONL is designed to be
trivially exportable.
"""
from __future__ import annotations

import json
import socket
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AuditEvent:
    id: str
    timestamp: float
    actor_id: str
    actor_role: str
    action: str        # e.g., "skill.run", "memory.read", "block.upsert"
    resource: str      # e.g., "skill:investment_analyst", "block:team_norms"
    outcome: str       # "success" | "denied" | "error"
    host: str = field(default_factory=socket.gethostname)
    metadata: dict[str, Any] = field(default_factory=dict)


class AuditLog:
    def __init__(self, storage_dir: Path | str = ".praxia/auth") -> None:
        self.dir = Path(storage_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "audit.jsonl"

    def record(
        self,
        *,
        actor_id: str,
        actor_role: str,
        action: str,
        resource: str,
        outcome: str = "success",
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            id=str(uuid.uuid4()),
            timestamp=time.time(),
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            resource=resource,
            outcome=outcome,
            metadata=metadata or {},
        )
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")
        return event

    def tail(self, *, limit: int = 100) -> list[AuditEvent]:
        if not self.path.exists():
            return []
        events: list[AuditEvent] = []
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    events.append(AuditEvent(**json.loads(line)))
                except (json.JSONDecodeError, TypeError):
                    continue
        return events[-limit:]

    def search(
        self,
        *,
        actor_id: str | None = None,
        action: str | None = None,
        outcome: str | None = None,
        since: float | None = None,
        limit: int = 1000,
    ) -> list[AuditEvent]:
        out: list[AuditEvent] = []
        for e in self.tail(limit=10_000):
            if actor_id and e.actor_id != actor_id:
                continue
            if action and not e.action.startswith(action):
                continue
            if outcome and e.outcome != outcome:
                continue
            if since and e.timestamp < since:
                continue
            out.append(e)
            if len(out) >= limit:
                break
        return out
