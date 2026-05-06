"""Multi-provider LLM abstraction.

Praxia relies on LiteLLM under the hood, which exposes a unified OpenAI-style
chat completion API for every major provider. The model string follows the
LiteLLM convention `<provider>/<model>` (or just the model name when the default
provider is unambiguous).

Supported providers (out of the box):

| Provider           | Model string examples                    | Auth env var          |
|--------------------|------------------------------------------|-----------------------|
| Anthropic Claude   | anthropic/claude-opus-4-7                | ANTHROPIC_API_KEY     |
| OpenAI ChatGPT     | openai/gpt-4o, openai/o1                 | OPENAI_API_KEY        |
| Google Gemini      | gemini/gemini-2.0-pro                    | GEMINI_API_KEY        |
| Alibaba Qwen (API) | dashscope/qwen-max, dashscope/qwen2.5-72b| DASHSCOPE_API_KEY     |
| Qwen (local)       | ollama/qwen2.5:72b                       | (Ollama on localhost) |
| OpenRouter         | openrouter/anthropic/claude-3.5-sonnet   | OPENROUTER_API_KEY    |

Any other LiteLLM-supported provider works automatically — just pass the
appropriate model string.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Literal

def _import_litellm():  # type: ignore[no-untyped-def]
    """Lazy-load LiteLLM only when an actual completion call is made.
    This lets users browse skills/flows without installing the LLM client.
    """
    try:
        import litellm  # type: ignore[import-untyped]
        return litellm
    except ImportError as e:  # pragma: no cover - install hint
        raise ImportError(
            "litellm is required to call an LLM. Install with: pip install praxia"
        ) from e


# Friendly aliases — users can write "claude" instead of "anthropic/claude-opus-4-7"
DEFAULT_ALIASES: dict[str, str] = {
    "claude": "anthropic/claude-opus-4-7",
    "claude-sonnet": "anthropic/claude-sonnet-4-6",
    "claude-haiku": "anthropic/claude-haiku-4-5-20251001",
    "chatgpt": "openai/gpt-4o",
    "gpt-4o": "openai/gpt-4o",
    "o1": "openai/o1",
    "gemini": "gemini/gemini-2.0-pro",
    "gemini-flash": "gemini/gemini-2.0-flash",
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
}


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
            "ollama",  # local Qwen / Llama / Mistral
            "openrouter",
            "azure",
            "bedrock",
            "vertex_ai",
            "groq",
            "mistral",
            "cohere",
        ]

    @staticmethod
    def auto_detect() -> str:
        """Pick a sensible default based on which API keys are present."""
        if os.getenv("ANTHROPIC_API_KEY"):
            return "claude"
        if os.getenv("OPENAI_API_KEY"):
            return "chatgpt"
        if os.getenv("GEMINI_API_KEY"):
            return "gemini"
        if os.getenv("DASHSCOPE_API_KEY"):
            return "qwen"
        # Last resort: pick a local Ollama model. PRAXIA_LOCAL_MODEL lets the
        # operator opt into Gemma instead of the default Qwen.
        local = os.getenv("PRAXIA_LOCAL_MODEL", "qwen-local")
        return local if local in DEFAULT_ALIASES else "qwen-local"
