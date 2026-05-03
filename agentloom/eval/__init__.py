"""Evaluation utilities — hallucination detection, retrieval relevance, etc.

These are intentionally small helpers; full Eval coverage is a Phase 2 goal
(track progress in docs/roadmap.md).
"""
from agentloom.eval.hallucination import HallucinationCheck, check_hallucination
from agentloom.eval.metrics import recall_at_k, retrieval_precision

__all__ = [
    "HallucinationCheck",
    "check_hallucination",
    "recall_at_k",
    "retrieval_precision",
]
