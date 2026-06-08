"""Coverage for the alpha25 web_search agent tool.

The handler must:
  - return a structured `error` when no provider key is configured
    (so the LLM relays it instead of crashing the run)
  - normalise the Tavily + Brave response shapes into the same dict
  - choose Tavily over Brave when both keys are present
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from praxia.agent import web_search as ws
from praxia.agent.tools import _web_search, builtin_tools


@pytest.fixture(autouse=True)
def clear_env(monkeypatch):
    for k in (
        "TAVILY_API_KEY",
        "BRAVE_SEARCH_API_KEY",
        "BRAVE_API_KEY",
    ):
        monkeypatch.delenv(k, raising=False)


def _agent():
    a = MagicMock()
    a.user_id = "alice"
    a.role = "member"
    return a


class TestAvailability:
    def test_no_keys_reports_unavailable(self):
        assert ws.is_available() is False
        assert ws.active_provider() is None

    def test_tavily_key_picked_first(self, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "tvly-xxx")
        monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "BSA-xxx")
        assert ws.active_provider() == "tavily"

    def test_brave_alias_recognized(self, monkeypatch):
        monkeypatch.setenv("BRAVE_API_KEY", "BSA-xxx")
        assert ws.is_available() is True
        assert ws.active_provider() == "brave"


class TestHandlerSurface:
    def test_no_provider_returns_error_field(self):
        # The tool handler MUST NOT raise — it returns an error string
        # so the LLM can relay a clear "add a key" message.
        res = _web_search(_agent(), query="anything")
        assert res["count"] == 0
        assert "error" in res
        assert "TAVILY_API_KEY" in res["error"] or "BRAVE" in res["error"]

    def test_registered_in_builtin_tools(self):
        tools = builtin_tools()
        assert "web_search" in tools
        schema = tools["web_search"].parameters_schema
        assert "query" in schema["properties"]
        # The description must mention what NOT to use it for
        # (search_documents / search_personal_memory) so the LLM
        # doesn't over-fire it for things already on disk.
        desc = tools["web_search"].description
        assert "search_documents" in desc
        assert "search_personal_memory" in desc


class TestTavilyShape:
    def test_normalises_tavily_response(self, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "tvly-xxx")
        fake_resp = MagicMock()
        fake_resp.raise_for_status = MagicMock()
        fake_resp.json = MagicMock(return_value={
            "query": "test",
            "answer": "One-paragraph synthesis.",
            "results": [
                {"title": "T1", "url": "https://a.example",
                 "content": "snippet body 1", "score": 0.9},
                {"title": "T2", "url": "https://b.example",
                 "content": "snippet body 2", "score": 0.8},
            ],
        })
        fake_client = MagicMock()
        fake_client.__enter__ = MagicMock(return_value=fake_client)
        fake_client.__exit__ = MagicMock(return_value=False)
        fake_client.post = MagicMock(return_value=fake_resp)

        with patch("httpx.Client", return_value=fake_client):
            res = ws.search("test", max_results=5)

        assert res["source"] == "tavily"
        assert res["count"] == 2
        assert res["answer"] == "One-paragraph synthesis."
        assert res["results"][0]["url"] == "https://a.example"
        assert res["results"][0]["snippet"] == "snippet body 1"


class TestBraveShape:
    def test_normalises_brave_response(self, monkeypatch):
        monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "BSA-xxx")
        fake_resp = MagicMock()
        fake_resp.raise_for_status = MagicMock()
        fake_resp.json = MagicMock(return_value={
            "web": {
                "results": [
                    {"title": "B1", "url": "https://c.example",
                     "description": "brave snippet 1"},
                    {"title": "B2", "url": "https://d.example",
                     "description": "brave snippet 2"},
                ],
            },
        })
        fake_client = MagicMock()
        fake_client.__enter__ = MagicMock(return_value=fake_client)
        fake_client.__exit__ = MagicMock(return_value=False)
        fake_client.get = MagicMock(return_value=fake_resp)

        with patch("httpx.Client", return_value=fake_client):
            res = ws.search("test", max_results=2)

        assert res["source"] == "brave"
        assert res["count"] == 2
        assert res["answer"] is None
        assert res["results"][1]["snippet"] == "brave snippet 2"

    def test_empty_query_short_circuits(self, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "tvly-xxx")
        # Both whitespace-only and empty should return cleanly without
        # touching the network.
        res = ws.search("   ", max_results=5)
        assert res["count"] == 0
        assert res["results"] == []
