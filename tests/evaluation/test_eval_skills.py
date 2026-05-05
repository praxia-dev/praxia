"""Skills + flows + registry — regression scenarios.

Coverage:
    - 6 business skills + manifest validity
    - OutputFormatSkill
    - Custom skill registration via decorator
    - Skill registry promotion / distribution
    - SKILL.md serialization (Claude Skills compatible)
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.evaluation


class TestBusinessSkills:
    def test_six_business_skills_registered(self):
        from praxia.skills import BUSINESS_SKILLS

        assert len(BUSINESS_SKILLS) == 6
        names = {cls.manifest.name for cls in BUSINESS_SKILLS}
        assert names == {
            "investment_analyst",
            "sales_strategist",
            "design_reviewer",
            "purchasing_analyst",
            "patent_analyst",
            "legal_reviewer",
        }

    @pytest.mark.parametrize(
        "skill_module",
        [
            "praxia.skills.business.investment:InvestmentSkill",
            "praxia.skills.business.sales:SalesSkill",
            "praxia.skills.business.design:DesignSkill",
            "praxia.skills.business.purchasing:PurchasingSkill",
            "praxia.skills.business.patent:PatentSkill",
            "praxia.skills.business.legal:LegalSkill",
        ],
    )  # type: ignore[misc]
    def test_each_skill_has_required_metadata(self, skill_module):
        mod_path, cls_name = skill_module.split(":")
        mod = __import__(mod_path, fromlist=[cls_name])
        cls = getattr(mod, cls_name)
        assert cls.manifest.name
        assert cls.manifest.description
        assert cls.manifest.domain
        assert cls.system_prompt
        assert len(cls.system_prompt) > 100, "system_prompt is suspiciously short"

    def test_skill_md_serialization_is_claude_compatible(self):
        from praxia.skills.business import InvestmentSkill

        md = InvestmentSkill().to_skill_md()
        # Frontmatter
        assert md.startswith("---\n")
        # Required Claude Skills fields
        assert "name: investment_analyst" in md
        assert "description:" in md
        assert "domain: investment" in md
        # Body
        assert md.endswith(InvestmentSkill.system_prompt)

    def test_skill_run_smoke(self):
        """Each skill should be instantiable without an LLM key (no LLM call yet)."""
        from praxia.skills.business import (
            DesignSkill,
            InvestmentSkill,
            LegalSkill,
            PatentSkill,
            PurchasingSkill,
            SalesSkill,
        )

        for cls in (
            InvestmentSkill,
            SalesSkill,
            DesignSkill,
            PurchasingSkill,
            PatentSkill,
            LegalSkill,
        ):
            inst = cls()  # no LLM call yet
            agent = inst.as_agent()
            assert agent.name == cls.manifest.name


class TestSkillRegistry:
    def test_registry_lookup_by_name(self):
        from praxia.skills import SKILLS

        assert SKILLS.has("investment_analyst")
        cls = SKILLS.get("investment_analyst")
        assert cls.manifest.name == "investment_analyst"

    def test_unknown_skill_raises_keyerror(self):
        from praxia.skills import SKILLS

        with pytest.raises(KeyError):
            SKILLS.get("nonexistent_skill")

    def test_decorator_registration_works_then_unregister(self):
        from praxia.skills import SKILLS
        from praxia.skills.skill import Skill, SkillManifest

        @SKILLS.register_decorator("eval_temp_skill")
        class TempSkill(Skill):
            manifest = SkillManifest(
                name="eval_temp_skill",
                description="temporary",
                domain="test",
            )
            system_prompt = "..."

        assert SKILLS.has("eval_temp_skill")
        assert SKILLS.get("eval_temp_skill") is TempSkill

        # Cleanup
        SKILLS.unregister("eval_temp_skill")
        assert not SKILLS.has("eval_temp_skill")

    def test_business_skills_excludes_utility_domain(self):
        """OutputFormatSkill (domain=utility) must NOT be in BUSINESS_SKILLS."""
        from praxia.skills import BUSINESS_SKILLS

        domains = {cls.manifest.domain for cls in BUSINESS_SKILLS}
        assert "utility" not in domains

    def test_output_format_skill_in_skills_registry(self):
        """But OutputFormatSkill IS registered in the SKILLS registry (just filtered out)."""
        from praxia.skills import SKILLS

        assert SKILLS.has("output_formatter")


class TestSkillDistribution:
    def test_distribute_to_role_appears_in_list_for_user(self, tmp_storage):
        from praxia.skills.business import InvestmentSkill
        from praxia.skills.registry import SkillRegistry

        reg = SkillRegistry(storage_dir=tmp_storage)
        reg.distribute(InvestmentSkill(), target_roles=["member"])

        member_skills = reg.list_for_user(user_id="bob", role="member")
        assert any(s.name == "investment_analyst" for s in member_skills)

        # Viewer NOT in target roles → doesn't see it
        viewer_skills = reg.list_for_user(user_id="charlie", role="viewer")
        assert not any(s.name == "investment_analyst" for s in viewer_skills)


class TestFlowRegistry:
    def test_three_default_flows_registered(self):
        from praxia.flows import FLOWS

        names = FLOWS.list()
        assert "sales_agent_flow" in names
        assert "logic_checker_flow" in names
        assert "rag_optimization_flow" in names

    def test_flow_by_name(self):
        from praxia.flows import get_flow

        cls = get_flow("sales_agent_flow")
        assert cls.name == "sales_agent_flow"
        assert cls.description
