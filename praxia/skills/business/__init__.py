"""Six default business-domain skills shipped with Praxia.

| Skill          | Domain          | Use cases                                  |
|----------------|-----------------|--------------------------------------------|
| InvestmentSkill| 投資            | Equity research, portfolio analysis        |
| SalesSkill     | 営業            | Account research, proposal drafting        |
| DesignSkill    | 設計            | System design review, requirements eng.    |
| PurchasingSkill| 購買            | Supplier evaluation, RFQ analysis          |
| PatentSkill    | 特許            | Prior-art search, claims drafting          |
| LegalSkill     | 法務            | Contract review, compliance checks         |

Each skill ships with a battle-tested system prompt, can be invoked one-shot
via `.run(query)`, embedded in a Flow via `.as_agent()`, or registered into
the SkillRegistry for organizational sharing.
"""
from praxia.skills.business.investment import InvestmentSkill
from praxia.skills.business.sales import SalesSkill
from praxia.skills.business.design import DesignSkill
from praxia.skills.business.purchasing import PurchasingSkill
from praxia.skills.business.patent import PatentSkill
from praxia.skills.business.legal import LegalSkill

BUSINESS_SKILLS = [
    InvestmentSkill,
    SalesSkill,
    DesignSkill,
    PurchasingSkill,
    PatentSkill,
    LegalSkill,
]

__all__ = [
    "InvestmentSkill",
    "SalesSkill",
    "DesignSkill",
    "PurchasingSkill",
    "PatentSkill",
    "LegalSkill",
    "BUSINESS_SKILLS",
]
