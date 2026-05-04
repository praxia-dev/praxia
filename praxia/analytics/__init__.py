"""Analytics & dashboards.

Aggregates from existing JSONL sources (audit log, skill usage, personal
memory entries) — no new persistence layer.
"""
from praxia.analytics.dashboard import (
    Dashboard,
    OrgSummary,
    PersonalSummary,
)

__all__ = ["Dashboard", "PersonalSummary", "OrgSummary"]
