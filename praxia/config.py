"""Unified configuration — one place to manage all Praxia keys / secrets.

Praxia reads configuration from three sources, in order of precedence:

    1. **Process environment variables** (highest)
    2. **.env file** in the working directory (loaded by `dotenv` if present)
    3. **`.praxia/config.toml`** (lowest — long-lived defaults)

All Praxia code paths funnel through `PraxiaConfig.get(key, default)` so
a single change in any of the three sources is picked up everywhere.

CLI:
    praxia config show       # display all keys (secrets masked)
    praxia config init       # interactive wizard — first-time setup
    praxia config get KEY    # one-off query
    praxia config set KEY=v  # write to .praxia/config.toml

Recommended workflow:

    1. Copy `.env.example` → `.env`
    2. Fill in just the keys you actually use
    3. (Optional) Run `praxia config init` for an interactive walkthrough

Key catalog (the canonical list):

    # LLM providers — set at least one
    ANTHROPIC_API_KEY
    OPENAI_API_KEY
    GEMINI_API_KEY
    DASHSCOPE_API_KEY                # Alibaba Qwen API
    OLLAMA_API_BASE                  # local Qwen / Llama

    # Memory backend selection
    PRAXIA_MEMORY_BACKEND            # json (default) / mem0 / langmem / letta / zep / hindsight

    # Auth / security
    PRAXIA_JWT_SECRET                # signs JWT tokens
    PRAXIA_TOKEN_ENC_KEY             # encrypts OAuth tokens at rest

    # Per-user OAuth — one pair per provider
    PRAXIA_OAUTH_BOX_CLIENT_ID
    PRAXIA_OAUTH_BOX_CLIENT_SECRET
    PRAXIA_OAUTH_MICROSOFT_CLIENT_ID
    PRAXIA_OAUTH_MICROSOFT_CLIENT_SECRET
    PRAXIA_OAUTH_DROPBOX_CLIENT_ID
    PRAXIA_OAUTH_DROPBOX_CLIENT_SECRET
    PRAXIA_OAUTH_GOOGLE_CLIENT_ID
    PRAXIA_OAUTH_GOOGLE_CLIENT_SECRET
    PRAXIA_OAUTH_SALESFORCE_CLIENT_ID
    PRAXIA_OAUTH_SALESFORCE_CLIENT_SECRET

    # Shared-credential (legacy) connector auth — when not using OAuth
    PRAXIA_CONN_BOX_ACCESS_TOKEN
    PRAXIA_CONN_KINTONE_SUBDOMAIN
    PRAXIA_CONN_KINTONE_API_TOKEN
    # ... etc., pattern: PRAXIA_CONN_<UPPERCASE_NAME>_<UPPERCASE_KEY>

    # Audio (optional)
    OPENAI_API_KEY                   # also used for Whisper STT + OpenAI TTS
    ELEVENLABS_API_KEY               # ElevenLabs voice cloning (TTS)

    # SSO (optional, for federated auth)
    PRAXIA_SSO_PROVIDER              # google / microsoft / okta / github / keycloak
    PRAXIA_SSO_CLIENT_ID
    PRAXIA_SSO_CLIENT_SECRET
    PRAXIA_SSO_REDIRECT_URI
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any


# Canonical list of keys Praxia knows about, with category + secret-flag
KNOWN_KEYS: dict[str, tuple[str, bool]] = {
    # category, is_secret

    # LLM providers (auto-detected by LLM.auto_detect in this priority)
    "ANTHROPIC_API_KEY":              ("LLM", True),
    "OPENAI_API_KEY":                 ("LLM", True),
    "GEMINI_API_KEY":                 ("LLM", True),
    "DEEPSEEK_API_KEY":               ("LLM", True),
    "MISTRAL_API_KEY":                ("LLM", True),
    "XAI_API_KEY":                    ("LLM", True),
    "DASHSCOPE_API_KEY":              ("LLM", True),
    "COHERE_API_KEY":                 ("LLM", True),
    "PERPLEXITY_API_KEY":             ("LLM", True),
    "GROQ_API_KEY":                   ("LLM", True),
    "TOGETHERAI_API_KEY":             ("LLM", True),
    "OPENROUTER_API_KEY":             ("LLM", True),
    # Azure OpenAI (different from OpenAI: requires deployment name +
    # endpoint + API version; the AZURE_API_KEY is from Azure portal,
    # not platform.openai.com)
    "AZURE_API_KEY":                  ("LLM", True),
    "AZURE_API_BASE":                 ("LLM", False),  # https://<resource>.openai.azure.com/
    "AZURE_API_VERSION":              ("LLM", False),  # e.g. 2024-08-01-preview
    # Azure AI Foundry / Inference (separate endpoint flavor — uses
    # OpenAI-compatible API but lives under foundry.azure.com)
    "AZURE_AI_API_KEY":               ("LLM", True),
    "AZURE_AI_API_BASE":              ("LLM", False),
    # AWS Bedrock — Claude / Llama / Titan etc. served on AWS infra.
    # Authenticates with AWS IAM credentials, not an Anthropic key.
    # AWS_REGION is shared with KMS but Bedrock needs it too — we list
    # it once under KMS; same value works for both.
    "AWS_ACCESS_KEY_ID":              ("LLM", True),
    "AWS_SECRET_ACCESS_KEY":          ("LLM", True),
    "AWS_SESSION_TOKEN":              ("LLM", True),  # only when using STS / role assumption
    "AWS_BEDROCK_RUNTIME_ENDPOINT":   ("LLM", False),  # rare — for VPC endpoints
    # Google Vertex AI — for Gemini & Anthropic-on-Vertex deployments
    "VERTEX_PROJECT":                 ("LLM", False),
    "VERTEX_LOCATION":                ("LLM", False),  # e.g. us-central1
    "GOOGLE_APPLICATION_CREDENTIALS": ("LLM", False),  # path to service-account JSON
    "OLLAMA_API_BASE":                ("LLM", False),
    "PRAXIA_LOCAL_MODEL":             ("LLM", False),

    # Identity (for the agent / multi-tenant scenarios)
    "PRAXIA_USER_ID":                 ("Identity", False),

    # Memory
    "PRAXIA_MEMORY_BACKEND":          ("Memory", False),
    "PRAXIA_MEMORY_MODE":             ("Memory", False),

    # Auth (JWT / token encryption)
    "PRAXIA_JWT_SECRET":              ("Auth", True),
    "PRAXIA_TOKEN_ENC_KEY":           ("Auth", True),

    # SCIM
    "PRAXIA_SCIM_TOKEN":              ("SCIM", True),
    "PRAXIA_SCIM_DEFAULT_ROLE":       ("SCIM", False),

    # SSO (OIDC)
    "PRAXIA_SSO_PROVIDER":            ("SSO", False),
    "PRAXIA_SSO_CLIENT_ID":           ("SSO", False),
    "PRAXIA_SSO_CLIENT_SECRET":       ("SSO", True),
    "PRAXIA_SSO_REDIRECT_URI":        ("SSO", False),
    "PRAXIA_SSO_TENANT_ID":           ("SSO", False),
    "PRAXIA_SSO_OKTA_DOMAIN":         ("SSO", False),
    "PRAXIA_SSO_KEYCLOAK_BASE_URL":   ("SSO", False),
    "PRAXIA_SSO_KEYCLOAK_REALM":      ("SSO", False),
    "PRAXIA_SSO_ISSUER_URL":          ("SSO", False),

    # KMS — wraps DEKs that envelope-encrypt OAuth tokens at rest
    "PRAXIA_KMS_ADAPTER":             ("KMS", False),
    "PRAXIA_KMS_KEY_ID":              ("KMS", False),
    "AWS_REGION":                     ("KMS", False),
    "VAULT_ADDR":                     ("KMS", False),
    "VAULT_TOKEN":                    ("KMS", True),
    "VAULT_TRANSIT_KEY":              ("KMS", False),

    # OAuth — server-side surface
    "PRAXIA_PUBLIC_URL":              ("OAuth (server)", False),
    "PRAXIA_OAUTH_SUCCESS_REDIRECT":  ("OAuth (server)", False),

    # OAuth — one pair per provider
    "PRAXIA_OAUTH_BOX_CLIENT_ID":             ("OAuth (Box)", False),
    "PRAXIA_OAUTH_BOX_CLIENT_SECRET":         ("OAuth (Box)", True),
    "PRAXIA_OAUTH_MICROSOFT_CLIENT_ID":       ("OAuth (Microsoft)", False),
    "PRAXIA_OAUTH_MICROSOFT_CLIENT_SECRET":   ("OAuth (Microsoft)", True),
    "PRAXIA_OAUTH_DROPBOX_CLIENT_ID":         ("OAuth (Dropbox)", False),
    "PRAXIA_OAUTH_DROPBOX_CLIENT_SECRET":     ("OAuth (Dropbox)", True),
    "PRAXIA_OAUTH_GOOGLE_CLIENT_ID":          ("OAuth (Google)", False),
    "PRAXIA_OAUTH_GOOGLE_CLIENT_SECRET":      ("OAuth (Google)", True),
    "PRAXIA_OAUTH_SALESFORCE_CLIENT_ID":      ("OAuth (Salesforce)", False),
    "PRAXIA_OAUTH_SALESFORCE_CLIENT_SECRET":  ("OAuth (Salesforce)", True),
    # Per-tenant URL placeholders — required by some providers (e.g. Zendesk subdomain)
    "PRAXIA_OAUTH_ZENDESK_CLIENT_ID":         ("OAuth (Zendesk)", False),
    "PRAXIA_OAUTH_ZENDESK_CLIENT_SECRET":     ("OAuth (Zendesk)", True),
    "PRAXIA_OAUTH_ZENDESK_SUBDOMAIN":         ("OAuth (Zendesk)", False),

    # MCP HTTP transport
    "PRAXIA_MCP_TOKEN":               ("MCP", True),

    # Audio (optional, separate from LLM)
    "ELEVENLABS_API_KEY":             ("Audio", True),
}


class PraxiaConfig:
    """Single source of truth for runtime configuration.

    Reads from process env vars first; falls back to .env (auto-loaded if
    `python-dotenv` is installed); falls back to ``.praxia/config.toml``.

    Use class methods on this — there's no need to instantiate.
    """

    _toml_cache: dict[str, str] | None = None

    @classmethod
    def get(cls, key: str, default: str | None = None) -> str | None:
        """Resolve `key` against env → .env → config.toml → default."""
        # Process env (also picks up .env if dotenv was loaded by user)
        val = os.environ.get(key)
        if val is not None:
            return val
        # config.toml fallback
        toml_data = cls._load_toml()
        if key in toml_data:
            return toml_data[key]
        return default

    @classmethod
    def get_required(cls, key: str) -> str:
        """Same as get() but raises ValueError if missing."""
        val = cls.get(key)
        if val is None:
            raise ValueError(
                f"Required config key {key!r} is not set. "
                f"Add it to .env, your environment, or .praxia/config.toml. "
                f"See `praxia config init` for an interactive walkthrough."
            )
        return val

    @classmethod
    def set_persistent(cls, key: str, value: str) -> None:
        """Write `key=value` to .praxia/config.toml (creates if missing)."""
        toml_path = Path(".praxia/config.toml")
        toml_path.parent.mkdir(parents=True, exist_ok=True)
        existing = cls._load_toml() if toml_path.exists() else {}
        existing[key] = value
        cls._write_toml(toml_path, existing)
        cls._toml_cache = existing  # invalidate cache

    @classmethod
    def list_set(cls) -> dict[str, tuple[str, str]]:
        """Return {key: (category, masked_value)} for every known key that's set."""
        out: dict[str, tuple[str, str]] = {}
        for key, (category, is_secret) in KNOWN_KEYS.items():
            val = cls.get(key)
            if val is None:
                continue
            display = cls._mask(val) if is_secret else val
            out[key] = (category, display)
        return out

    @classmethod
    def list_unset(cls) -> dict[str, str]:
        """Return {key: category} for known keys that are not currently set."""
        return {
            k: cat for k, (cat, _) in KNOWN_KEYS.items() if cls.get(k) is None
        }

    @classmethod
    def load_dotenv(cls, path: str | Path = ".env") -> bool:
        """Load a .env file into the process environment if it exists.

        Returns True if a file was found and loaded.
        Uses `python-dotenv` if installed; otherwise a minimal parser.
        """
        p = Path(path)
        if not p.exists():
            return False
        try:
            from dotenv import load_dotenv as _ld  # type: ignore[import-not-found]
            _ld(p, override=False)
            return True
        except ImportError:
            # Minimal stdlib parser — KEY=VALUE per line, ignores # comments
            with p.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    os.environ.setdefault(key, value)
            return True

    # --- Internals --------------------------------------------------------

    @classmethod
    def _load_toml(cls) -> dict[str, str]:
        if cls._toml_cache is not None:
            return cls._toml_cache
        toml_path = Path(".praxia/config.toml")
        cls._toml_cache = {}
        if not toml_path.exists():
            return cls._toml_cache
        try:
            import tomllib
        except ImportError:  # pragma: no cover — Python < 3.11
            import tomli as tomllib  # type: ignore[no-redef]
        with toml_path.open("rb") as f:
            data = tomllib.load(f)
        # Flatten (only top-level + a single 'praxia' table supported)
        flat: dict[str, str] = {}
        for k, v in data.items():
            if isinstance(v, dict):
                for kk, vv in v.items():
                    flat[kk] = str(vv)
            else:
                flat[k] = str(v)
        cls._toml_cache = flat
        return flat

    @classmethod
    def _write_toml(cls, path: Path, data: dict[str, str]) -> None:
        # Stable, sorted output (no tomli-w dep)
        lines: list[str] = ["# Praxia persistent config — managed by `praxia config set`\n"]
        for key in sorted(data):
            value = data[key].replace('"', '\\"')
            lines.append(f'{key} = "{value}"\n')
        path.write_text("".join(lines), encoding="utf-8")

    @staticmethod
    def _mask(value: str) -> str:
        """Show first 4 + last 4 chars of secrets; full value if too short."""
        if len(value) <= 12:
            return "****"
        return f"{value[:4]}…{value[-4:]}"


# Auto-load .env on import (no-op if not present)
PraxiaConfig.load_dotenv()
