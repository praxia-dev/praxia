"""Slack connector — pull channel history, push messages.

Path semantics:
    pull:  channel ID (e.g. "C0123ABCD") — returns last N messages
           OR "search:<query>" — returns matches via search.messages
    push:  channel ID — posts a message (text or markdown)
"""
from __future__ import annotations

import json
from typing import Any
from urllib import parse, request

from praxia.connectors.base import Connector, ConnectorItem


class SlackConnector:
    name = "slack"

    def __init__(
        self,
        *,
        access_token: str | None = None,
        user_id: str | None = None,
    ) -> None:
        if user_id and not access_token:
            from praxia.connectors.oauth import oauth_token_for
            access_token = oauth_token_for(user_id, "slack").access_token
        if not access_token:
            raise ValueError(
                "Provide access_token or user_id (with a stored Slack OAuth token)."
            )
        self._token = access_token

    def pull(self, path: str, *, limit: int = 50) -> list[ConnectorItem]:
        if path.startswith("search:"):
            return self._search(path[len("search:"):], limit=limit)
        return self._channel_history(path, limit=limit)

    def push(self, path: str, data: ConnectorItem | dict[str, Any]) -> dict[str, Any]:
        if isinstance(data, dict):
            data = ConnectorItem(**data)
        body = data.content if isinstance(data.content, str) else str(data.content)
        # Pre-pend title as bold if present
        if data.name:
            body = f"*{data.name}*\n{body}"
        result = self._call("chat.postMessage", {
            "channel": path,
            "text": body[:39000],   # Slack limit ~40k
            "mrkdwn": True,
        })
        if not result.get("ok"):
            raise RuntimeError(f"Slack chat.postMessage failed: {result.get('error')}")
        return {"ts": result.get("ts"), "channel": result.get("channel")}

    # --- helpers ---------------------------------------------------------

    def _channel_history(self, channel: str, *, limit: int) -> list[ConnectorItem]:
        result = self._call("conversations.history", {
            "channel": channel,
            "limit": min(limit, 200),
        })
        if not result.get("ok"):
            raise RuntimeError(f"Slack conversations.history failed: {result.get('error')}")
        out: list[ConnectorItem] = []
        for msg in result.get("messages", []):
            out.append(ConnectorItem(
                id=msg.get("ts"),
                name=msg.get("user", "(unknown)"),
                content=msg.get("text", ""),
                mime_type="text/plain",
                metadata={
                    "channel": channel,
                    "ts": msg.get("ts"),
                    "thread_ts": msg.get("thread_ts"),
                    "reactions": msg.get("reactions", []),
                },
            ))
        return out

    def _search(self, query: str, *, limit: int) -> list[ConnectorItem]:
        result = self._call("search.messages", {"query": query, "count": min(limit, 100)})
        if not result.get("ok"):
            raise RuntimeError(f"Slack search.messages failed: {result.get('error')}")
        out: list[ConnectorItem] = []
        for m in (result.get("messages", {}).get("matches", []) or []):
            out.append(ConnectorItem(
                id=m.get("ts", m.get("iid", "")),
                name=(m.get("username") or m.get("user") or "(unknown)"),
                content=m.get("text", ""),
                mime_type="text/plain",
                metadata={
                    "channel": (m.get("channel") or {}).get("id"),
                    "permalink": m.get("permalink"),
                },
            ))
        return out

    def _call(self, method: str, body: dict[str, Any]) -> dict[str, Any]:
        url = f"https://slack.com/api/{method}"
        # Slack accepts JSON for write methods, form-urlencoded for reads
        if method.startswith(("conversations.", "search.")):
            url = url + "?" + parse.urlencode(body)
            req = request.Request(url, headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/json",
            })
        else:
            req = request.Request(
                url,
                data=json.dumps(body).encode(),
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Content-Type": "application/json; charset=utf-8",
                },
                method="POST",
            )
        with request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
