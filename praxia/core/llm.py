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

    Side effects:
      - ``litellm.drop_params = True`` — silently drop params the model
        rejects (temperature for o-series, etc.).
      - ``litellm.modify_params = True`` — let LiteLLM rename params
        between providers (e.g. ``max_tokens`` → ``max_completion_tokens``
        when the target model needs it).
    """
    try:
        import litellm  # type: ignore[import-untyped]
        try:
            litellm.drop_params = True
            litellm.modify_params = True
        except Exception:
            pass
        return litellm
    except ImportError as e:  # pragma: no cover - install hint
        raise ImportError(
            "litellm is required to call an LLM. Install with: pip install praxia"
        ) from e


# Friendly aliases — users can write "claude" instead of "anthropic/claude-opus-4-7"
# (Verified against vendor docs / Wikipedia, May 2026.)
DEFAULT_ALIASES: dict[str, str] = {
    # Anthropic — Claude 4.x family. Opus 4.7 (Apr 16 2026), Sonnet 4.6
    # (Feb 17 2026), Haiku 4.5 (Oct 15 2025) are the active stable
    # releases per Anthropic's lineup page.
    "claude": "anthropic/claude-opus-4-7",
    "claude-opus": "anthropic/claude-opus-4-7",
    "claude-opus-4-7": "anthropic/claude-opus-4-7",
    "claude-opus-4-6": "anthropic/claude-opus-4-6",
    "claude-sonnet": "anthropic/claude-sonnet-4-6",
    "claude-sonnet-4-6": "anthropic/claude-sonnet-4-6",
    "claude-haiku": "anthropic/claude-haiku-4-5",
    "claude-haiku-4-5": "anthropic/claude-haiku-4-5",
    # OpenAI — GPT-5.x family. 5.5 released Apr 23 2026 (codename "Spud")
    # with Thinking + Pro variants. 5.4 released Mar 5 2026 with mini/nano
    # added Mar 17. 5.3-Codex is a code-specialised variant. 5.2 / 5.1
    # remain available.
    "chatgpt": "openai/gpt-5.5",
    "gpt-5.5": "openai/gpt-5.5",
    "gpt-5.5-thinking": "openai/gpt-5.5-thinking",
    "gpt-5.5-pro": "openai/gpt-5.5-pro",
    "gpt-5.4": "openai/gpt-5.4",
    "gpt-5.4-mini": "openai/gpt-5.4-mini",
    "gpt-5.4-nano": "openai/gpt-5.4-nano",
    "gpt-5.3-codex": "openai/gpt-5.3-codex",
    "gpt-5.2": "openai/gpt-5.2",
    "gpt-5.1": "openai/gpt-5.1",
    "gpt-5": "openai/gpt-5",
    "gpt-5-mini": "openai/gpt-5-mini",
    "gpt-5-nano": "openai/gpt-5-nano",
    "gpt-4.5": "openai/gpt-4.5",
    "gpt-4.1": "openai/gpt-4.1",
    "gpt-4o": "openai/gpt-4o",
    "gpt-4o-mini": "openai/gpt-4o-mini",
    "o4-mini": "openai/o4-mini",
    "o3": "openai/o3",
    "o3-mini": "openai/o3-mini",
    "o1": "openai/o1",
    # Google Gemini — Gemini 3.1 Pro (Feb 19 2026) is the current
    # flagship; 3.1 Flash Lite (Mar 3 2026) is the cheap tier.
    "gemini": "gemini/gemini-3.1-pro",
    "gemini-pro": "gemini/gemini-3.1-pro",
    "gemini-3-pro": "gemini/gemini-3-pro",
    "gemini-flash-lite": "gemini/gemini-3.1-flash-lite",
    "gemini-2.5-pro": "gemini/gemini-2.5-pro",
    "gemini-2.5-flash": "gemini/gemini-2.5-flash",
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
    # DeepSeek — V4 (Pro/Flash) released Apr 24 2026. V3.2 + V3.2-Speciale
    # (reasoning) still available.
    "deepseek": "deepseek/deepseek-v4",
    "deepseek-v4": "deepseek/deepseek-v4",
    "deepseek-v4-pro": "deepseek/deepseek-v4-pro",
    "deepseek-v4-flash": "deepseek/deepseek-v4-flash",
    "deepseek-v3.2": "deepseek/deepseek-v3.2",
    "deepseek-reasoner": "deepseek/deepseek-v3.2-speciale",
    # Mistral — Mistral Large 3 (Dec 2 2025), Medium 3.5 (Apr 30 2026),
    # Small 4 (Mar 2026), Magistral 1.2 (reasoning), Devstral 2 (code).
    "mistral": "mistral/mistral-large-3",
    "mistral-large": "mistral/mistral-large-3",
    "mistral-large-3": "mistral/mistral-large-3",
    "mistral-medium": "mistral/mistral-medium-3.5",
    "mistral-medium-3.5": "mistral/mistral-medium-3.5",
    "mistral-small": "mistral/mistral-small-4",
    "mistral-small-4": "mistral/mistral-small-4",
    "magistral": "mistral/magistral-medium-1.2",
    "codestral": "mistral/codestral-2508",
    "devstral": "mistral/devstral-medium-2",
    # xAI Grok — 4.1 (Nov 17-18 2025) is current. Grok 4.1 Fast is the
    # speed variant; Grok Code Fast 1 is for code.
    "grok": "xai/grok-4.1",
    "grok-4.1": "xai/grok-4.1",
    "grok-4.1-fast": "xai/grok-4.1-fast",
    "grok-4-heavy": "xai/grok-4-heavy",
    "grok-4-fast": "xai/grok-4-fast",
    "grok-4": "xai/grok-4",
    "grok-3": "xai/grok-3",
    "grok-code": "xai/grok-code-fast-1",
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
        ("Claude Opus 4.7 (latest, recommended)", "anthropic/claude-opus-4-7"),
        ("Claude Opus 4.6", "anthropic/claude-opus-4-6"),
        ("Claude Sonnet 4.6 (balanced)", "anthropic/claude-sonnet-4-6"),
        ("Claude Sonnet 4.5", "anthropic/claude-sonnet-4-5"),
        ("Claude Haiku 4.5 (fastest, cheapest)", "anthropic/claude-haiku-4-5"),
    ],
    "OpenAI": [
        ("GPT-5.5 (latest, recommended)", "openai/gpt-5.5"),
        ("GPT-5.5 Thinking", "openai/gpt-5.5-thinking"),
        ("GPT-5.5 Pro", "openai/gpt-5.5-pro"),
        ("GPT-5.4", "openai/gpt-5.4"),
        ("GPT-5.4 mini", "openai/gpt-5.4-mini"),
        ("GPT-5.4 nano (cheapest)", "openai/gpt-5.4-nano"),
        ("GPT-5.3 Codex (code-tuned)", "openai/gpt-5.3-codex"),
        ("GPT-5.2", "openai/gpt-5.2"),
        ("GPT-5.1", "openai/gpt-5.1"),
        ("GPT-5", "openai/gpt-5"),
        ("GPT-4o", "openai/gpt-4o"),
        ("GPT-4o mini", "openai/gpt-4o-mini"),
        ("o4 mini (reasoning)", "openai/o4-mini"),
        ("o3 (reasoning, capable)", "openai/o3"),
        ("o3 mini (reasoning, cheap)", "openai/o3-mini"),
        ("o1 (reasoning)", "openai/o1"),
    ],
    "Azure OpenAI Service": [
        # 'azure/<deployment-name>' uses AZURE_API_KEY +
        # AZURE_API_BASE + AZURE_API_VERSION (we also mirror to the
        # AZURE_OPENAI_* names so the openai SDK is happy).
        # Deployment names are user-defined per Azure resource —
        # these templates assume a deployment named like the model.
        # Pick Provider=Custom if your deployment is named differently.
        ("Azure deployment: gpt-5.5", "azure/gpt-5.5"),
        ("Azure deployment: gpt-5.4", "azure/gpt-5.4"),
        ("Azure deployment: gpt-5.1", "azure/gpt-5.1"),
        ("Azure deployment: gpt-5", "azure/gpt-5"),
        ("Azure deployment: gpt-4o", "azure/gpt-4o"),
        ("Azure deployment: gpt-4o-mini", "azure/gpt-4o-mini"),
        ("Azure deployment: o4-mini", "azure/o4-mini"),
        ("Azure deployment: o3", "azure/o3"),
    ],
    "Azure AI Foundry (Inference)": [
        # 'azure_ai/<model-name>' uses AZURE_AI_API_KEY +
        # AZURE_AI_API_BASE — completely separate from Azure OpenAI
        # Service above. Use this when your Foundry endpoint hosts
        # non-OpenAI models (Mistral / Llama / Phi / Cohere /
        # DeepSeek / your own custom deployment). The model name
        # must match what's deployed at your Foundry endpoint —
        # check Foundry Studio → your endpoint → 'Deployment name'.
        ("Foundry: Mistral Large", "azure_ai/Mistral-large"),
        ("Foundry: Llama 3.3 70B", "azure_ai/Llama-3.3-70B-Instruct"),
        ("Foundry: Phi-3 medium 128k", "azure_ai/Phi-3-medium-128k-instruct"),
        ("Foundry: Cohere Command R+", "azure_ai/Cohere-command-r-plus"),
        ("Foundry: DeepSeek-V3", "azure_ai/DeepSeek-V3"),
    ],
    "AWS Bedrock (Anthropic Claude)": [
        # Bedrock uses anthropic.<model>-<version> prefix and AWS auth
        # (AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY + AWS_REGION).
        # The exact ":v1:0" suffix and inference-profile prefix
        # (us./eu./apac.) varies by region/account — check the
        # 'Available models' page in your Bedrock console. Use
        # Provider=Custom if your deployment uses a region-prefixed
        # inference profile (e.g. bedrock/us.anthropic.claude-opus-4-7-v1:0).
        ("Claude Opus 4.7 (Bedrock)", "bedrock/anthropic.claude-opus-4-7-v1:0"),
        ("Claude Sonnet 4.6 (Bedrock)", "bedrock/anthropic.claude-sonnet-4-6-v1:0"),
        ("Claude Haiku 4.5 (Bedrock)", "bedrock/anthropic.claude-haiku-4-5-v1:0"),
        ("Claude 3.5 Sonnet v2 (Bedrock)", "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0"),
        ("Claude 3.5 Haiku (Bedrock)", "bedrock/anthropic.claude-3-5-haiku-20241022-v1:0"),
    ],
    "AWS Bedrock (other)": [
        # Non-Anthropic models hosted on Bedrock — same AWS IAM auth.
        ("Llama 3.3 70B (Bedrock)", "bedrock/meta.llama3-3-70b-instruct-v1:0"),
        ("Mistral Large (Bedrock)", "bedrock/mistral.mistral-large-2407-v1:0"),
        ("Cohere Command R+ (Bedrock)", "bedrock/cohere.command-r-plus-v1:0"),
        ("Amazon Nova Pro", "bedrock/amazon.nova-pro-v1:0"),
        ("Amazon Nova Lite", "bedrock/amazon.nova-lite-v1:0"),
    ],
    "Google Vertex AI": [
        # Requires VERTEX_PROJECT + VERTEX_LOCATION +
        # GOOGLE_APPLICATION_CREDENTIALS. Both Gemini and
        # Anthropic-on-Vertex deployments are reachable.
        ("Gemini 3.1 Pro (Vertex)", "vertex_ai/gemini-3.1-pro"),
        ("Gemini 3 Pro (Vertex)", "vertex_ai/gemini-3-pro"),
        ("Gemini 2.5 Pro (Vertex)", "vertex_ai/gemini-2.5-pro"),
        ("Claude Opus 4.7 (Vertex)", "vertex_ai/claude-opus-4-7"),
        ("Claude Sonnet 4.6 (Vertex)", "vertex_ai/claude-sonnet-4-6"),
        ("Claude Haiku 4.5 (Vertex)", "vertex_ai/claude-haiku-4-5"),
    ],
    "Google": [
        ("Gemini 3.1 Pro (latest, recommended)", "gemini/gemini-3.1-pro"),
        ("Gemini 3 Pro", "gemini/gemini-3-pro"),
        ("Gemini 3.1 Flash Lite (cheap)", "gemini/gemini-3.1-flash-lite"),
        ("Gemini 2.5 Pro", "gemini/gemini-2.5-pro"),
        ("Gemini 2.5 Flash", "gemini/gemini-2.5-flash"),
        ("Gemini 2.0 Pro", "gemini/gemini-2.0-pro"),
        ("Gemini 1.5 Pro (long context)", "gemini/gemini-1.5-pro"),
    ],
    "DeepSeek": [
        ("DeepSeek V4 Pro (latest)", "deepseek/deepseek-v4-pro"),
        ("DeepSeek V4 Flash (fast/cheap)", "deepseek/deepseek-v4-flash"),
        ("DeepSeek V4", "deepseek/deepseek-v4"),
        ("DeepSeek V3.2", "deepseek/deepseek-v3.2"),
        ("DeepSeek V3.2 Speciale (reasoning)", "deepseek/deepseek-v3.2-speciale"),
    ],
    "Mistral": [
        ("Mistral Large 3 (latest)", "mistral/mistral-large-3"),
        ("Mistral Medium 3.5", "mistral/mistral-medium-3.5"),
        ("Mistral Small 4 (cheap)", "mistral/mistral-small-4"),
        ("Magistral Medium 1.2 (reasoning)", "mistral/magistral-medium-1.2"),
        ("Codestral 25.08 (code)", "mistral/codestral-2508"),
        ("Devstral 2 (agentic code)", "mistral/devstral-medium-2"),
    ],
    "xAI": [
        ("Grok 4.1 (latest, recommended)", "xai/grok-4.1"),
        ("Grok 4.1 Fast", "xai/grok-4.1-fast"),
        ("Grok 4 Heavy", "xai/grok-4-heavy"),
        ("Grok 4 Fast", "xai/grok-4-fast"),
        ("Grok 4", "xai/grok-4"),
        ("Grok 3", "xai/grok-3"),
        ("Grok Code Fast 1 (code)", "xai/grok-code-fast-1"),
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
            _mt_value = overrides.get("max_tokens", self.config.max_tokens)
            # Pick the right kwarg name. GPT-5.x / o-series (o1/o3/o4)
            # *only* accept `max_completion_tokens` and explicitly reject
            # `max_tokens`. Same with Azure OpenAI when the deployed
            # model is one of those — but Azure deployment names are
            # user-defined ("ai-integration-planning2", "prod-gpt", …)
            # so we *can't* infer the family from the model string for
            # Azure. Default Azure to `max_completion_tokens` since it
            # works for the entire GPT-4.1 / GPT-4o / GPT-5 / o-series
            # generation; older deployments (GPT-3.5) are rare and
            # litellm.drop_params + modify_params will bridge them.
            _resolved = self.config.resolve_model().lower()
            _is_azure = _resolved.startswith("azure/") or _resolved.startswith("azure_ai/")
            _is_gpt5_family = "gpt-5" in _resolved
            _is_o_series = any(
                tok in _resolved
                for tok in ("/o1", "/o3", "/o4", "-o1-", "-o3-", "-o4-")
            ) or _resolved.endswith("/o1") or _resolved.endswith("/o3") or _resolved.endswith("/o4")
            _needs_completion_tokens = (
                _is_azure or _is_gpt5_family or _is_o_series
            )
            if _needs_completion_tokens:
                kwargs["max_completion_tokens"] = _mt_value
            else:
                kwargs["max_tokens"] = _mt_value
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
