"""Six default business-domain skills shipped with AgentLoom.

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
from agentloom.skills.business.investment import InvestmentSkill
from agentloom.skills.business.sales import SalesSkill
from agentloom.skills.business.design import DesignSkill
from agentloom.skills.business.purchasing import PurchasingSkill
from agentloom.skills.business.patent import PatentSkill
from agentloom.skills.business.legal import LegalSkill

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
