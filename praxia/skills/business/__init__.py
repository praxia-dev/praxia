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

These six register themselves with the central `SKILLS` registry — third-party
skills register via the `praxia.skills` entry-point group.
"""
from __future__ import annotations

from praxia.skills.business.investment import InvestmentSkill
from praxia.skills.business.sales import SalesSkill
from praxia.skills.business.design import DesignSkill
from praxia.skills.business.purchasing import PurchasingSkill
from praxia.skills.business.patent import PatentSkill
from praxia.skills.business.legal import LegalSkill


def _register_builtins() -> None:
    """Idempotent registration with the central skills registry."""
    from praxia.skills import SKILLS  # local import avoids circular init

    for cls in (
        InvestmentSkill,
        SalesSkill,
        DesignSkill,
        PurchasingSkill,
        PatentSkill,
        LegalSkill,
    ):
        if not SKILLS.has(cls.manifest.name):
            SKILLS.register(cls.manifest.name, cls)


try:
    _register_builtins()
except ImportError:  # pragma: no cover — only during initial circular-import
    pass


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
