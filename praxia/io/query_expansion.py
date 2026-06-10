"""LLM-driven query expansion for Praxia's Documents search.

When the user has no embedding provider configured (most commonly:
Anthropic-only, no OpenAI/Ollama/Azure/Gemini key), Documents search
falls back to keyword scoring. Pure keyword matching is brittle for
the JA-query-against-EN-doc case — "アクションアイテム" never matches
"action items" without an embedding to bridge them.

This module fills the gap by asking the active LLM to rewrite each
query into 3-5 alternative phrasings before keyword scoring. The
expansion targets four kinds of misses:

  * **Synonyms in the same language** ("price" / "cost" / "fee")
  * **Cross-language equivalents** ("アクションアイテム" / "action items")
  * **Abbreviations and expansions** ("PR" / "pull request" /
    "プルリクエスト")
  * **Domain paraphrases** ("make safer" / "harden" / "improve security")

The expanded variants are run as parallel keyword searches and the
maximum score per chunk wins. Result: semantic-search-like recall
without an embedding provider, at the cost of one LLM round-trip per
distinct query (cached in an LRU so repeated queries skip the call).

Why this matters: the L0 bench in
``real_hermes_l0_verification.md`` shows agentic grep/read recursion
hitting 87% on multi-hop document QA — close to dedicated semantic
search — when the LLM drives synonym + cross-language expansion. We
implement the single-shot synonym-expansion half here; the agent
loop already handles the recursive part by calling search_documents
multiple times with refined queries.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
from collections import OrderedDict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from praxia.core.llm import LLM

_log = logging.getLogger(__name__)


class _LRU:
    """Tiny thread-safe LRU keyed on (model, query) → tuple of variants.

    The stdlib ``functools.lru_cache`` doesn't fit here because we'd
    have to bake the LLM object into the key (not hashable) and the
    cached value would need to be computed inside the wrapped function
    (which makes graceful error handling awkward). A bespoke OrderedDict
    is 20 lines and behaves predictably under the read-mostly access
    pattern of search queries.
    """

    def __init__(self, max_entries: int = 1024) -> None:
        self._max = int(max_entries)
        self._data: "OrderedDict[str, tuple[str, ...]]" = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> tuple[str, ...] | None:
        with self._lock:
            if key not in self._data:
                return None
            self._data.move_to_end(key)
            return self._data[key]

    def put(self, key: str, value: tuple[str, ...]) -> None:
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = value
            while len(self._data) > self._max:
                self._data.popitem(last=False)


_CACHE = _LRU(max_entries=1024)


# Hard cap. Higher = better recall, more LLM tokens per round.
# Five is enough to cover most synonym/translation pairs without
# blowing up the keyword-scoring inner loop (which is O(chunks)).
_MAX_VARIANTS = 5

# Cap the prompt at this many chars — long queries pasted from
# Documents themselves shouldn't waste a 4k-token call. Truncation
# preserves the head of the query, which usually carries the intent.
_QUERY_TRUNCATE = 600


_EXPANSION_PROMPT = """\
You will receive a search query that will be used to look up content \
in the user's local Documents folder via keyword matching. The corpus \
may be in any language. Generate up to {n} ALTERNATIVE PHRASINGS \
designed to maximize recall against documents that say the same thing \
in different words.

Include where relevant:
- Direct synonyms in the same language as the query.
- Cross-language equivalents (e.g., a JA query gets EN/CN/KR variants \
  if appropriate, an EN query gets JA/CN variants).
- Common abbreviations and their expansions.
- Domain-specific paraphrases.

Do NOT include the original query itself — the caller adds it. \
Each variant must be a self-contained keyword phrase (no quotes, no \
explanations, no ranking). At most {n} entries total.

Return JSON, no other text: {{"variants": ["...", "...", ...]}}

Query: {query}
"""


def _cache_key(query: str, model: str) -> str:
    """Deterministic cache key. Model is part of the key because
    different LLMs produce different variants for the same query —
    we don't want a cached Claude expansion to be served to an
    OpenAI scout, since the downstream keyword loop is the same but
    the variant quality differs."""
    h = hashlib.sha256(f"{model}::{query}".encode("utf-8")).hexdigest()
    return h[:32]


def _parse_variants(json_payload: str) -> tuple[str, ...]:
    """Pull a dedup'd, capped variant list out of the LLM's JSON
    response. Tolerant of empty / malformed payloads — returns ()
    in that case so the caller transparently uses the original
    query alone."""
    try:
        data = json.loads(json_payload)
        variants = data.get("variants", [])
    except (json.JSONDecodeError, AttributeError, TypeError):
        return ()
    seen = set()
    out: list[str] = []
    for v in variants:
        if not isinstance(v, str):
            continue
        s = v.strip()
        if not s or s.lower() in seen:
            continue
        seen.add(s.lower())
        out.append(s)
        if len(out) >= _MAX_VARIANTS:
            break
    return tuple(out)


def expand_query(
    query: str,
    *,
    llm: "LLM",
    max_variants: int = _MAX_VARIANTS,
) -> list[str]:
    """Return up to ``max_variants`` alternate phrasings for ``query``.

    Always returns a list — never raises. On any failure (LLM error,
    JSON parse failure, empty response) returns ``[]`` so the caller
    can transparently fall back to the original query alone. The
    original query should NOT be passed back to the keyword scorer
    by this function; that's the caller's job (so the caller can
    decide whether to dedupe against it).
    """
    q = (query or "").strip()
    if not q:
        return []
    if len(q) > _QUERY_TRUNCATE:
        q = q[:_QUERY_TRUNCATE]
    n = max(1, min(int(max_variants), _MAX_VARIANTS))

    model = getattr(getattr(llm, "config", None), "model", "") or ""
    key = _cache_key(q, model)

    # Cache hit: skip the LLM call entirely.
    cached = _CACHE.get(key)
    if cached is not None:
        return list(cached)

    prompt = _EXPANSION_PROMPT.format(n=n, query=q)
    try:
        resp = llm.complete(
            [{"role": "user", "content": prompt}],
            response_format="json",
        )
    except Exception as e:
        _log.warning("query_expansion LLM call failed (%s); skipping", e)
        return []

    payload = (resp.text or "").strip()
    if not payload:
        return []
    variants = _parse_variants(payload)
    # Cache even the empty-tuple result so repeated misses don't
    # re-burn LLM tokens. Negative caching is fine here because the
    # LLM's "I cannot expand this query" verdict is stable for the
    # same (model, query) pair.
    _CACHE.put(key, variants)
    return list(variants)
