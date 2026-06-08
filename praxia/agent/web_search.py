"""Web search backend for the ``web_search`` agent tool.

Praxia ships no web index of its own — when the agent needs current
events ("latest news on X", "what's the price of Y today",
"recent guidance from Z") it calls one of the providers below. Two
are supported, picked by precedence:

  1. ``TAVILY_API_KEY``        → Tavily (built for LLM agents, has
                                 a free tier).
  2. ``BRAVE_SEARCH_API_KEY``  → Brave Search (also has a free tier;
                                 serves the generic web-search use
                                 case fine).

(Both vendors publish current pricing on their own sites — we
deliberately don't quote numeric quotas here because they change
faster than this comment does.)

Anthropic, OpenAI, etc. are *not* in this list — none of them
expose a first-party web-search HTTP endpoint that's appropriate
for non-streaming sub-call use. We deliberately keep this narrow
so a casual Praxia user can paste one key and be done.
"""
from __future__ import annotations

import logging
import os
from typing import Any

_log = logging.getLogger(__name__)

# Request timeout — generous enough for slow third-party search,
# bounded so a hung provider doesn't stall the parent agent loop.
_TIMEOUT_SEC = 12.0


def is_available() -> bool:
    """Cheap check: do we have at least one provider configured?"""
    return bool(
        os.environ.get("TAVILY_API_KEY")
        or os.environ.get("BRAVE_SEARCH_API_KEY")
        or os.environ.get("BRAVE_API_KEY")  # alias some users set
    )


def active_provider() -> str | None:
    """Return the provider name that ``web_search`` would call right
    now, or None if none is configured. Used by the tool handler to
    surface a clear error message."""
    if os.environ.get("TAVILY_API_KEY"):
        return "tavily"
    if os.environ.get("BRAVE_SEARCH_API_KEY") or os.environ.get("BRAVE_API_KEY"):
        return "brave"
    return None


def search(query: str, *, max_results: int = 5) -> dict[str, Any]:
    """Run a web search via the configured provider.

    Returns a normalised dict with::

        {
          "query": str,
          "answer": str | None,             # one-paragraph synthesis if the
                                            # provider returns it (Tavily does,
                                            # Brave does not)
          "results": [
            {"title": str, "url": str, "snippet": str},
            ...
          ],
          "count": int,
          "source": "tavily" | "brave",
        }

    Raises ``RuntimeError`` when no provider key is set; the agent
    tool wrapper catches and surfaces it to the LLM so the model can
    relay an actionable message to the user.
    """
    provider = active_provider()
    if provider is None:
        raise RuntimeError(
            "No web search provider configured. Set TAVILY_API_KEY "
            "(https://tavily.com) or BRAVE_SEARCH_API_KEY "
            "(https://brave.com/search/api/)."
        )
    q = (query or "").strip()
    if not q:
        return {"query": "", "answer": None, "results": [], "count": 0, "source": provider}
    n = max(1, min(int(max_results or 5), 10))

    if provider == "tavily":
        return _tavily_search(q, n)
    return _brave_search(q, n)


def _tavily_search(query: str, max_results: int) -> dict[str, Any]:
    import httpx

    api_key = os.environ["TAVILY_API_KEY"]
    body = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": max_results,
        # include_answer asks Tavily to synthesize a one-paragraph
        # answer alongside the raw results — useful when the agent
        # is doing a one-shot RAG lookup and doesn't want to read
        # every snippet itself.
        "include_answer": True,
    }
    try:
        with httpx.Client(timeout=_TIMEOUT_SEC) as c:
            r = c.post("https://api.tavily.com/search", json=body)
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as e:
        raise RuntimeError(f"Tavily request failed: {e}") from e

    results: list[dict[str, Any]] = []
    for item in (data.get("results") or [])[:max_results]:
        results.append({
            "title": str(item.get("title") or ""),
            "url": str(item.get("url") or ""),
            "snippet": str(item.get("content") or "")[:500],
        })
    return {
        "query": query,
        "answer": (data.get("answer") or None),
        "results": results,
        "count": len(results),
        "source": "tavily",
    }


def _brave_search(query: str, max_results: int) -> dict[str, Any]:
    import httpx

    api_key = (
        os.environ.get("BRAVE_SEARCH_API_KEY")
        or os.environ["BRAVE_API_KEY"]
    )
    params = {"q": query, "count": str(max_results)}
    headers = {
        "X-Subscription-Token": api_key,
        "Accept": "application/json",
    }
    try:
        with httpx.Client(timeout=_TIMEOUT_SEC) as c:
            r = c.get(
                "https://api.search.brave.com/res/v1/web/search",
                params=params, headers=headers,
            )
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as e:
        raise RuntimeError(f"Brave Search request failed: {e}") from e

    web_block = (data.get("web") or {}).get("results") or []
    results: list[dict[str, Any]] = []
    for item in web_block[:max_results]:
        results.append({
            "title": str(item.get("title") or ""),
            "url": str(item.get("url") or ""),
            "snippet": str(item.get("description") or "")[:500],
        })
    return {
        "query": query,
        "answer": None,   # Brave doesn't synthesize an answer in the basic plan
        "results": results,
        "count": len(results),
        "source": "brave",
    }
