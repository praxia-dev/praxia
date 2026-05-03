"""Skill registry — personal & organizational skill catalog with promotion.

Mirrors the memory promotion model: skills start as personal, get tracked for
usage frequency and outcomes, then promote to the org registry once they meet
thresholds.

Storage layout (on disk):
    <storage_dir>/
        personal/<user_id>/<skill_name>/SKILL.md
        org/<skill_name>/SKILL.md
        usage.jsonl   — append-only usage log for promotion stats
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from praxia.skills.skill import Skill, SkillManifest


@dataclass
class SkillUsage:
    skill_name: str
    user_id: str
    timestamp: float
    success: bool | None = None  # outcome data, optional
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class RegisteredSkill:
    name: str
    manifest_path: Path
    scope: str  # "personal" | "org"
    user_id: str | None = None


class SkillRegistry:
    """Personal & organizational skill catalog."""

    def __init__(self, storage_dir: Path | str = ".praxia/skills") -> None:
        self.root = Path(storage_dir)
        (self.root / "personal").mkdir(parents=True, exist_ok=True)
        (self.root / "org").mkdir(parents=True, exist_ok=True)
        self._usage_log = self.root / "usage.jsonl"

    def register_personal(self, skill: Skill, user_id: str) -> RegisteredSkill:
        target_dir = self.root / "personal" / user_id / skill.manifest.name
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / "SKILL.md"
        path.write_text(skill.to_skill_md(), encoding="utf-8")
        return RegisteredSkill(
            name=skill.manifest.name,
            manifest_path=path,
            scope="personal",
            user_id=user_id,
        )

    def register_org(self, skill: Skill) -> RegisteredSkill:
        target_dir = self.root / "org" / skill.manifest.name
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / "SKILL.md"
        path.write_text(skill.to_skill_md(), encoding="utf-8")
        return RegisteredSkill(
            name=skill.manifest.name,
            manifest_path=path,
            scope="org",
        )

    def log_usage(
        self,
        *,
        skill_name: str,
        user_id: str,
        success: bool | None = None,
        metadata: dict[str, str] | None = None,
    ) -> None:
        usage = SkillUsage(
            skill_name=skill_name,
            user_id=user_id,
            timestamp=time.time(),
            success=success,
            metadata=metadata or {},
        )
        with self._usage_log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(usage), ensure_ascii=False) + "\n")

    def list_personal(self, user_id: str) -> list[RegisteredSkill]:
        base = self.root / "personal" / user_id
        if not base.exists():
            return []
        return [
            RegisteredSkill(
                name=p.parent.name,
                manifest_path=p,
                scope="personal",
                user_id=user_id,
            )
            for p in base.glob("*/SKILL.md")
        ]

    def list_org(self) -> list[RegisteredSkill]:
        base = self.root / "org"
        return [
            RegisteredSkill(name=p.parent.name, manifest_path=p, scope="org")
            for p in base.glob("*/SKILL.md")
        ]

    def get(self, name: str, *, scope: str = "org", user_id: str | None = None) -> Path | None:
        if scope == "personal" and user_id:
            path = self.root / "personal" / user_id / name / "SKILL.md"
        else:
            path = self.root / "org" / name / "SKILL.md"
        return path if path.exists() else None

    # --- Promotion ----------------------------------------------------------

    def usage_stats(self, skill_name: str) -> dict[str, float | int]:
        """Aggregate stats for a personal skill, used by the promotion engine."""
        if not self._usage_log.exists():
            return {"count": 0, "users": 0, "success_rate": 0.0}
        users: set[str] = set()
        successes = 0
        total = 0
        with self._usage_log.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    u = SkillUsage(**json.loads(line))
                except (json.JSONDecodeError, TypeError):
                    continue
                if u.skill_name != skill_name:
                    continue
                total += 1
                users.add(u.user_id)
                if u.success:
                    successes += 1
        return {
            "count": total,
            "users": len(users),
            "success_rate": (successes / total) if total else 0.0,
        }

    def promote_candidates(
        self,
        *,
        min_users: int = 3,
        min_count: int = 10,
        min_success_rate: float = 0.6,
    ) -> list[RegisteredSkill]:
        """Find personal skills that meet org-promotion thresholds."""
        seen: dict[str, RegisteredSkill] = {}
        candidates: list[RegisteredSkill] = []
        for user_dir in (self.root / "personal").glob("*"):
            user_id = user_dir.name
            for skill in self.list_personal(user_id):
                if skill.name in seen:
                    continue
                stats = self.usage_stats(skill.name)
                if (
                    stats["users"] >= min_users
                    and stats["count"] >= min_count
                    and stats["success_rate"] >= min_success_rate
                ):
                    candidates.append(skill)
                    seen[skill.name] = skill
        return candidates

    def promote(self, name: str, *, source_user_id: str) -> RegisteredSkill | None:
        """Copy a personal skill into the org-scope catalog."""
        src = self.root / "personal" / source_user_id / name / "SKILL.md"
        if not src.exists():
            return None
        dst_dir = self.root / "org" / name
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / "SKILL.md"
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        return RegisteredSkill(name=name, manifest_path=dst, scope="org")
