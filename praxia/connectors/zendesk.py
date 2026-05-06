"""Zendesk Support connector — pull tickets, push (create) tickets.

Path semantics:
    pull:  "tickets:<query>" — Search tickets via Zendesk Search API
           "tickets"          — Recent tickets
           "<ticket_id>"      — Single ticket with comments
    push:  always creates a new ticket (path is ignored or used for tags)

Auth: per-user OAuth (recommended) OR API token.
For API-token auth, set:
    PRAXIA_CONN_ZENDESK_SUBDOMAIN, PRAXIA_CONN_ZENDESK_EMAIL, PRAXIA_CONN_ZENDESK_API_TOKEN
"""
from __future__ import annotations

import base64
import json
import os
from typing import Any
from urllib import parse, request

from praxia.connectors.base import Connector, ConnectorItem


class ZendeskConnector:
    name = "zendesk"

    def __init__(
        self,
        *,
        subdomain: str | None = None,
        access_token: str | None = None,
        email: str | None = None,
        api_token: str | None = None,
        user_id: str | None = None,
    ) -> None:
        subdomain = subdomain or os.getenv("PRAXIA_CONN_ZENDESK_SUBDOMAIN")
        if not subdomain:
            raise ValueError(
                "Provide subdomain (your Zendesk subdomain, e.g. 'acme' for acme.zendesk.com)"
            )
        self._base = f"https://{subdomain}.zendesk.com/api/v2"

        if user_id and not (access_token or api_token):
            from praxia.connectors.oauth import oauth_token_for
            access_token = oauth_token_for(user_id, "zendesk").access_token

        # Choose auth header
        if access_token:
            self._auth = f"Bearer {access_token}"
        elif email and api_token:
            creds = f"{email}/token:{api_token}".encode()
            self._auth = "Basic " + base64.b64encode(creds).decode()
        elif (
            os.getenv("PRAXIA_CONN_ZENDESK_EMAIL")
            and os.getenv("PRAXIA_CONN_ZENDESK_API_TOKEN")
        ):
            creds = (
                f"{os.environ['PRAXIA_CONN_ZENDESK_EMAIL']}/token:"
                f"{os.environ['PRAXIA_CONN_ZENDESK_API_TOKEN']}"
            ).encode()
            self._auth = "Basic " + base64.b64encode(creds).decode()
        else:
            raise ValueError(
                "Provide one of: access_token, (email + api_token), or user_id (with OAuth)."
            )

    def pull(self, path: str, *, limit: int = 25) -> list[ConnectorItem]:
        if path.startswith("tickets:"):
            return self._search(path[len("tickets:"):], limit=limit)
        if path == "tickets" or path == "":
            return self._recent_tickets(limit=limit)
        return self._single_ticket(path)

    def push(self, path: str, data: ConnectorItem | dict[str, Any]) -> dict[str, Any]:
        if isinstance(data, dict):
            data = ConnectorItem(**data)
        body = data.content if isinstance(data.content, str) else str(data.content)
        meta = data.metadata or {}
        payload = {
            "ticket": {
                "subject": (data.name or "(no subject)")[:150],
                "comment": {"body": body[:65000]},
                "priority": meta.get("priority", "normal"),
                "tags": meta.get("tags", []),
            }
        }
        result = self._post("/tickets.json", payload)
        return {"id": result["ticket"]["id"], "url": result["ticket"]["url"]}

    # --- helpers ---------------------------------------------------------

    def _recent_tickets(self, *, limit: int) -> list[ConnectorItem]:
        data = self._get(f"/tickets.json?per_page={min(limit, 100)}")
        return [self._ticket_to_item(t) for t in data.get("tickets", [])]

    def _search(self, query: str, *, limit: int) -> list[ConnectorItem]:
        url = f"/search.json?query=type:ticket {query}&per_page={min(limit, 100)}"
        data = self._get(url)
        return [self._ticket_to_item(t) for t in data.get("results", [])]

    def _single_ticket(self, ticket_id: str) -> list[ConnectorItem]:
        data = self._get(f"/tickets/{ticket_id}.json")
        return [self._ticket_to_item(data["ticket"])]

    @staticmethod
    def _ticket_to_item(t: dict) -> ConnectorItem:
        return ConnectorItem(
            id=str(t.get("id")),
            name=t.get("subject", ""),
            content=t.get("description", ""),
            mime_type="text/plain",
            metadata={
                "status": t.get("status"),
                "priority": t.get("priority"),
                "tags": t.get("tags", []),
                "url": t.get("url"),
                "updated_at": t.get("updated_at"),
            },
        )

    def _get(self, path: str) -> dict[str, Any]:
        url = self._base + path
        req = request.Request(url, headers={
            "Authorization": self._auth,
            "Accept": "application/json",
        })
        with request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        url = self._base + path
        req = request.Request(
            url,
            data=json.dumps(body).encode(),
            headers={
                "Authorization": self._auth,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
