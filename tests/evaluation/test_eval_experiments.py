"""A/B experiments framework — exhaustive scenarios.

Coverage:
    - Experiment lifecycle (draft / running / paused / finished)
    - Deterministic assignment (same user → same variant always)
    - Traffic split (with tolerance for hash distribution)
    - Eligibility: status + audience + start/end window
    - Outcome recording + winner detection
    - Persistence (save / load / list)
"""
from __future__ import annotations

import time

import pytest

pytestmark = pytest.mark.evaluation


class TestExperimentLifecycle:
    def test_create_then_get(self, tmp_storage):
        from praxia.experiments import Experiment, ExperimentRegistry, Variant

        reg = ExperimentRegistry(storage_dir=tmp_storage)
        exp = reg.create(Experiment(
            id="t1",
            name="Test 1",
            variants={"a": Variant(name="a"), "b": Variant(name="b")},
            traffic_split={"a": 0.5, "b": 0.5},
        ))
        loaded = reg.get("t1")
        assert loaded is not None
        assert loaded.id == "t1"
        assert set(loaded.variants) == {"a", "b"}

    def test_create_twice_raises(self, tmp_storage):
        from praxia.experiments import Experiment, ExperimentRegistry, Variant

        reg = ExperimentRegistry(storage_dir=tmp_storage)
        reg.create(Experiment(
            id="t1", name="x",
            variants={"a": Variant(name="a")}, traffic_split={"a": 1.0},
        ))
        with pytest.raises(ValueError):
            reg.create(Experiment(
                id="t1", name="dup",
                variants={"a": Variant(name="a")}, traffic_split={"a": 1.0},
            ))

    def test_status_transition(self, tmp_storage):
        from praxia.experiments import (
            Experiment, ExperimentRegistry, ExperimentStatus, Variant,
        )

        reg = ExperimentRegistry(storage_dir=tmp_storage)
        reg.create(Experiment(
            id="t1", name="x",
            variants={"a": Variant(name="a")}, traffic_split={"a": 1.0},
            status=ExperimentStatus.DRAFT.value,
        ))
        reg.set_status("t1", ExperimentStatus.RUNNING)
        assert reg.get("t1").status == ExperimentStatus.RUNNING.value
        reg.set_status("t1", "finished")
        assert reg.get("t1").status == "finished"

    def test_delete(self, tmp_storage):
        from praxia.experiments import Experiment, ExperimentRegistry, Variant

        reg = ExperimentRegistry(storage_dir=tmp_storage)
        reg.create(Experiment(
            id="t1", name="x",
            variants={"a": Variant(name="a")}, traffic_split={"a": 1.0},
        ))
        assert reg.delete("t1") is True
        assert reg.delete("t1") is False  # idempotent
        assert reg.get("t1") is None


class TestValidation:
    def test_no_variants_rejected(self, tmp_storage):
        from praxia.experiments import Experiment, ExperimentRegistry

        reg = ExperimentRegistry(storage_dir=tmp_storage)
        with pytest.raises(ValueError):
            reg.create(Experiment(id="t", name="x"))

    def test_traffic_split_sum_check(self, tmp_storage):
        from praxia.experiments import Experiment, ExperimentRegistry, Variant

        reg = ExperimentRegistry(storage_dir=tmp_storage)
        with pytest.raises(ValueError):
            reg.create(Experiment(
                id="t", name="x",
                variants={"a": Variant(name="a"), "b": Variant(name="b")},
                traffic_split={"a": 0.7, "b": 0.4},  # sums to 1.1
            ))

    def test_unknown_variant_in_split_rejected(self, tmp_storage):
        from praxia.experiments import Experiment, ExperimentRegistry, Variant

        reg = ExperimentRegistry(storage_dir=tmp_storage)
        with pytest.raises(ValueError):
            reg.create(Experiment(
                id="t", name="x",
                variants={"a": Variant(name="a")},
                traffic_split={"a": 0.5, "ghost": 0.5},
            ))

    def test_default_uniform_split_when_omitted(self, tmp_storage):
        from praxia.experiments import Experiment, ExperimentRegistry, Variant

        reg = ExperimentRegistry(storage_dir=tmp_storage)
        exp = reg.create(Experiment(
            id="t", name="x",
            variants={"a": Variant(name="a"), "b": Variant(name="b")},
        ))
        assert exp.traffic_split == {"a": 0.5, "b": 0.5}


class TestAssignment:
    def test_deterministic_per_user(self, tmp_storage):
        from praxia.experiments import (
            Experiment, ExperimentRegistry, ExperimentStatus, Variant,
        )

        reg = ExperimentRegistry(storage_dir=tmp_storage)
        reg.create(Experiment(
            id="t", name="x",
            variants={"a": Variant(name="a"), "b": Variant(name="b")},
            traffic_split={"a": 0.5, "b": 0.5},
            status=ExperimentStatus.RUNNING.value,
        ))
        for _ in range(10):
            v1 = reg.assign("t", user_id="alice", role="member")
            v2 = reg.assign("t", user_id="alice", role="member")
            assert v1.name == v2.name

    def test_split_approximates_target(self, tmp_storage):
        from praxia.experiments import (
            Experiment, ExperimentRegistry, ExperimentStatus, Variant,
        )

        reg = ExperimentRegistry(storage_dir=tmp_storage)
        reg.create(Experiment(
            id="t", name="x",
            variants={"a": Variant(name="a"), "b": Variant(name="b")},
            traffic_split={"a": 0.7, "b": 0.3},
            status=ExperimentStatus.RUNNING.value,
        ))
        counts = {"a": 0, "b": 0}
        for i in range(2000):
            v = reg.assign("t", user_id=f"u{i}", role="member")
            counts[v.name] += 1
        ratio_a = counts["a"] / sum(counts.values())
        # 70% target ± 3% tolerance for 2000 samples
        assert 0.67 <= ratio_a <= 0.73

    def test_draft_assignment_returns_none(self, tmp_storage):
        from praxia.experiments import (
            Experiment, ExperimentRegistry, ExperimentStatus, Variant,
        )

        reg = ExperimentRegistry(storage_dir=tmp_storage)
        reg.create(Experiment(
            id="t", name="x",
            variants={"a": Variant(name="a")}, traffic_split={"a": 1.0},
            status=ExperimentStatus.DRAFT.value,
        ))
        assert reg.assign("t", user_id="alice") is None

    def test_audience_role_filter(self, tmp_storage):
        from praxia.experiments import (
            Experiment, ExperimentRegistry, ExperimentStatus, Variant,
        )

        reg = ExperimentRegistry(storage_dir=tmp_storage)
        reg.create(Experiment(
            id="t", name="x",
            variants={"a": Variant(name="a"), "b": Variant(name="b")},
            traffic_split={"a": 0.5, "b": 0.5},
            status=ExperimentStatus.RUNNING.value,
            target_audience={"roles": ["operator"]},
        ))
        # Member: not in audience → no assignment
        assert reg.assign("t", user_id="alice", role="member") is None
        # Operator: in audience → gets variant
        v = reg.assign("t", user_id="bob", role="operator")
        assert v is not None

    def test_user_specific_audience(self, tmp_storage):
        from praxia.experiments import (
            Experiment, ExperimentRegistry, ExperimentStatus, Variant,
        )

        reg = ExperimentRegistry(storage_dir=tmp_storage)
        reg.create(Experiment(
            id="t", name="x",
            variants={"a": Variant(name="a")}, traffic_split={"a": 1.0},
            status=ExperimentStatus.RUNNING.value,
            target_audience={"users": ["alice"]},
        ))
        assert reg.assign("t", user_id="alice", role="member") is not None
        assert reg.assign("t", user_id="bob", role="member") is None

    def test_time_window_respected(self, tmp_storage):
        from praxia.experiments import (
            Experiment, ExperimentRegistry, ExperimentStatus, Variant,
        )

        reg = ExperimentRegistry(storage_dir=tmp_storage)
        # Already-finished window
        reg.create(Experiment(
            id="t", name="x",
            variants={"a": Variant(name="a")}, traffic_split={"a": 1.0},
            status=ExperimentStatus.RUNNING.value,
            start_at=time.time() - 1000,
            end_at=time.time() - 500,
        ))
        assert reg.assign("t", user_id="alice", role="member") is None


class TestOutcomes:
    def test_record_and_aggregate(self, tmp_storage):
        from praxia.experiments import (
            Experiment, ExperimentRegistry, ExperimentStatus, Variant,
        )

        reg = ExperimentRegistry(storage_dir=tmp_storage)
        reg.create(Experiment(
            id="t", name="x",
            variants={"a": Variant(name="a"), "b": Variant(name="b")},
            traffic_split={"a": 0.5, "b": 0.5},
            status=ExperimentStatus.RUNNING.value,
        ))
        # Record 50 outcomes for various users
        for i in range(50):
            reg.record_outcome(
                "t", user_id=f"u{i}", episode_id=f"ep{i}",
                success=(i % 2 == 0), score=0.5 + (i * 0.005),
            )
        results = reg.results("t")
        total = sum(s.outcomes_recorded for s in results.variants)
        assert total == 50
        success_total = sum(s.successes for s in results.variants)
        assert success_total == 25  # half

    def test_outcome_for_unenrolled_user_returns_none(self, tmp_storage):
        from praxia.experiments import (
            Experiment, ExperimentRegistry, ExperimentStatus, Variant,
        )

        reg = ExperimentRegistry(storage_dir=tmp_storage)
        reg.create(Experiment(
            id="t", name="x",
            variants={"a": Variant(name="a")}, traffic_split={"a": 1.0},
            status=ExperimentStatus.RUNNING.value,
            target_audience={"users": ["alice"]},
        ))
        result = reg.record_outcome(
            "t", user_id="bob", episode_id="ep-1",
            success=True, role="member",
        )
        assert result is None

    def test_winner_detection(self, tmp_storage):
        from praxia.experiments import (
            Experiment, ExperimentRegistry, ExperimentStatus, Variant,
        )

        reg = ExperimentRegistry(storage_dir=tmp_storage)
        reg.create(Experiment(
            id="t", name="x",
            variants={"control": Variant(name="control"), "treat": Variant(name="treat")},
            traffic_split={"control": 0.5, "treat": 0.5},
            status=ExperimentStatus.RUNNING.value,
        ))
        # Find users that map to each variant (deterministic), then record
        # outcomes that strongly favor "treat"
        recorded_per_variant = {"control": 0, "treat": 0}
        i = 0
        while min(recorded_per_variant.values()) < 35:
            user = f"u{i}"
            v = reg.assign("t", user_id=user, role="member")
            if v is None:
                break
            target = recorded_per_variant[v.name]
            if target < 35:
                # control = 30% success, treat = 80% success
                if v.name == "control":
                    success = (target % 10) < 3  # ~30%
                else:
                    success = (target % 10) < 8  # ~80%
                reg.record_outcome(
                    "t", user_id=user, episode_id=f"ep{i}",
                    success=success,
                )
                recorded_per_variant[v.name] += 1
            i += 1
            if i > 5000:
                break  # safety
        results = reg.results("t")
        assert results.winner == "treat"
        assert results.confidence > 0.0
