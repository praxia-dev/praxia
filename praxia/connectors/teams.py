"""Microsoft Teams connector — pull channel messages, push new messages.

Reuses the existing Microsoft OAuth token (`microsoft` provider) — Teams
uses the same Microsoft Graph API as SharePoint.

Path semantics:
    pull:  "<team_id>/<channel_id>" — returns recent messages in the channel
    push:  "<team_id>/<channel_id>" — posts a new chat message

Note: Microsoft Teams chat APIs require additional consent
(`ChannelMessage.Read.All` + `ChannelMessage.Send`). The default scope set
in MICROSOFT_OAUTH covers Sites/Files; for Teams you need to extend the
authorization scope at OAuth registration time.
"""
from __future__ import annotations

import json
from typing import Any
from urllib import parse, request

from praxia.connectors._helpers import resolve_oauth_token
from praxia.connectors.base import Connector, ConnectorItem


GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class TeamsConnector:
    name = "teams"

    def __init__(
        self,
        *,
        access_token: str | None = None,
        user_id: str | None = None,
    ) -> None:
        self._token = resolve_oauth_token(
            access_token, user_id, "microsoft",
            error_hint="Token must include ChannelMessage.* scopes for Teams.",
        )

    def pull(self, path: str, *, limit: int = 50) -> list[ConnectorItem]:
        team_id, channel_id = self._split_path(path)
        url = (
            f"{GRAPH_BASE}/teams/{team_id}/channels/{channel_id}/messages"
            f"?$top={min(limit, 50)}"
        )
        data = self._get(url)
        out: list[ConnectorItem] = []
        for m in data.get("value", []):
            content = (m.get("body") or {}).get("content", "")
            from_user = ((m.get("from") or {}).get("user") or {}).get("displayName", "")
            out.append(ConnectorItem(
                id=m.get("id", ""),
                name=from_user or "(unknown)",
                content=content,
                mime_type=(m.get("body") or {}).get("contentType", "text/html"),
                metadata={
                    "team_id": team_id,
                    "channel_id": channel_id,
                    "created": m.get("createdDateTime"),
                    "subject": m.get("subject"),
                },
            ))
        return out

    def push(self, path: str, data: ConnectorItem | dict[str, Any]) -> dict[str, Any]:
        if isinstance(data, dict):
            data = ConnectorItem(**data)
        team_id, channel_id = self._split_path(path)
        body = data.content if isinstance(data.content, str) else str(data.content)
        # Detect HTML vs plain
        content_type = data.mime_type if "html" in (data.mime_type or "") else "text"
        url = f"{GRAPH_BASE}/teams/{team_id}/channels/{channel_id}/messages"
        payload: dict[str, Any] = {
            "body": {"contentType": content_type, "content": body[:28000]},
        }
        if data.name:
            payload["subject"] = data.name[:255]
        result = self._post(url, payload)
        return {"id": result.get("id"), "etag": result.get("etag")}

    @staticmethod
    def _split_path(path: str) -> tuple[str, str]:
        parts = path.split("/", 1)
        if len(parts) != 2:
            raise ValueError(
                f"Teams path must be '<team_id>/<channel_id>' — got {path!r}"
            )
        return parts[0], parts[1]

    def _get(self, url: str) -> dict[str, Any]:
        req = request.Request(url, headers=self._headers())
        with request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())

    def _post(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
        req = request.Request(
            url,
            data=json.dumps(body).encode(),
            headers={**self._headers(), "Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}", "Accept": "application/json"}
