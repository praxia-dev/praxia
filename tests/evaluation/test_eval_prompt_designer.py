"""Tests for praxia.skills.PromptDesignerSkill — meta-prompt → designed prompt."""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from praxia.skills import DesignedPrompt, DesignerResult, PromptDesignerSkill


# --- Stub LLM --------------------------------------------------------------


class StubLLM:
    """Returns a scripted JSON payload — emulates `LLM.complete()`."""

    def __init__(self, payload: dict[str, Any] | str, model: str = "stub/test") -> None:
        self.text = payload if isinstance(payload, str) else json.dumps(payload)
        self.model = model
        self.calls: list[dict[str, Any]] = []

    def complete(self, messages, *, tools=None, response_format="text", **kwargs):  # noqa: ANN001
        self.calls.append({
            "messages": messages,
            "response_format": response_format,
            "kwargs": kwargs,
        })
        return SimpleNamespace(
            text=self.text,
            model=self.model,
            usage={"input_tokens": 10, "output_tokens": 50, "total_tokens": 60},
            raw=None,
            tool_calls=[],
        )


def _payload(name: str = "v1", **overrides: Any) -> dict[str, Any]:
    base = {
        "name": name,
        "system_prompt": "You are a contract reviewer. Output JSON.",
        "user_template": "Review this contract: ${contract_text}",
        "variables": ["contract_text"],
        "examples": [
            {"input": "Sample contract A", "output": '{"risk": 3}', "note": "medium risk"},
            {"input": "Sample contract B", "output": '{"risk": 5}', "note": "high risk"},
        ],
        "rubric": [
            "Output is parsable JSON",
            "Risk score is 1-5 integer",
            "All flags cite contract clauses",
            "No hallucinated parties",
            "Concise reasoning (< 200 words)",
        ],
        "output_format": "json",
        "notes": "JSON-mode design tuned for Claude.",
    }
    base.update(overrides)
    return base


# --- Tests -----------------------------------------------------------------


def test_design_returns_one_variant_by_default():
    llm = StubLLM({"variants": [_payload()]})
    designer = PromptDesignerSkill(llm=llm)
    result = designer.design("Review legal contracts and score risk 1-5")

    assert isinstance(result, DesignerResult)
    assert len(result.prompts) == 1
    p = result.primary
    assert isinstance(p, DesignedPrompt)
    assert p.name == "v1"
    assert "${contract_text}" in p.user_template
    assert "contract_text" in p.variables
    assert len(p.examples) == 2
    assert len(p.rubric) == 5
    assert p.output_format == "json"


def test_design_supports_multiple_variants_for_ab_testing():
    llm = StubLLM({"variants": [
        _payload("strict-v1", notes="strict"),
        _payload("loose-v2", notes="loose"),
        _payload("xml-v3", notes="xml-tagged"),
    ]})
    designer = PromptDesignerSkill(llm=llm)
    result = designer.design(
        "Summarize meetings", target_llm="claude", variants=3,
    )
    assert len(result.prompts) == 3
    assert {p.name for p in result.prompts} == {"strict-v1", "loose-v2", "xml-v3"}


def test_design_propagates_target_llm_into_each_variant():
    llm = StubLLM({"variants": [_payload()]})
    designer = PromptDesignerSkill(llm=llm)
    result = designer.design("test", target_llm="deepseek-reasoner")
    assert result.primary.target_llm == "deepseek-reasoner"


def test_design_rejects_empty_task():
    llm = StubLLM({"variants": [_payload()]})
    designer = PromptDesignerSkill(llm=llm)
    with pytest.raises(ValueError, match="non-empty"):
        designer.design("   ")


def test_design_handles_markdown_fenced_json():
    fenced = "```json\n" + json.dumps({"variants": [_payload()]}) + "\n```"
    llm = StubLLM(fenced)
    designer = PromptDesignerSkill(llm=llm)
    result = designer.design("test")
    assert result.primary.name == "v1"


def test_design_raises_on_invalid_json():
    llm = StubLLM("this is not JSON at all")
    designer = PromptDesignerSkill(llm=llm)
    with pytest.raises(ValueError, match="invalid JSON"):
        designer.design("test")


def test_design_raises_when_variants_missing():
    llm = StubLLM({"foo": "bar"})
    designer = PromptDesignerSkill(llm=llm)
    with pytest.raises(ValueError, match="variants"):
        designer.design("test")


def test_design_raises_when_no_valid_variants():
    llm = StubLLM({"variants": ["not-a-dict", 42]})  # filtered out as non-dicts
    designer = PromptDesignerSkill(llm=llm)
    with pytest.raises(ValueError, match="0 valid variants"):
        designer.design("test")


def test_design_request_to_llm_uses_json_response_format():
    llm = StubLLM({"variants": [_payload()]})
    designer = PromptDesignerSkill(llm=llm)
    designer.design("test")
    call = llm.calls[0]
    assert call["response_format"] == "json"
    # System role + user role with the meta-prompt
    roles = [m["role"] for m in call["messages"]]
    assert roles == ["system", "user"]
    assert "test" in call["messages"][1]["content"]


def test_design_meta_prompt_includes_target_llm_tuning():
    llm = StubLLM({"variants": [_payload()]})
    designer = PromptDesignerSkill(llm=llm)
    designer.design("test", target_llm="claude")
    user_msg = llm.calls[0]["messages"][1]["content"]
    # Claude-specific tuning text should be embedded in the meta-prompt
    assert "XML tags" in user_msg
    assert "<thinking>" in user_msg


def test_design_meta_prompt_includes_deepseek_reasoner_caveat():
    llm = StubLLM({"variants": [_payload()]})
    designer = PromptDesignerSkill(llm=llm)
    designer.design("test", target_llm="deepseek-reasoner")
    user_msg = llm.calls[0]["messages"][1]["content"]
    # R1 has its own reasoning channel — meta-prompt warns against forcing tags
    assert "do NOT force" in user_msg or "reasoning channel" in user_msg


def test_run_skill_protocol_returns_markdown():
    llm = StubLLM({"variants": [_payload()]})
    designer = PromptDesignerSkill(llm=llm)
    md = designer.run("Review legal contracts", target_llm="claude")
    assert isinstance(md, str)
    assert "# v1" in md
    assert "## System prompt" in md
    assert "## User template" in md
    assert "${contract_text}" in md
    assert "## Few-shot examples" in md
    assert "## Evaluation rubric" in md


def test_format_markdown_handles_minimal_prompt():
    p = DesignedPrompt(
        name="bare",
        system_prompt="You are a bot.",
        user_template="Q: ${question}",
    )
    md = PromptDesignerSkill.format_markdown(p)
    assert "# bare" in md
    assert "You are a bot." in md
    # No examples / rubric / variables when empty
    assert "## Few-shot examples" not in md
    assert "## Evaluation rubric" not in md


def test_skill_is_registered_in_skills_registry():
    from praxia.skills import SKILLS
    assert SKILLS.has("prompt_designer")
    cls = SKILLS.get("prompt_designer")
    assert cls is PromptDesignerSkill


def test_skill_manifest_marks_as_utility_not_business():
    from praxia.skills import get_business_skills
    business = {s.manifest.name for s in get_business_skills()}
    # Utility domain should NOT show up under business skills
    assert "prompt_designer" not in business


def test_design_with_include_examples_false_still_parses():
    payload_no_ex = _payload(examples=[])
    llm = StubLLM({"variants": [payload_no_ex]})
    designer = PromptDesignerSkill(llm=llm)
    result = designer.design("test", include_examples=False)
    assert result.primary.examples == []
