"""Tests for the v1.1 extension modules: webhooks, MCP, SCIM, email backends.

Coverage:
    - Webhook subscription CRUD + HMAC signing/verification
    - Webhook dispatch with sync delivery returning status
    - MCP tool builder produces tools for every registered skill + flow
    - MCP server handles initialize / tools/list / unknown method
    - SCIM mapping functions roundtrip
"""
from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.evaluation


# ------------------------------------------------------------ Webhooks ----

class TestWebhookCrud:
    def test_add_list_remove(self, tmp_storage):
        from praxia.webhooks import WebhookManager

        mgr = WebhookManager(storage_dir=tmp_storage)
        s = mgr.add(url="https://example.com/hook", event="flow.run.complete", secret="s")
        assert s.id
        assert s.event == "flow.run.complete"
        assert mgr.list() == [s] or any(x.id == s.id for x in mgr.list())
        assert mgr.remove(s.id) is True
        assert mgr.remove(s.id) is False
        assert all(x.id != s.id for x in mgr.list())

    def test_set_active(self, tmp_storage):
        from praxia.webhooks import WebhookManager

        mgr = WebhookManager(storage_dir=tmp_storage)
        s = mgr.add(url="https://example.com", event="*")
        result = mgr.set_active(s.id, False)
        assert result.active is False
        again = mgr.set_active(s.id, True)
        assert again.active is True


class TestWebhookSigning:
    def test_sign_verify_roundtrip(self):
        from praxia.webhooks import sign_payload, verify_payload

        body = b'{"event":"x","payload":{}}'
        sig = sign_payload(body, "shared-secret")
        assert sig.startswith("sha256=")
        assert verify_payload(body, "shared-secret", sig) is True
        assert verify_payload(b"tampered", "shared-secret", sig) is False
        assert verify_payload(body, "wrong-secret", sig) is False


class TestWebhookDispatch:
    def test_dispatch_no_subs_returns_empty(self, tmp_storage):
        from praxia.webhooks import WebhookManager

        mgr = WebhookManager(storage_dir=tmp_storage)
        deliveries = mgr.dispatch("flow.run.complete", {"id": "x"}, sync=True)
        assert deliveries == []

    def test_dispatch_to_unreachable_url_records_failure(self, tmp_storage):
        from praxia.webhooks import WebhookManager

        mgr = WebhookManager(storage_dir=tmp_storage, timeout_seconds=1.0)
        mgr.add(
            url="http://127.0.0.1:1/probably-no-server",
            event="*", secret="s",
        )
        deliveries = mgr.dispatch("test.ping", {"hello": "world"}, sync=True)
        assert len(deliveries) == 1
        assert deliveries[0].success is False
        assert deliveries[0].error  # some error message recorded

    def test_event_filter_excludes_non_matching(self, tmp_storage):
        from praxia.webhooks import WebhookManager

        mgr = WebhookManager(storage_dir=tmp_storage, timeout_seconds=1.0)
        mgr.add(url="http://127.0.0.1:1", event="flow.run.complete")
        mgr.add(url="http://127.0.0.1:1", event="*")
        # Only the wildcard sub matches a different event
        deliveries = mgr.dispatch("memory.consolidate.complete", {}, sync=True)
        assert len(deliveries) == 1


# ----------------------------------------------------------------- MCP ----

class TestMCPTools:
    def test_build_includes_skill_and_flow_tools(self):
        from praxia.mcp import build_tools

        tools = build_tools()
        names = {t.name for t in tools}
        # Skill tools
        assert "skill_investment_analyst" in names
        assert "skill_legal_reviewer" in names
        # Flow tools
        assert "flow_sales_agent_flow" in names
        # Utility tools
        assert "search_memory" in names
        assert "export_as" in names

    def test_each_tool_has_input_schema(self):
        from praxia.mcp import build_tools

        for t in build_tools():
            assert t.name
            assert t.description
            assert isinstance(t.input_schema, dict)
            assert t.input_schema.get("type") == "object"


class TestMCPServer:
    def test_initialize(self):
        from praxia.mcp import MCPServer

        server = MCPServer()
        resp = server.handle({
            "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {},
        })
        assert resp["id"] == 1
        assert resp["result"]["protocolVersion"]
        assert resp["result"]["serverInfo"]["name"] == "praxia-mcp"

    def test_tools_list(self):
        from praxia.mcp import MCPServer

        server = MCPServer()
        resp = server.handle({
            "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {},
        })
        assert "tools" in resp["result"]
        assert len(resp["result"]["tools"]) > 0

    def test_unknown_tool_returns_error(self):
        from praxia.mcp import MCPServer

        server = MCPServer()
        resp = server.handle({
            "jsonrpc": "2.0", "id": 3,
            "method": "tools/call",
            "params": {"name": "nonexistent_tool", "arguments": {}},
        })
        assert "error" in resp
        assert resp["error"]["code"] == -32602

    def test_unknown_method_returns_error(self):
        from praxia.mcp import MCPServer

        server = MCPServer()
        resp = server.handle({
            "jsonrpc": "2.0", "id": 4, "method": "made.up", "params": {},
        })
        assert "error" in resp
        assert resp["error"]["code"] == -32601

    def test_notification_returns_none(self):
        """Notifications (no `id`) must not produce a response."""
        from praxia.mcp import MCPServer

        server = MCPServer()
        resp = server.handle({
            "jsonrpc": "2.0", "method": "notifications/cancelled", "params": {},
        })
        assert resp is None


# ----------------------------------------------------------------- SCIM ---

class TestSCIMMapping:
    def test_praxia_user_to_scim(self):
        from praxia.scim import map_praxia_user_to_scim

        class FakeUser:
            id = "u-123"
            username = "alice"
            email = "alice@example.com"
            is_active = True
            created_at = 1714945200.0
            last_login_at = None

        scim = map_praxia_user_to_scim(FakeUser())
        d = scim.to_dict()
        assert d["userName"] == "alice"
        assert d["id"] == "u-123"
        assert d["active"] is True
        assert d["emails"][0]["value"] == "alice@example.com"
        assert "Users/u-123" in d["meta"]["location"]
        assert d["schemas"] == ["urn:ietf:params:scim:schemas:core:2.0:User"]

    def test_scim_to_praxia_kwargs(self):
        from praxia.scim import map_scim_user_to_praxia_kwargs

        kw = map_scim_user_to_praxia_kwargs({
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "userName": "bob",
            "emails": [{"value": "bob@example.com", "primary": True, "type": "work"}],
            "active": True,
        })
        assert kw["username"] == "bob"
        assert kw["email"] == "bob@example.com"
        assert kw["role"] is not None  # defaults to MEMBER

    def test_missing_username_raises(self):
        from praxia.scim import map_scim_user_to_praxia_kwargs

        with pytest.raises(ValueError):
            map_scim_user_to_praxia_kwargs({"schemas": [], "emails": []})


# ----------------------------------------------------------------- Email --

class TestEmailBackend:
    def test_invalid_backend_raises(self):
        from praxia.connectors.email_ import EmailConnector

        with pytest.raises(ValueError):
            EmailConnector(backend="ftp")  # Not a real backend

    def test_imap_backend_requires_creds(self, monkeypatch):
        from praxia.connectors.email_ import EmailConnector

        for env in (
            "PRAXIA_CONN_EMAIL_IMAP_HOST", "PRAXIA_CONN_EMAIL_USERNAME",
            "PRAXIA_CONN_EMAIL_PASSWORD",
        ):
            monkeypatch.delenv(env, raising=False)
        with pytest.raises(ValueError):
            EmailConnector(backend="imap")

    def test_gmail_backend_requires_token(self):
        from praxia.connectors.email_ import EmailConnector

        with pytest.raises(ValueError):
            EmailConnector(backend="gmail")
