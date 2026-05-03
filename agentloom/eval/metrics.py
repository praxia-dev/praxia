"""Lightweight retrieval-quality metrics."""
from __future__ import annotations

from collections.abc import Iterable


def recall_at_k(retrieved_ids: Iterable[str], gold_ids: Iterable[str], k: int) -> float:
    retrieved = list(retrieved_ids)[:k]
    gold = set(gold_ids)
    if not gold:
        return 0.0
    hits = sum(1 for r in retrieved if r in gold)
    return hits / len(gold)


def retrieval_precision(retrieved_ids: Iterable[str], gold_ids: Iterable[str]) -> float:
    retrieved = list(retrieved_ids)
    if not retrieved:
        return 0.0
    gold = set(gold_ids)
    hits = sum(1 for r in retrieved if r in gold)
    return hits / len(retrieved)
