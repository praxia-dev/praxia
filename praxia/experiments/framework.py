"""A/B experiment framework — declarative experiments + deterministic
hash-based assignment + outcome rollup.

Storage is a single JSON file per experiment plus a JSONL outcome log;
no external service required.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ExperimentStatus(str, Enum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"


@dataclass
class Variant:
    """One arm of an experiment. `payload` is opaque — the calling code
    interprets it (prompt body, LLM alias, memory backend choice, etc.)."""

    name: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class Experiment:
    """Declarative experiment definition.

    Args:
        id: stable identifier (used in hashing — don't change once running).
        name: human-readable label.
        description: free text.
        variants: mapping of variant_name → Variant (or dict).
        traffic_split: mapping of variant_name → fraction (must sum to 1.0).
        status: ExperimentStatus value.
        target_audience: who is eligible. Keys: "roles" (list[str]),
                         "users" (list[str]), or "*" wildcard. Empty = all.
        start_at / end_at: epoch seconds, optional.
    """

    id: str
    name: str
    variants: dict[str, Variant] = field(default_factory=dict)
    traffic_split: dict[str, float] = field(default_factory=dict)
    description: str = ""
    status: str = ExperimentStatus.DRAFT.value
    target_audience: dict[str, Any] = field(default_factory=dict)
    start_at: float = 0.0
    end_at: float = 0.0
    created_at: float = field(default_factory=time.time)

    def is_eligible(self, *, user_id: str, role: str) -> bool:
        """Whether this user should see the experiment."""
        if self.status != ExperimentStatus.RUNNING.value:
            return False
        now = time.time()
        if self.start_at and now < self.start_at:
            return False
        if self.end_at and now > self.end_at:
            return False
        aud = self.target_audience or {}
        if not aud:
            return True
        roles = aud.get("roles") or []
        users = aud.get("users") or []
        if "*" in roles or "*" in users:
            return True
        return role in roles or user_id in users

    def validate(self) -> None:
        if not self.variants:
            raise ValueError(f"Experiment {self.id} has no variants")
        if not self.traffic_split:
            # Auto-uniform split
            n = len(self.variants)
            self.traffic_split = {name: 1 / n for name in self.variants}
        unknown = set(self.traffic_split) - set(self.variants)
        if unknown:
            raise ValueError(
                f"traffic_split has unknown variants: {unknown}"
            )
        total = sum(self.traffic_split.values())
        if not math.isclose(total, 1.0, abs_tol=0.01):
            raise ValueError(
                f"traffic_split must sum to 1.0, got {total:.3f}"
            )


@dataclass
class Assignment:
    """The variant assigned to a user for a given experiment."""

    experiment_id: str
    user_id: str
    variant_name: str
    payload: dict[str, Any]
    assigned_at: float = field(default_factory=time.time)


@dataclass
class ExperimentOutcome:
    """A single outcome event tied to an experiment + variant."""

    experiment_id: str
    variant_name: str
    user_id: str
    episode_id: str
    success: bool
    score: float | None
    notes: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class VariantSummary:
    name: str
    assignments: int = 0
    outcomes_recorded: int = 0
    successes: int = 0
    avg_score: float | None = None

    @property
    def success_rate(self) -> float | None:
        if self.outcomes_recorded == 0:
            return None
        return self.successes / self.outcomes_recorded


@dataclass
class ExperimentResults:
    experiment_id: str
    variants: list[VariantSummary]
    winner: str | None = None
    confidence: float = 0.0
    notes: str = ""


# --- Assignment function (pure) -------------------------------------------


def assign_variant(experiment: Experiment, *, user_id: str) -> Variant | None:
    """Deterministic hash-based assignment.

    The same (experiment.id, user_id) pair always maps to the same
    variant within one experiment run. Changing experiment.id resets
    the assignment (intentional — use a new id when you want fresh
    randomization).
    """
    if not experiment.variants:
        return None
    # Hash the (experiment_id, user_id) tuple to a value in [0, 1)
    h = hashlib.sha256(f"{experiment.id}:{user_id}".encode()).digest()
    bucket = int.from_bytes(h[:8], "big") / 2**64

    cumulative = 0.0
    for name, share in experiment.traffic_split.items():
        cumulative += share
        if bucket < cumulative:
            return experiment.variants.get(name)
    # Should not reach here if traffic_split sums to 1.0; fallback
    last = list(experiment.traffic_split)[-1]
    return experiment.variants.get(last)


# --- Storage ----------------------------------------------------------------


class ExperimentRegistry:
    """Persistent registry of experiments + outcomes.

    Storage layout:
        <storage_dir>/
            experiments/
                <experiment_id>.json
            outcomes/
                <experiment_id>.jsonl
    """

    def __init__(self, storage_dir: Path | str = ".praxia/experiments") -> None:
        self.dir = Path(storage_dir)
        self.exp_dir = self.dir / "experiments"
        self.out_dir = self.dir / "outcomes"
        for d in (self.exp_dir, self.out_dir):
            d.mkdir(parents=True, exist_ok=True)

    # --- Experiment CRUD --------------------------------------------------

    def create(self, exp: Experiment) -> Experiment:
        exp.validate()
        path = self.exp_dir / f"{exp.id}.json"
        if path.exists():
            raise ValueError(f"Experiment {exp.id} already exists")
        self._write_exp(exp)
        return exp

    def get(self, exp_id: str) -> Experiment | None:
        path = self.exp_dir / f"{exp_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        # Rebuild variants from dict
        variants = {
            n: Variant(**v) if not isinstance(v, Variant) else v
            for n, v in data.get("variants", {}).items()
        }
        data["variants"] = variants
        return Experiment(**data)

    def list(self, *, status: ExperimentStatus | str | None = None) -> list[Experiment]:
        out: list[Experiment] = []
        for p in self.exp_dir.glob("*.json"):
            exp = self.get(p.stem)
            if exp is None:
                continue
            if status and exp.status != (
                status.value if isinstance(status, ExperimentStatus) else status
            ):
                continue
            out.append(exp)
        return out

    def update(self, exp: Experiment) -> Experiment:
        exp.validate()
        self._write_exp(exp)
        return exp

    def set_status(self, exp_id: str, status: ExperimentStatus | str) -> Experiment:
        exp = self.get(exp_id)
        if exp is None:
            raise KeyError(f"Unknown experiment: {exp_id}")
        exp.status = status.value if isinstance(status, ExperimentStatus) else status
        self._write_exp(exp)
        return exp

    def delete(self, exp_id: str) -> bool:
        path = self.exp_dir / f"{exp_id}.json"
        if not path.exists():
            return False
        path.unlink()
        # Outcomes log is left intact for audit; admins can prune it manually
        return True

    def _write_exp(self, exp: Experiment) -> None:
        path = self.exp_dir / f"{exp.id}.json"
        # Serialize variants to dicts
        data = asdict(exp)
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )

    # --- Assignment -------------------------------------------------------

    def assign(
        self,
        exp_id: str,
        *,
        user_id: str,
        role: str = "member",
    ) -> Variant | None:
        """Resolve which variant `user_id` sees for experiment `exp_id`.

        Returns None if:
            - the experiment doesn't exist,
            - it's not RUNNING,
            - the user isn't in the target audience.
        """
        exp = self.get(exp_id)
        if exp is None:
            return None
        if not exp.is_eligible(user_id=user_id, role=role):
            return None
        return assign_variant(exp, user_id=user_id)

    # --- Outcomes ---------------------------------------------------------

    def record_outcome(
        self,
        exp_id: str,
        *,
        user_id: str,
        episode_id: str,
        success: bool,
        score: float | None = None,
        notes: str = "",
        role: str = "member",
    ) -> ExperimentOutcome | None:
        """Record an outcome for the variant `user_id` was assigned to.

        Returns None if the user isn't enrolled in the experiment.
        """
        variant = self.assign(exp_id, user_id=user_id, role=role)
        if variant is None:
            return None
        outcome = ExperimentOutcome(
            experiment_id=exp_id,
            variant_name=variant.name,
            user_id=user_id,
            episode_id=episode_id,
            success=success,
            score=score,
            notes=notes,
        )
        log = self.out_dir / f"{exp_id}.jsonl"
        with log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(outcome), ensure_ascii=False) + "\n")
        return outcome

    def outcomes(self, exp_id: str) -> list[ExperimentOutcome]:
        log = self.out_dir / f"{exp_id}.jsonl"
        if not log.exists():
            return []
        out: list[ExperimentOutcome] = []
        with log.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(ExperimentOutcome(**json.loads(line)))
                except Exception:
                    continue
        return out

    # --- Results ---------------------------------------------------------

    def results(
        self,
        exp_id: str,
        *,
        users: list[str] | None = None,
        role: str = "member",
    ) -> ExperimentResults:
        """Roll up outcomes by variant + flag a tentative winner.

        Args:
            users: optional list of user_ids to count as enrolled
                   (used for assignments-count). If None, derived from the
                   set of users who have outcomes.
        """
        exp = self.get(exp_id)
        if exp is None:
            raise KeyError(f"Unknown experiment: {exp_id}")

        outcomes = self.outcomes(exp_id)
        # Group outcomes
        variant_summaries: dict[str, VariantSummary] = {
            n: VariantSummary(name=n) for n in exp.variants
        }

        for o in outcomes:
            if o.variant_name not in variant_summaries:
                continue
            s = variant_summaries[o.variant_name]
            s.outcomes_recorded += 1
            if o.success:
                s.successes += 1
            if o.score is not None:
                # Running average
                if s.avg_score is None:
                    s.avg_score = float(o.score)
                else:
                    s.avg_score = (
                        s.avg_score * (s.outcomes_recorded - 1) + o.score
                    ) / s.outcomes_recorded

        # Estimate assignments
        if users:
            for u in users:
                v = self.assign(exp_id, user_id=u, role=role)
                if v:
                    variant_summaries[v.name].assignments += 1

        # Pick a tentative winner — highest success rate with ≥30 outcomes
        winner = None
        confidence = 0.0
        eligible = [
            s for s in variant_summaries.values()
            if s.outcomes_recorded >= 30 and s.success_rate is not None
        ]
        if len(eligible) >= 2:
            eligible.sort(key=lambda s: s.success_rate or 0.0, reverse=True)
            top, runner_up = eligible[0], eligible[1]
            margin = (top.success_rate or 0) - (runner_up.success_rate or 0)
            if margin >= 0.05:
                winner = top.name
                # Naive confidence from sample size + margin
                confidence = min(1.0, margin * math.sqrt(top.outcomes_recorded) / 5)

        notes = (
            "tentative — proper significance test recommended for production decisions"
            if winner else "insufficient data for a confident winner"
        )
        return ExperimentResults(
            experiment_id=exp_id,
            variants=list(variant_summaries.values()),
            winner=winner,
            confidence=confidence,
            notes=notes,
        )


__all__ = [
    "ExperimentStatus",
    "Variant",
    "Experiment",
    "Assignment",
    "ExperimentOutcome",
    "VariantSummary",
    "ExperimentResults",
    "ExperimentRegistry",
    "assign_variant",
]
