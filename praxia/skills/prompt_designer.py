"""PromptDesignerSkill — turn a one-line task description into a production-grade prompt.

A user describes what they want to accomplish in plain language; this skill
returns a `DesignedPrompt` with:

    - a polished system prompt
    - a user-message template with ${variable} placeholders
    - 2-3 few-shot examples
    - a 5-criteria evaluation rubric for grading future runs

Per-LLM tuning is applied based on `target_llm` so the same task description
produces XML-tag-heavy output for Claude, JSON-mode + role-segmented output
for OpenAI, "thinking-tag-respectful" output for DeepSeek-R1, and so on.

Designed to compose with the rest of Praxia:

    - Output can be persisted via `praxia.skills.prompts.PromptStore.save_personal`
      so individual users build their library, and effective prompts auto-promote
      to the org via the standard memory-cycling pipeline.
    - When `variants > 1`, the skill emits multiple candidate prompts that you
      can A/B-test through `praxia.experiments`.

Example:

    from praxia.skills import PromptDesignerSkill

    designer = PromptDesignerSkill()
    out = designer.design(
        task="Have in-house legal score contract risk on a 5-point scale",
        target_llm="claude",
        output_format="json",
        include_examples=True,
        constraint_level="strict",
    )
    print(out.system_prompt)     # production-grade system prompt
    print(out.user_template)     # with ${contract_text} placeholders
    for ex in out.examples:
        print(ex.input, "→", ex.output)
    print(out.rubric)            # 5-criterion evaluation rubric
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from praxia.skills.skill import Skill, SkillManifest


# --- Result types ----------------------------------------------------------


@dataclass
class FewShotExample:
    """A single (input, output) pair to include in the prompt as an example."""
    input: str
    output: str
    note: str = ""


@dataclass
class DesignedPrompt:
    """One design produced by `PromptDesignerSkill.design()`.

    Multiple `DesignedPrompt`s come back inside a `DesignerResult` when
    `variants > 1` — feed them to `praxia.experiments` to A/B-test.
    """
    name: str
    system_prompt: str
    user_template: str
    variables: list[str] = field(default_factory=list)
    examples: list[FewShotExample] = field(default_factory=list)
    rubric: list[str] = field(default_factory=list)
    target_llm: str = ""
    output_format: str = "markdown"
    notes: str = ""


@dataclass
class DesignerResult:
    """Returned by `design()`. Has at least one prompt; more if `variants > 1`."""
    prompts: list[DesignedPrompt]
    raw_text: str = ""        # raw model output (debugging)
    usage: dict[str, int] = field(default_factory=dict)

    @property
    def primary(self) -> DesignedPrompt:
        return self.prompts[0]


# --- Per-LLM tuning ---------------------------------------------------------
# Selected by `target_llm` (or auto-inferred from `LLM.provider`). The string
# is injected into the meta-prompt so the generated prompt uses idioms the
# target model responds well to.

_LLM_TUNING = {
    "claude": (
        "Use XML tags (<task>, <context>, <constraints>, <output_format>) to "
        "delimit sections. Encourage step-by-step reasoning inside <thinking> "
        "tags before the final answer. Claude responds well to clear role "
        "framing and explicit examples."
    ),
    "openai": (
        "Use a role-segmented prompt (system / user). Prefer JSON-mode-friendly "
        "output schemas. Be explicit about formatting; OpenAI models tend to "
        "over-elaborate without strict constraints."
    ),
    "gemini": (
        "Front-load the most important instructions; Gemini's 1M-token context "
        "tolerates examples but the first ~2000 tokens drive behavior. "
        "Markdown output is well-supported."
    ),
    "deepseek": (
        "DeepSeek-V3 follows OpenAI-style instructions well. For "
        "deepseek-reasoner (R1), keep the system message *short* and let the "
        "model think — do NOT force it into <thinking> tags, it has its own "
        "reasoning channel."
    ),
    "mistral": (
        "Mistral models prefer concise system prompts (under 300 tokens). "
        "Codestral excels at code; for natural language stick to mistral-large."
    ),
    "xai": (
        "Grok responds well to direct, no-preamble instructions. Avoid "
        "lengthy role-play; state the task and expected output in the first "
        "two sentences."
    ),
    "cohere": (
        "Cohere Command R+ is tuned for retrieval-augmented use. If your task "
        "involves source documents, structure the prompt as <Documents> + "
        "<Question>."
    ),
    "perplexity": (
        "Perplexity Sonar models are search-augmented. Don't ask for "
        "fact-recall from training data — ask the model to answer based on "
        "what it retrieves."
    ),
    "groq": (
        "Llama 3.3 70B via Groq prefers explicit step lists over implicit "
        "reasoning. Numbered instructions work better than prose."
    ),
    "ollama": (
        "Local Ollama models (Llama / Phi / Gemma) need very direct "
        "instructions and shorter context. Trim long system prompts."
    ),
    "_default": (
        "Use clear role framing (system message), enumerated constraints, and "
        "explicit output format. Include 2-3 few-shot examples for non-trivial "
        "tasks."
    ),
}


def _tuning_for(target_llm: str) -> str:
    """Pick a tuning hint based on alias or `provider/model` prefix."""
    if not target_llm:
        return _LLM_TUNING["_default"]
    key = target_llm.lower()
    # Direct alias match (e.g. "claude" / "deepseek" / "perplexity")
    if key in _LLM_TUNING:
        return _LLM_TUNING[key]
    # Provider prefix from "<provider>/<model>"
    provider = key.split("/", 1)[0]
    if provider in _LLM_TUNING:
        return _LLM_TUNING[provider]
    # Aliases that map to a known provider
    alias_provider = {
        "claude-sonnet": "claude", "claude-haiku": "claude",
        "chatgpt": "openai", "gpt-4o": "openai", "o1": "openai",
        "gemini-flash": "gemini", "gemma": "ollama",
        "qwen": "_default", "qwen-72b": "_default", "qwen-local": "ollama",
        "deepseek-reasoner": "deepseek",
        "mistral-small": "mistral", "codestral": "mistral",
        "grok": "xai",
        "command-r": "cohere",
        "llama": "groq", "llama-local": "ollama",
        "phi": "ollama",
    }
    return _LLM_TUNING.get(alias_provider.get(key, "_default"), _LLM_TUNING["_default"])


# --- Meta-prompt -----------------------------------------------------------

_META_PROMPT_TEMPLATE = """You are a senior prompt engineer. Your job is to take a user's plain-language
description of what they want a downstream LLM to do, and produce a production-grade
prompt design they can paste directly into their application.

# User's task description
{task}

# Target LLM tuning hint
{tuning}

# Constraints
- Output format requested: {output_format}
- Constraint level: {constraint_level}  (strict = anti-hallucination guards / loose = creativity-friendly)
- Number of variants to produce: {variants}
- Include few-shot examples: {include_examples}

# What to produce

For EACH of the {variants} variant(s), return a JSON object with these fields:

    name              short identifier, kebab-case (e.g. "legal-risk-eval-v1")
    system_prompt     the system message to send to the target LLM, polished
    user_template     the user message template with ${{variable}} placeholders
                      where the caller substitutes actual values (e.g. ${{contract_text}})
    variables         list of placeholder names found in user_template
    examples          list of {{"input": ..., "output": ..., "note": ...}}
                      (2-3 entries; empty if include_examples=false)
    rubric            list of 5 short evaluation criteria, each one line, suitable
                      for grading future outputs against this prompt
    output_format     one of "markdown" / "text" / "json" / "xml" / "html" /
                      "docx" / "pptx" (matching what you encoded into
                      system_prompt)
    notes             one sentence explaining the design choice for this variant

Wrap the array of variants in: {{"variants": [...]}}.

Do NOT include commentary outside the JSON object.

# Quality bar

- Use the target LLM's native idioms (the tuning hint above explains what works for it).
- Avoid filler phrases like "you are a helpful assistant".
- For strict constraint level, include explicit refusal conditions and grounding requirements.
- For json output_format, the system_prompt MUST instruct the model to return parsable JSON
  and define the schema.
- For markdown output_format, the system_prompt should instruct the model to use
  proper heading hierarchy (#, ##, ###) and to keep prose tight + scannable.
- For html output_format, the system_prompt should instruct the model to produce
  semantic HTML (h1/h2/p/ul/li/table) — no inline styles, no <script>.
- For docx output_format, the system_prompt should instruct the model to
  produce structured Markdown with a clear `# Title`, `## Section`, `### Subsection`
  hierarchy plus tables (Markdown pipe syntax) where data is tabular. Praxia's
  exporter converts this Markdown into a Word document.
- For pptx output_format, the system_prompt should instruct the model to produce
  Markdown structured as a slide deck: a top `# Deck Title` line, then one
  `## Slide N — <slide title>` per slide, with 3-6 bullet points per slide
  (no paragraphs). Praxia's pptx exporter splits on `##` headings.
- The user_template MUST use ${{variable}}-style placeholders only — no f-string, no {{}}.

Begin.
"""


# --- Skill -----------------------------------------------------------------


class PromptDesignerSkill(Skill):
    """Turn a one-line task description into a polished prompt template.

    Composes with the rest of Praxia — the result can be saved to PromptStore
    or A/B-tested via the experiments framework.
    """

    manifest = SkillManifest(
        name="prompt_designer",
        description=(
            "Take a plain-language task description and produce a "
            "production-grade prompt template (system + user + examples + "
            "rubric) tuned for the target LLM."
        ),
        version="0.1.0",
        domain="utility",
        tags=["prompt-engineering", "meta-prompt", "design", "templating"],
    )

    system_prompt = (
        "You are a senior prompt engineer. The user will describe a task; "
        "you respond with a production-grade prompt design as JSON."
    )

    # --- Public API -------------------------------------------------------

    def design(
        self,
        task: str,
        *,
        target_llm: str = "",
        output_format: str = "markdown",
        include_examples: bool = True,
        constraint_level: str = "strict",
        variants: int = 1,
        max_tokens: int = 4096,
    ) -> DesignerResult:
        """Generate one or more `DesignedPrompt`s for `task`.

        Args:
            task: free-text description of what the downstream LLM should do.
            target_llm: alias or `provider/model` hint (e.g. "claude", "openai/gpt-4o").
                Defaults to whatever `self.llm` is configured for.
            output_format: "markdown" (default) / "text" / "json" / "xml" /
                "html" / "docx" / "pptx". The latter three hint that the
                downstream LLM should produce structured Markdown that
                converts cleanly to that target document format via Praxia's
                exporter pipeline.
            include_examples: when True, generate 2-3 few-shot examples.
            constraint_level: "strict" (anti-hallucination) or "loose" (creativity).
            variants: how many candidate prompts to generate (>=1).
                When >1, feed them to `praxia.experiments` for A/B testing.
            max_tokens: cap on the meta-prompt's output (default 4096).
        """
        if not task or not task.strip():
            raise ValueError("`task` must be a non-empty description.")
        variants = max(1, int(variants))
        target_llm = target_llm or getattr(self.llm, "model", "")
        tuning = _tuning_for(target_llm)

        prompt = _META_PROMPT_TEMPLATE.format(
            task=task.strip(),
            tuning=tuning,
            output_format=output_format,
            constraint_level=constraint_level,
            variants=variants,
            include_examples=str(include_examples).lower(),
        )

        response = self.llm.complete(
            [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            response_format="json",
            max_tokens=max_tokens,
        )

        designed = self._parse(
            response.text,
            target_llm=target_llm,
            output_format=output_format,
        )
        return DesignerResult(
            prompts=designed,
            raw_text=response.text,
            usage=response.usage,
        )

    # Convenience: most callers want the system_prompt as a string.
    def run(self, user_input: str, **inputs: Any) -> str:
        """Skill-protocol entrypoint. Returns a Markdown view of the primary design."""
        result = self.design(
            user_input,
            target_llm=str(inputs.get("target_llm", "")),
            output_format=str(inputs.get("output_format", "text")),
            include_examples=bool(inputs.get("include_examples", True)),
            constraint_level=str(inputs.get("constraint_level", "strict")),
            variants=int(inputs.get("variants", 1)),
        )
        return self.format_markdown(result.primary)

    @staticmethod
    def format_markdown(prompt: DesignedPrompt) -> str:
        """Render a `DesignedPrompt` as a human-readable Markdown block."""
        lines: list[str] = [
            f"# {prompt.name}",
            "",
            f"> Target LLM: `{prompt.target_llm or 'any'}`  · Output: `{prompt.output_format}`",
            "",
            "## System prompt",
            "",
            "```",
            prompt.system_prompt.rstrip(),
            "```",
            "",
            "## User template",
            "",
            "```",
            prompt.user_template.rstrip(),
            "```",
        ]
        if prompt.variables:
            lines += [
                "",
                "## Variables",
                "",
                *[f"- `${{{v}}}`" for v in prompt.variables],
            ]
        if prompt.examples:
            lines += ["", "## Few-shot examples", ""]
            for i, ex in enumerate(prompt.examples, 1):
                lines += [
                    f"### Example {i}",
                    "",
                    "**Input:**",
                    "",
                    "```",
                    ex.input.rstrip(),
                    "```",
                    "",
                    "**Output:**",
                    "",
                    "```",
                    ex.output.rstrip(),
                    "```",
                ]
                if ex.note:
                    lines += ["", f"_Note: {ex.note}_"]
                lines += [""]
        if prompt.rubric:
            lines += ["", "## Evaluation rubric", "", *[f"- {r}" for r in prompt.rubric]]
        if prompt.notes:
            lines += ["", "## Design notes", "", prompt.notes]
        return "\n".join(lines)

    # --- Internals --------------------------------------------------------

    def _parse(
        self,
        raw: str,
        *,
        target_llm: str,
        output_format: str,
    ) -> list[DesignedPrompt]:
        """Parse the meta-prompt's JSON response into `DesignedPrompt`s."""
        text = self._extract_json(raw)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"meta-prompt returned invalid JSON: {exc}. Raw output (truncated): "
                f"{raw[:500]!r}"
            ) from exc
        variants_data = data.get("variants") if isinstance(data, dict) else None
        if not isinstance(variants_data, list) or not variants_data:
            raise ValueError(
                "meta-prompt JSON missing required 'variants' array. "
                f"Got keys: {list(data.keys()) if isinstance(data, dict) else type(data).__name__}"
            )
        out: list[DesignedPrompt] = []
        for i, v in enumerate(variants_data):
            if not isinstance(v, dict):
                continue
            examples_data = v.get("examples") or []
            examples = [
                FewShotExample(
                    input=str(e.get("input", "")),
                    output=str(e.get("output", "")),
                    note=str(e.get("note", "")),
                )
                for e in examples_data if isinstance(e, dict)
            ]
            out.append(DesignedPrompt(
                name=str(v.get("name") or f"variant-{i + 1}"),
                system_prompt=str(v.get("system_prompt") or ""),
                user_template=str(v.get("user_template") or ""),
                variables=[str(x) for x in (v.get("variables") or []) if x],
                examples=examples,
                rubric=[str(x) for x in (v.get("rubric") or []) if x],
                target_llm=target_llm,
                output_format=str(v.get("output_format") or output_format),
                notes=str(v.get("notes") or ""),
            ))
        if not out:
            raise ValueError("meta-prompt produced 0 valid variants.")
        return out

    @staticmethod
    def _extract_json(text: str) -> str:
        """Pull the JSON object out of the model's response.

        LLMs sometimes wrap JSON in markdown fences or prose. Be lenient.
        """
        text = text.strip()
        # Strip ```json ... ``` fences
        fence = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
        if fence:
            return fence.group(1).strip()
        # Otherwise return as-is (json.loads will raise if it's not valid)
        return text
