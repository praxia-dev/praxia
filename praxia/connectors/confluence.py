"""Confluence connector — pull pages via CQL, push child pages.

Path semantics:
    pull:  CQL query (e.g. "space=ENG AND type=page AND text~'memory'")
           OR space-key/page-title (slash-separated shortcut)
    push:  parent page_id (creates a child page in the same space)

Uses the Atlassian Cloud REST API. On-prem Confluence Server is not yet
supported (different API shape).
"""
from __future__ import annotations

import json
from typing import Any
from urllib import parse, request

from praxia.connectors._helpers import resolve_oauth_token
from praxia.connectors.base import Connector, ConnectorItem, _require


class ConfluenceConnector:
    name = "confluence"

    def __init__(
        self,
        *,
        access_token: str | None = None,
        cloud_id: str | None = None,
        site_url: str | None = None,
        user_id: str | None = None,
    ) -> None:
        access_token = resolve_oauth_token(access_token, user_id, "atlassian")
        if not (cloud_id or site_url):
            raise ValueError(
                "Provide cloud_id (Atlassian cloud id) OR site_url "
                "(e.g. https://yourcompany.atlassian.net)."
            )
        self._token = access_token
        self._base = (
            f"https://api.atlassian.com/ex/confluence/{cloud_id}"
            if cloud_id
            else f"{site_url.rstrip('/')}/wiki"
        )

    def pull(self, path: str, *, limit: int = 25) -> list[ConnectorItem]:
        """Run a CQL query and return matching pages."""
        cql = path if any(c in path for c in (" ", "=", "~")) else f'title="{path}"'
        url = f"{self._base}/rest/api/content/search"
        params = {
            "cql": cql,
            "limit": min(limit, 50),
            "expand": "body.storage,space,version",
        }
        data = self._get(url, params)
        out: list[ConnectorItem] = []
        for r in data.get("results", []):
            body = (r.get("body") or {}).get("storage", {}).get("value", "")
            out.append(ConnectorItem(
                id=r["id"],
                name=r.get("title", ""),
                content=body,
                mime_type="text/html",  # Confluence storage = XHTML-like
                metadata={
                    "space": (r.get("space") or {}).get("key"),
                    "version": (r.get("version") or {}).get("number"),
                    "url": (r.get("_links") or {}).get("webui"),
                },
            ))
        return out

    def push(self, path: str, data: ConnectorItem | dict[str, Any]) -> dict[str, Any]:
        """Create a child page under `path` (parent page id)."""
        if isinstance(data, dict):
            data = ConnectorItem(**data)
        # Look up parent to inherit space
        parent_url = f"{self._base}/rest/api/content/{path}"
        parent = self._get(parent_url, {"expand": "space"})
        space_key = (parent.get("space") or {}).get("key")
        if not space_key:
            raise RuntimeError(f"Could not resolve space for parent page {path}")

        body_html = data.content if isinstance(data.content, str) else str(data.content)
        payload = {
            "type": "page",
            "title": data.name or "Untitled",
            "ancestors": [{"id": path}],
            "space": {"key": space_key},
            "body": {"storage": {"value": body_html, "representation": "storage"}},
        }
        result = self._post(f"{self._base}/rest/api/content", payload)
        return {
            "id": result["id"],
            "url": (result.get("_links") or {}).get("webui"),
        }

    # --- HTTP helpers (no SDK to keep deps minimal) ----------------------

    def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        full = url + "?" + parse.urlencode(params)
        req = request.Request(full, headers=self._headers())
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
