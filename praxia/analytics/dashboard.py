"""Dashboard aggregations — personal and organizational usage views.

Pulls from these existing sources (no new tables):
    * `praxia.memory.PersonalMemory.all_entries()` — episodes / outcomes / facts
    * `praxia.skills.SkillRegistry.usage_stats()` + the usage.jsonl stream
    * `praxia.auth.AuditLog.tail()` — for action counts and active-user counts
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PersonalSummary:
    user_id: str
    flow_runs: int = 0
    skill_runs: int = 0
    memory_entries: int = 0
    episodes: int = 0
    outcomes_recorded: int = 0
    success_rate: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    top_skills: list[tuple[str, int]] = field(default_factory=list)  # (name, count)
    recent_episodes: list[str] = field(default_factory=list)
    last_active_ts: float = 0.0


@dataclass
class OrgSummary:
    org_id: str
    active_users: int = 0
    total_flow_runs: int = 0
    total_skill_runs: int = 0
    total_outcomes: int = 0
    org_success_rate: float = 0.0
    promoted_blocks: int = 0
    frozen_files: int = 0
    distributed_skills: int = 0
    distributed_prompts: int = 0
    top_users: list[tuple[str, int]] = field(default_factory=list)  # (user_id, action_count)
    top_skills: list[tuple[str, int]] = field(default_factory=list)
    audit_event_count: int = 0


class Dashboard:
    """Aggregator that produces both personal and organizational views.

    All inputs are optional — pass only the modules you've initialized.
    """

    def __init__(
        self,
        *,
        memory_dir: Path | str = ".praxia",
    ) -> None:
        self.root = Path(memory_dir)

    # --- Personal --------------------------------------------------------

    def personal_summary(self, user_id: str) -> PersonalSummary:
        s = PersonalSummary(user_id=user_id)
        s.memory_entries, s.episodes, s.outcomes_recorded, s.success_rate, s.recent_episodes, s.last_active_ts, s.total_input_tokens, s.total_output_tokens = self._scan_personal_memory(user_id)
        s.skill_runs, s.top_skills = self._scan_user_skill_usage(user_id)
        s.flow_runs = self._count_audit(action_prefix="flow.", actor_id=user_id)
        return s

    # --- Org ------------------------------------------------------------

    def org_summary(self, org_id: str = "default-org") -> OrgSummary:
        s = OrgSummary(org_id=org_id)
        s.active_users, s.top_users, s.audit_event_count = self._scan_audit()
        s.total_skill_runs, s.top_skills, s.org_success_rate, s.total_outcomes = self._scan_all_skill_usage()
        s.total_flow_runs = self._count_audit(action_prefix="flow.")
        s.promoted_blocks = self._count_files(self.root / "shared", "*.jsonl")
        s.frozen_files = self._count_files(self.root / "frozen", "*.md", recursive=True)
        s.distributed_skills = self._count_files(self.root / "skills" / "distributed", "*/SKILL.md", recursive=True)
        s.distributed_prompts = self._count_files(self.root / "prompts" / "distributed", "*.json", recursive=True)
        return s

    # --- Internals ------------------------------------------------------

    def _scan_personal_memory(
        self, user_id: str
    ) -> tuple[int, int, int, float, list[str], float, int, int]:
        path = self.root / "personal" / f"{user_id}.jsonl"
        if not path.exists():
            return 0, 0, 0, 0.0, [], 0.0, 0, 0
        entries = 0
        episodes = 0
        outcomes = 0
        successes = 0
        recent: list[tuple[float, str]] = []
        last_ts = 0.0
        in_tokens = 0
        out_tokens = 0
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                entries += 1
                ts = rec.get("timestamp", 0.0)
                last_ts = max(last_ts, ts)
                kind = rec.get("kind", "")
                if kind == "episode":
                    episodes += 1
                    recent.append((ts, rec.get("text", "")[:80]))
                    md = rec.get("metadata", {})
                    usage = md.get("usage", {})
                    in_tokens += usage.get("input_tokens", 0)
                    out_tokens += usage.get("output_tokens", 0)
                elif kind == "outcome":
                    outcomes += 1
                    if rec.get("metadata", {}).get("success"):
                        successes += 1
        recent.sort(reverse=True)
        rate = (successes / outcomes) if outcomes else 0.0
        return entries, episodes, outcomes, rate, [r[1] for r in recent[:5]], last_ts, in_tokens, out_tokens

    def _scan_user_skill_usage(self, user_id: str) -> tuple[int, list[tuple[str, int]]]:
        usage_log = self.root / "skills" / "usage.jsonl"
        if not usage_log.exists():
            return 0, []
        counter: Counter[str] = Counter()
        total = 0
        with usage_log.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    u = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if u.get("user_id") == user_id:
                    counter[u.get("skill_name", "?")] += 1
                    total += 1
        return total, counter.most_common(5)

    def _scan_all_skill_usage(self) -> tuple[int, list[tuple[str, int]], float, int]:
        usage_log = self.root / "skills" / "usage.jsonl"
        if not usage_log.exists():
            return 0, [], 0.0, 0
        counter: Counter[str] = Counter()
        total = 0
        outcomes = 0
        successes = 0
        with usage_log.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    u = json.loads(line)
                except json.JSONDecodeError:
                    continue
                counter[u.get("skill_name", "?")] += 1
                total += 1
                if u.get("success") is not None:
                    outcomes += 1
                    if u.get("success"):
                        successes += 1
        rate = (successes / outcomes) if outcomes else 0.0
        return total, counter.most_common(10), rate, outcomes

    def _scan_audit(self) -> tuple[int, list[tuple[str, int]], int]:
        audit = self.root / "auth" / "audit.jsonl"
        if not audit.exists():
            return 0, [], 0
        counter: Counter[str] = Counter()
        total = 0
        with audit.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                counter[e.get("actor_id", "unknown")] += 1
                total += 1
        # Filter system actor for "active users"
        active = [a for a in counter if a not in ("system", "anonymous", "unknown")]
        return len(active), counter.most_common(10), total

    def _count_audit(self, *, action_prefix: str, actor_id: str | None = None) -> int:
        audit = self.root / "auth" / "audit.jsonl"
        if not audit.exists():
            return 0
        count = 0
        with audit.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not e.get("action", "").startswith(action_prefix):
                    continue
                if actor_id and e.get("actor_id") != actor_id:
                    continue
                count += 1
        return count

    @staticmethod
    def _count_files(root: Path, pattern: str, *, recursive: bool = False) -> int:
        if not root.exists():
            return 0
        if recursive:
            return sum(1 for _ in root.rglob(pattern))
        return sum(1 for _ in root.glob(pattern))
