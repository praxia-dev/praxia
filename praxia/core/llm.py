"""Multi-provider LLM abstraction.

Praxia relies on LiteLLM under the hood, which exposes a unified OpenAI-style
chat completion API for every major provider. The model string follows the
LiteLLM convention `<provider>/<model>` (or just the model name when the default
provider is unambiguous).

Supported providers (out of the box, with friendly aliases):

| Provider              | Model string examples                       | Auth env var          |
|-----------------------|---------------------------------------------|-----------------------|
| Anthropic Claude      | anthropic/claude-opus-4-7                   | ANTHROPIC_API_KEY     |
| OpenAI ChatGPT        | openai/gpt-4o, openai/o1                    | OPENAI_API_KEY        |
| Google Gemini         | gemini/gemini-2.0-pro                       | GEMINI_API_KEY        |
| Google Gemma (open)   | ollama/gemma2:9b, vertex_ai/google/gemma-2  | (Ollama / Vertex)     |
| Alibaba Qwen (API)    | dashscope/qwen-max                          | DASHSCOPE_API_KEY     |
| Qwen (local)          | ollama/qwen2.5:14b                          | (Ollama on localhost) |
| DeepSeek              | deepseek/deepseek-chat, deepseek-reasoner   | DEEPSEEK_API_KEY      |
| Mistral               | mistral/mistral-large-latest, codestral     | MISTRAL_API_KEY       |
| xAI Grok              | xai/grok-2-latest                           | XAI_API_KEY           |
| Llama (Groq fast)     | groq/llama-3.3-70b-versatile                | GROQ_API_KEY          |
| Llama (local Ollama)  | ollama/llama3.3:70b                         | (Ollama on localhost) |
| Cohere Command R+     | cohere/command-r-plus                       | COHERE_API_KEY        |
| Perplexity Sonar      | perplexity/llama-3.1-sonar-large-128k-online| PERPLEXITY_API_KEY    |
| Microsoft Phi (local) | ollama/phi3.5:3.8b                          | (Ollama on localhost) |
| OpenRouter            | openrouter/anthropic/claude-3.5-sonnet      | OPENROUTER_API_KEY    |

Any other LiteLLM-supported provider works automatically — just pass the
appropriate model string. The aliases above are convenience shortcuts; the
underlying call goes through LiteLLM in every case.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Literal

def _import_litellm():  # type: ignore[no-untyped-def]
    """Lazy-load LiteLLM only when an actual completion call is made.
    This lets users browse skills/flows without installing the LLM client.

    Side effect: turn on ``litellm.drop_params`` so per-provider quirks
    (GPT-5 only allows ``temperature=1``, o-series doesn't accept
    temperature at all, Anthropic ignores ``response_format``, etc.)
    don't surface as ``UnsupportedParamsError`` to the user. LiteLLM
    silently strips the offending field instead.
    """
    try:
        import litellm  # type: ignore[import-untyped]
        try:
            litellm.drop_params = True
        except Exception:
            pass
        return litellm
    except ImportError as e:  # pragma: no cover - install hint
        raise ImportError(
            "litellm is required to call an LLM. Install with: pip install praxia"
        ) from e


# Friendly aliases — users can write "claude" instead of "anthropic/claude-opus-4-7"
DEFAULT_ALIASES: dict[str, str] = {
    # Anthropic — Claude 4.x family
    "claude": "anthropic/claude-opus-4-7",
    "claude-opus": "anthropic/claude-opus-4-7",
    "claude-sonnet": "anthropic/claude-sonnet-4-6",
    "claude-haiku": "anthropic/claude-haiku-4-5",
    # OpenAI — GPT-5 family + reasoning (o-series)
    "chatgpt": "openai/gpt-5.1",
    "gpt-5.1": "openai/gpt-5.1",
    "gpt-5.1-mini": "openai/gpt-5.1-mini",
    "gpt-5": "openai/gpt-5",
    "gpt-5-mini": "openai/gpt-5-mini",
    "gpt-5-nano": "openai/gpt-5-nano",
    "gpt-4o": "openai/gpt-4o",
    "gpt-4o-mini": "openai/gpt-4o-mini",
    "o4-mini": "openai/o4-mini",
    "o3": "openai/o3",
    "o3-mini": "openai/o3-mini",
    "o1": "openai/o1",
    # Google Gemini — 2.5 (latest) and 2.0 series
    "gemini": "gemini/gemini-2.5-pro",
    "gemini-pro": "gemini/gemini-2.5-pro",
    "gemini-flash": "gemini/gemini-2.5-flash",
    "gemini-2.0-pro": "gemini/gemini-2.0-pro",
    "gemini-2.0-flash": "gemini/gemini-2.0-flash",
    "gemini-1.5-pro": "gemini/gemini-1.5-pro",
    # Alibaba Qwen
    "qwen": "dashscope/qwen-max",
    "qwen-72b": "dashscope/qwen2.5-72b-instruct",
    "qwen-local": "ollama/qwen2.5:14b",
    # Gemma — Google's open-weight family. Local-first by default, cloud
    # variants supported via Vertex AI.
    "gemma": "ollama/gemma2:9b",          # default: local 9B (good size/quality)
    "gemma-2b": "ollama/gemma2:2b",        # tiny / edge
    "gemma-9b": "ollama/gemma2:9b",        # alias for 9B
    "gemma-27b": "ollama/gemma2:27b",      # local 27B (largest open weight)
    "gemma-cloud": "vertex_ai/google/gemma-2-27b-it",  # via Google Vertex AI
    # DeepSeek — Chinese SOTA, very low cost. v3 = chat, R1 = reasoning.
    "deepseek": "deepseek/deepseek-chat",
    "deepseek-reasoner": "deepseek/deepseek-reasoner",
    # Mistral — French OSS-leaning. Large for general, small for cheap, codestral for code.
    "mistral": "mistral/mistral-large-latest",
    "mistral-small": "mistral/mistral-small-latest",
    "codestral": "mistral/codestral-latest",
    # xAI Grok
    "grok": "xai/grok-4",
    "grok-4": "xai/grok-4",
    "grok-3": "xai/grok-3-latest",
    "grok-2": "xai/grok-2-latest",
    # Llama — fastest path is Groq (cloud) or Ollama (local).
    "llama": "groq/llama-3.3-70b-versatile",
    "llama-local": "ollama/llama3.3:70b",
    # Cohere — Command R+ shines on retrieval-augmented enterprise use.
    "command-r": "cohere/command-r-plus",
    # Perplexity — Sonar models do web search internally; useful for research-style agents.
    # New naming: sonar / sonar-pro / sonar-reasoning / sonar-reasoning-pro.
    # The old llama-3.1-sonar-* IDs are deprecated.
    "perplexity": "perplexity/sonar-pro",
    "perplexity-pro": "perplexity/sonar-pro",
    "perplexity-cheap": "perplexity/sonar",
    "perplexity-reasoning": "perplexity/sonar-reasoning-pro",
    # Microsoft Phi — small / efficient, the "edge" companion to Gemma.
    "phi": "ollama/phi3.5:3.8b",
}


# Provider → list of (display_label, full_model_id) for the UI picker.
# Display label is what the user sees in the dropdown; full_model_id is
# what gets stored in session_state and passed to LiteLLM.
LLM_PROVIDERS: dict[str, list[tuple[str, str]]] = {
    "Anthropic": [
        ("Claude Opus 4.7 (most capable)", "anthropic/claude-opus-4-7"),
        ("Claude Sonnet 4.6 (balanced)", "anthropic/claude-sonnet-4-6"),
        ("Claude Haiku 4.5 (fastest, cheapest)", "anthropic/claude-haiku-4-5"),
    ],
    "OpenAI": [
        ("GPT-5.1 (latest, recommended)", "openai/gpt-5.1"),
        ("GPT-5.1 mini", "openai/gpt-5.1-mini"),
        ("GPT-5", "openai/gpt-5"),
        ("GPT-5 mini", "openai/gpt-5-mini"),
        ("GPT-5 nano (cheapest)", "openai/gpt-5-nano"),
        ("GPT-4o", "openai/gpt-4o"),
        ("GPT-4o mini (cheap)", "openai/gpt-4o-mini"),
        ("o4 mini (reasoning)", "openai/o4-mini"),
        ("o3 (reasoning, capable)", "openai/o3"),
        ("o3 mini (reasoning, cheap)", "openai/o3-mini"),
        ("o1 (reasoning)", "openai/o1"),
    ],
    "Google": [
        ("Gemini 2.5 Pro (most capable)", "gemini/gemini-2.5-pro"),
        ("Gemini 2.5 Flash (fast)", "gemini/gemini-2.5-flash"),
        ("Gemini 2.0 Pro", "gemini/gemini-2.0-pro"),
        ("Gemini 2.0 Flash (cheap)", "gemini/gemini-2.0-flash"),
        ("Gemini 1.5 Pro (long context)", "gemini/gemini-1.5-pro"),
    ],
    "DeepSeek": [
        ("DeepSeek V3 (chat)", "deepseek/deepseek-chat"),
        ("DeepSeek R1 (reasoning)", "deepseek/deepseek-reasoner"),
    ],
    "Mistral": [
        ("Mistral Large", "mistral/mistral-large-latest"),
        ("Mistral Small (cheap)", "mistral/mistral-small-latest"),
        ("Codestral (code-tuned)", "mistral/codestral-latest"),
    ],
    "xAI": [
        ("Grok 4 (latest)", "xai/grok-4"),
        ("Grok 3", "xai/grok-3-latest"),
        ("Grok 2", "xai/grok-2-latest"),
    ],
    "Cohere": [
        ("Command R+", "cohere/command-r-plus"),
    ],
    "Groq (fast Llama)": [
        ("Llama 3.3 70B", "groq/llama-3.3-70b-versatile"),
    ],
    "Perplexity (web-augmented)": [
        ("Sonar Pro (web search, recommended)", "perplexity/sonar-pro"),
        ("Sonar (web search, cheaper)", "perplexity/sonar"),
        ("Sonar Reasoning Pro (web + reasoning)", "perplexity/sonar-reasoning-pro"),
        ("Sonar Reasoning (web + reasoning, cheaper)", "perplexity/sonar-reasoning"),
    ],
    "Alibaba Qwen": [
        ("Qwen Max", "dashscope/qwen-max"),
        ("Qwen 2.5 72B", "dashscope/qwen2.5-72b-instruct"),
    ],
    "Local (Ollama)": [
        ("Llama 3.3 70B", "ollama/llama3.3:70b"),
        ("Qwen 2.5 72B", "ollama/qwen2.5:72b"),
        ("Qwen 2.5 14B", "ollama/qwen2.5:14b"),
        ("Gemma 2 27B", "ollama/gemma2:27b"),
        ("Gemma 2 9B", "ollama/gemma2:9b"),
        ("Phi 3.5 (3.8B, edge)", "ollama/phi3.5:3.8b"),
    ],
}


def provider_for_model(model: str) -> str:
    """Find which provider a model id (or alias) belongs to."""
    resolved = DEFAULT_ALIASES.get(model, model)
    for provider, models in LLM_PROVIDERS.items():
        for _, mid in models:
            if mid == resolved:
                return provider
    return "Custom"


@dataclass
class ProviderConfig:
    """Configuration for a specific LLM provider invocation."""

    model: str
    temperature: float = 0.2
    max_tokens: int | None = None
    top_p: float | None = None
    api_key: str | None = None
    api_base: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def resolve_model(self) -> str:
        """Apply default aliases. `claude` -> `anthropic/claude-opus-4-7`."""
        return DEFAULT_ALIASES.get(self.model, self.model)


@dataclass
class LLMResponse:
    text: str
    model: str
    usage: dict[str, int]
    raw: Any
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class LLM:
    """Unified multi-provider LLM client.

    Example:
        llm = LLM("claude")              # alias
        llm = LLM("openai/gpt-4o")       # full
        llm = LLM("ollama/qwen2.5:14b", api_base="http://localhost:11434")

        response = llm.complete([
            {"role": "system", "content": "You are concise."},
            {"role": "user", "content": "Hello!"},
        ])
    """

    def __init__(
        self,
        model: str = "claude",
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        api_key: str | None = None,
        api_base: str | None = None,
        **extra: Any,
    ) -> None:
        self.config = ProviderConfig(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key,
            api_base=api_base,
            extra=extra,
        )

    @property
    def model(self) -> str:
        return self.config.resolve_model()

    @property
    def provider(self) -> str:
        return self.model.split("/", 1)[0] if "/" in self.model else "openai"

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        tools: list[dict[str, Any]] | None = None,
        response_format: Literal["text", "json"] = "text",
        **overrides: Any,
    ) -> LLMResponse:
        """Synchronous completion call. Uses LiteLLM under the hood."""
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": overrides.get("temperature", self.config.temperature),
        }
        if self.config.max_tokens or "max_tokens" in overrides:
            kwargs["max_tokens"] = overrides.get("max_tokens", self.config.max_tokens)
        if self.config.api_key:
            kwargs["api_key"] = self.config.api_key
        if self.config.api_base:
            kwargs["api_base"] = self.config.api_base
        if tools:
            kwargs["tools"] = tools
        if response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}
        kwargs.update(self.config.extra)

        litellm = _import_litellm()
        result = litellm.completion(**kwargs)
        choice = result.choices[0].message
        text = choice.content or ""
        usage = {
            "input_tokens": getattr(result.usage, "prompt_tokens", 0) or 0,
            "output_tokens": getattr(result.usage, "completion_tokens", 0) or 0,
            "total_tokens": getattr(result.usage, "total_tokens", 0) or 0,
        }
        tool_calls: list[dict[str, Any]] = []
        for tc in getattr(choice, "tool_calls", None) or []:
            fn = getattr(tc, "function", None)
            tool_calls.append({
                "id": getattr(tc, "id", None) or "",
                "name": getattr(fn, "name", "") if fn else "",
                "arguments": getattr(fn, "arguments", "") if fn else "",
            })
        return LLMResponse(
            text=text,
            model=self.model,
            usage=usage,
            raw=result,
            tool_calls=tool_calls,
        )

    async def acomplete(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> LLMResponse:
        """Async variant. Mirrors `complete()`."""
        # Delegate to sync inside thread for simplicity. Replace with
        # litellm.acompletion when streaming is implemented.
        import asyncio

        return await asyncio.to_thread(self.complete, messages, **kwargs)

    @staticmethod
    def list_supported_providers() -> list[str]:
        """Return the well-known provider names (LiteLLM supports more)."""
        return [
            "anthropic",
            "openai",
            "gemini",
            "dashscope",  # Alibaba Cloud Qwen API
            "ollama",  # local Qwen / Llama / Mistral / Phi / Gemma
            "openrouter",
            "azure",
            "bedrock",
            "vertex_ai",
            "groq",       # fast Llama / Mixtral inference
            "mistral",    # Mistral cloud API (mistral-large, codestral)
            "cohere",     # Command R+ for enterprise RAG
            "deepseek",   # DeepSeek v3 / R1
            "xai",        # Grok
            "perplexity", # Sonar (web-search-augmented)
            "together_ai",
        ]

    @staticmethod
    def auto_detect() -> str:
        """Pick a sensible default based on which API keys are present.

        Priority order favors quality + ubiquity. Override with
        ``PRAXIA_LOCAL_MODEL=<alias>`` to force a specific local fallback.
        """
        # Tier 1: frontier proprietary
        if os.getenv("ANTHROPIC_API_KEY"):
            return "claude"
        if os.getenv("OPENAI_API_KEY"):
            return "chatgpt"
        if os.getenv("GEMINI_API_KEY"):
            return "gemini"
        # Tier 2: strong proprietary / OSS-friendly cloud APIs
        if os.getenv("DEEPSEEK_API_KEY"):
            return "deepseek"
        if os.getenv("MISTRAL_API_KEY"):
            return "mistral"
        if os.getenv("XAI_API_KEY"):
            return "grok"
        if os.getenv("DASHSCOPE_API_KEY"):
            return "qwen"
        if os.getenv("COHERE_API_KEY"):
            return "command-r"
        if os.getenv("PERPLEXITY_API_KEY"):
            return "perplexity"
        # Tier 3: fast inference of OSS weights
        if os.getenv("GROQ_API_KEY"):
            return "llama"
        if os.getenv("TOGETHERAI_API_KEY"):
            return "llama"
        # Tier 4: local Ollama. PRAXIA_LOCAL_MODEL lets the operator opt
        # into Gemma / Phi / Llama instead of the default Qwen.
        local = os.getenv("PRAXIA_LOCAL_MODEL", "qwen-local")
        return local if local in DEFAULT_ALIASES else "qwen-local"
