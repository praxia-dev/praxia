"""Skills layer — capability registry + business-domain skills.

Two halves:
  - registry.py  : Personal & organizational skill registry with promotion.
  - business/    : 6 default domain skills (investment / sales / design /
                    purchasing / patent / legal).
"""
from praxia.skills.registry import Skill, SkillRegistry
from praxia.skills.business import (
    DesignSkill,
    InvestmentSkill,
    LegalSkill,
    PatentSkill,
    PurchasingSkill,
    SalesSkill,
    BUSINESS_SKILLS,
)

__all__ = [
    "Skill",
    "SkillRegistry",
    "InvestmentSkill",
    "SalesSkill",
    "DesignSkill",
    "PurchasingSkill",
    "PatentSkill",
    "LegalSkill",
    "BUSINESS_SKILLS",
]
