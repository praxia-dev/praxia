"""Skills layer — capability registry + business-domain skills.

Three pieces:
  - registry.py    : Personal & organizational skill catalog with promotion.
  - prompts.py     : Custom prompt store (per-user + admin distribution).
  - business/      : 6 default domain skills (investment / sales / design /
                      purchasing / patent / legal).

Adding a new business skill:

    1. Subclass `Skill` (or use the existing pattern in business/*.py).
    2. Either:
       a. `@SKILLS.register_decorator("my_skill")` for in-tree skills.
       b. Declare an entry-point in your package's pyproject.toml:
          [project.entry-points."praxia.skills"]
          my_skill = "my_pkg.my_skill:MyCustomSkill"

The framework auto-discovers entry-points; **no edit to this file**.
"""
from __future__ import annotations

from praxia.extensions import Registry
from praxia.skills.registry import Skill, SkillRegistry

SKILLS: Registry[Skill] = Registry(name="skill", entry_point_group="praxia.skills")

# Built-in business skills register themselves on import via decorators.
from praxia.skills.business import (  # noqa: E402, F401  (registers via side-effect)
    DesignSkill,
    InvestmentSkill,
    LegalSkill,
    PatentSkill,
    PurchasingSkill,
    SalesSkill,
)


def get_business_skills() -> list[type[Skill]]:
    """Return all built-in + entry-point business skill classes."""
    return [cls for _, cls in SKILLS.items()]


# Backwards-compatible alias — kept so existing tests / examples / docs work.
BUSINESS_SKILLS: list[type[Skill]] = get_business_skills()


__all__ = [
    "Skill",
    "SkillRegistry",
    "SKILLS",
    "InvestmentSkill",
    "SalesSkill",
    "DesignSkill",
    "PurchasingSkill",
    "PatentSkill",
    "LegalSkill",
    "BUSINESS_SKILLS",
    "get_business_skills",
]
