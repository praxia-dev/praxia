"""Document-chunk embeddings via litellm.

Praxia's Documents search used to be pure keyword (BM25-style token
overlap), which fell apart whenever the query language didn't match
the document language or used synonyms. This module replaces that
with semantic search — embed every chunk at ingest time, embed the
query at search time, score by cosine similarity.

litellm is already a Praxia dep (the chat path uses it) so this
module adds zero new packages — we just call litellm.embedding()
with whatever model the user has configured. Falls back gracefully:
if the embedding call fails (no API key, network down, unknown
model), the caller can retain the chunk's text-only state and the
search router falls back to keyword scoring.

Model selection (in priority order):
  1. ``model=`` parameter at the call site
  2. ``PRAXIA_EMBEDDING_MODEL`` environment variable
  3. Provider auto-detect from a configured API key:
       OPENAI_API_KEY    → "text-embedding-3-small"
       AZURE_API_KEY     → "azure/text-embedding-3-small"
                           (requires AZURE_API_BASE too)
       OLLAMA_BASE_URL   → "ollama/nomic-embed-text"
       GOOGLE_API_KEY    → "gemini/text-embedding-004"
       DASHSCOPE_API_KEY → "dashscope/text-embedding-v3"
       HF_TOKEN          → "huggingface/BAAI/bge-m3"
  4. Hard default: "text-embedding-3-small" (errors loudly if no
     OPENAI_API_KEY is around — that's the right failure mode).

Anthropic deliberately omitted: Claude has no public embedding API
(verified 2026-06). Anthropic-only users must add a second provider
(Ollama for free local, OpenAI / Gemini / DashScope / HF for cloud).
"""
from __future__ import annotations

import logging
import math
import os
from typing import Iterable

_log = logging.getLogger(__name__)

_HARD_DEFAULT = "text-embedding-3-small"


def get_default_embedding_model() -> str:
    """Pick the most sensible default embedding model for the current
    environment. See module docstring for the precedence rules."""
    explicit = os.environ.get("PRAXIA_EMBEDDING_MODEL", "").strip()
    if explicit:
        return explicit
    if os.environ.get("OPENAI_API_KEY"):
        return "text-embedding-3-small"
    if os.environ.get("AZURE_API_KEY") and os.environ.get("AZURE_API_BASE"):
        # The user must have a deployment named text-embedding-3-small;
        # there's no portable way for us to discover the deployment
        # name, but most Azure tenants follow the convention.
        return "azure/text-embedding-3-small"
    if os.environ.get("OLLAMA_BASE_URL"):
        return "ollama/nomic-embed-text"
    if os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"):
        # Google AI Studio's embedding endpoint — free tier covers a lot.
        return "gemini/text-embedding-004"
    if os.environ.get("DASHSCOPE_API_KEY"):
        # Alibaba's Qwen embedding family — same key as the chat model.
        return "dashscope/text-embedding-v3"
    if os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_API_KEY"):
        # HF Inference's hosted bge-m3 — multilingual, MIT-licensed.
        return "huggingface/BAAI/bge-m3"
    return _HARD_DEFAULT


def embed_texts(
    texts: list[str],
    *,
    model: str | None = None,
    batch_size: int = 64,
) -> list[list[float]]:
    """Embed a batch of texts. Returns a list of vectors in the same
    order. Raises RuntimeError on any failure — callers wrap to fall
    back to keyword search.

    We chunk into ``batch_size`` groups because most providers cap at
    100-2048 inputs per call; 64 is a safe middle ground that keeps
    request latency bounded.
    """
    if not texts:
        return []
    try:
        import litellm
    except ImportError as e:  # pragma: no cover - litellm is a hard dep
        raise RuntimeError(f"litellm not importable: {e}") from e

    chosen = model or get_default_embedding_model()
    out: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        try:
            resp = litellm.embedding(model=chosen, input=batch)
        except Exception as e:
            # Surface a single combined error so the caller doesn't
            # have to figure out which sub-batch died.
            raise RuntimeError(
                f"embedding call failed (model={chosen!r}, batch={i}-{i+len(batch)}): {e}"
            ) from e
        # litellm normalises to OpenAI-shaped response: data = [{"embedding": [..]}]
        try:
            for item in resp.data:
                vec = item.get("embedding") if isinstance(item, dict) else getattr(item, "embedding", None)
                if not isinstance(vec, list):
                    raise RuntimeError(f"unexpected embedding shape: {type(vec).__name__}")
                out.append([float(x) for x in vec])
        except (AttributeError, KeyError, TypeError) as e:
            raise RuntimeError(f"could not parse embedding response: {e}") from e
    return out


def embed_text(text: str, *, model: str | None = None) -> list[float]:
    """Embed a single text. Convenience wrapper around ``embed_texts``."""
    result = embed_texts([text], model=model)
    if not result:
        raise RuntimeError("embed_text got an empty result")
    return result[0]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity in [-1.0, 1.0]. Returns 0.0 for empty /
    mismatched-dimension inputs rather than raising so retrieval
    stays robust against corrupt or stale embeddings."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def is_available() -> bool:
    """Cheap check: do we have *any* embedding path configured? Used
    by the search router to decide whether to attempt semantic search
    or stay on keyword scoring."""
    return bool(
        os.environ.get("OPENAI_API_KEY")
        or os.environ.get("AZURE_API_KEY")
        or os.environ.get("OLLAMA_BASE_URL")
        or os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("DASHSCOPE_API_KEY")
        or os.environ.get("HF_TOKEN")
        or os.environ.get("HUGGINGFACE_API_KEY")
        or os.environ.get("PRAXIA_EMBEDDING_MODEL")
    )
