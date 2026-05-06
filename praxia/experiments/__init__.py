"""A/B experiments — variant assignment + outcome tracking.

The Praxia experiments module lets admins:

    1. Define an experiment with two or more variants (e.g., a baseline
       prompt vs a candidate prompt; Claude vs GPT-4o on the same skill).
    2. Assign each user to a variant deterministically (hash-based) so a
       given user always sees the same variant during the experiment.
    3. Track outcomes (success / score) per variant via the existing
       `record_outcome()` API.
    4. Decide a winner using either a simple proportion test or by
       eyeballing the dashboard.

Concept hierarchy:

    Experiment
        ├── id, name, description
        ├── variants  (e.g., {"control": ..., "treatment": ...})
        ├── traffic_split (e.g., {"control": 0.5, "treatment": 0.5})
        ├── status  (draft / running / paused / finished)
        ├── target_audience (role / user list / "*")
        └── start_at / end_at

A "variant" is opaque payload — typically:
    - Prompt body / system prompt for a skill
    - LLM provider alias to use
    - Memory backend choice
    - Skill version

Variants can target ANY part of the system because the assignment
function returns the variant payload; the calling code interprets it.

Example use:

    from praxia.experiments import ExperimentRegistry, Experiment

    registry = ExperimentRegistry(storage_dir=".praxia/experiments")
    exp = registry.create(Experiment(
        id="proposal_prompt_v2",
        name="Proposal prompt: shorter vs longer",
        variants={
            "control": {"prompt": "Original 800-word system prompt..."},
            "candidate": {"prompt": "New 400-word system prompt..."},
        },
        traffic_split={"control": 0.5, "candidate": 0.5},
        target_audience={"roles": ["member", "operator"]},
    ))

    # During flow execution
    variant = registry.assign(exp.id, user_id="alice", role="member")
    if variant is not None:
        prompt = variant.payload["prompt"]
    else:
        prompt = default_prompt
    ...
    # Record outcome on the same episode_id
    registry.record_outcome(exp.id, user_id="alice", episode_id=ep.id,
                            success=True, score=0.9)
"""
from praxia.experiments.framework import (
    Assignment,
    Experiment,
    ExperimentOutcome,
    ExperimentRegistry,
    ExperimentResults,
    ExperimentStatus,
    Variant,
    assign_variant,
)

__all__ = [
    "Experiment",
    "ExperimentRegistry",
    "ExperimentStatus",
    "Variant",
    "Assignment",
    "ExperimentOutcome",
    "ExperimentResults",
    "assign_variant",
]
