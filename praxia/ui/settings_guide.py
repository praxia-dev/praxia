"""Per-category guidance for the Persistent settings form.

Some categories (AWS Bedrock, Azure OpenAI, Vertex, OAuth) need
several env vars set *together* to function — the form would otherwise
look like a flat list with no indication of which keys belong to a
working set. This module annotates each category with:

- ``intro``       : i18n key for a short paragraph explaining what the
                    group is, when to use it, and what to plug in
- ``required``    : list of env-var names that are required (the rest
                    are optional / situational)
- ``key_help``    : per-env-var i18n key that replaces the generic
                    "currently set / unset" tooltip with specific
                    "this is your <something>, get it from <where>"
                    text. Falls back to the generic help when missing.
- ``cross_refs``  : list of env-var names that live in a *different*
                    category but matter for this one (e.g. AWS_REGION
                    is under KMS but Bedrock needs it too).

The shape mirrors what the i18n catalog already does — every value is
either an i18n key or a list of env-var names, never localized strings
in this file.
"""
from __future__ import annotations


# Top-level section headings used by the Settings UI to group related
# categories under one banner. Order matters — sections appear in the
# UI in this order. Each entry is (section_label_i18n_key, predicate)
# where predicate(category) decides whether a category belongs here.
TOP_LEVEL_SECTIONS: list[tuple[str, callable]] = [
    ("settings.section.llm",     lambda c: c.startswith("LLM ")),
    ("settings.section.oauth",   lambda c: c == "OAuth (server)" or c.startswith("OAuth (")),
    ("settings.section.security", lambda c: c in ("Auth", "KMS", "SSO", "SCIM")),
    ("settings.section.runtime", lambda c: (
        c in ("Memory", "MCP", "Audio") or c.startswith("Identity")
    )),
]


def section_for(category: str) -> str:
    """Return the i18n key of the top-level section a category belongs
    to, or ``"settings.section.other"`` if it doesn't match anything."""
    for label_key, predicate in TOP_LEVEL_SECTIONS:
        if predicate(category):
            return label_key
    return "settings.section.other"


# Category-name → guidance metadata.
# Categories that aren't listed here render with no intro / no required
# markers — the simple "1 key" case (e.g. ANTHROPIC_API_KEY alone).
CATEGORY_GUIDE: dict[str, dict] = {
    "LLM · OpenAI": {
        "intro": "settings.guide.openai.intro",
        "required": ["OPENAI_API_KEY"],
        "key_help": {
            "OPENAI_API_KEY": "settings.guide.openai.OPENAI_API_KEY",
        },
    },
    "LLM · Anthropic": {
        "intro": "settings.guide.anthropic.intro",
        "required": ["ANTHROPIC_API_KEY"],
        "key_help": {
            "ANTHROPIC_API_KEY": "settings.guide.anthropic.ANTHROPIC_API_KEY",
        },
    },
    "LLM · Azure OpenAI": {
        "intro": "settings.guide.azure_openai.intro",
        "required": ["AZURE_API_KEY", "AZURE_API_BASE", "AZURE_API_VERSION"],
        "key_help": {
            "AZURE_API_KEY":     "settings.guide.azure_openai.AZURE_API_KEY",
            "AZURE_API_BASE":    "settings.guide.azure_openai.AZURE_API_BASE",
            "AZURE_API_VERSION": "settings.guide.azure_openai.AZURE_API_VERSION",
        },
    },
    "LLM · Azure AI Foundry": {
        "intro": "settings.guide.azure_ai.intro",
        "required": ["AZURE_AI_API_KEY", "AZURE_AI_API_BASE"],
        "key_help": {
            "AZURE_AI_API_KEY":  "settings.guide.azure_ai.AZURE_AI_API_KEY",
            "AZURE_AI_API_BASE": "settings.guide.azure_ai.AZURE_AI_API_BASE",
        },
    },
    "LLM · AWS Bedrock": {
        "intro": "settings.guide.aws_bedrock.intro",
        "required": ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"],
        "key_help": {
            "AWS_ACCESS_KEY_ID":            "settings.guide.aws_bedrock.AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY":        "settings.guide.aws_bedrock.AWS_SECRET_ACCESS_KEY",
            "AWS_SESSION_TOKEN":            "settings.guide.aws_bedrock.AWS_SESSION_TOKEN",
            "AWS_BEDROCK_RUNTIME_ENDPOINT": "settings.guide.aws_bedrock.AWS_BEDROCK_RUNTIME_ENDPOINT",
        },
        "cross_refs": ["AWS_REGION"],  # lives under KMS category
    },
    "LLM · Google": {
        "intro": "settings.guide.google.intro",
        "required": ["GEMINI_API_KEY"],
        "key_help": {
            "GEMINI_API_KEY":                 "settings.guide.google.GEMINI_API_KEY",
            "VERTEX_PROJECT":                 "settings.guide.google.VERTEX_PROJECT",
            "VERTEX_LOCATION":                "settings.guide.google.VERTEX_LOCATION",
            "GOOGLE_APPLICATION_CREDENTIALS": "settings.guide.google.GOOGLE_APPLICATION_CREDENTIALS",
        },
    },
    "LLM · Local (Ollama)": {
        "intro": "settings.guide.ollama.intro",
        "required": [],  # all optional — defaults work for local installs
        "key_help": {
            "OLLAMA_API_BASE":    "settings.guide.ollama.OLLAMA_API_BASE",
            "PRAXIA_LOCAL_MODEL": "settings.guide.ollama.PRAXIA_LOCAL_MODEL",
        },
    },
    "KMS": {
        "intro": "settings.guide.kms.intro",
        "required": ["PRAXIA_KMS_ADAPTER"],
        "key_help": {
            "PRAXIA_KMS_ADAPTER":  "settings.guide.kms.PRAXIA_KMS_ADAPTER",
            "PRAXIA_KMS_KEY_ID":   "settings.guide.kms.PRAXIA_KMS_KEY_ID",
            "AWS_REGION":          "settings.guide.kms.AWS_REGION",
            "VAULT_ADDR":          "settings.guide.kms.VAULT_ADDR",
            "VAULT_TOKEN":         "settings.guide.kms.VAULT_TOKEN",
            "VAULT_TRANSIT_KEY":   "settings.guide.kms.VAULT_TRANSIT_KEY",
        },
    },
    "Identity (CLI / SDK default)": {
        "intro": "settings.guide.identity.intro",
        "required": [],
        "key_help": {
            "PRAXIA_USER_ID": "settings.guide.identity.PRAXIA_USER_ID",
        },
    },
}


def category_meta(category: str) -> dict:
    """Return guidance metadata for a category, or an empty dict if no
    entry is registered (single-key categories don't need any)."""
    return CATEGORY_GUIDE.get(category, {})


__all__ = ["CATEGORY_GUIDE", "category_meta"]
