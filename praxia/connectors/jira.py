"""Jira connector — pull issues via JQL, push (create) new issues.

Path semantics:
    pull:  JQL query (e.g. "project = ENG AND status = 'In Progress'")
           OR project key (returns recent issues)
    push:  project key (creates an issue inside that project)

Uses the Atlassian Cloud REST API v3.
"""
from __future__ import annotations

import json
from typing import Any
from urllib import parse, request

from praxia.connectors._helpers import resolve_oauth_token
from praxia.connectors.base import Connector, ConnectorItem


class JiraConnector:
    name = "jira"

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
                "Provide cloud_id OR site_url (e.g. https://yourcompany.atlassian.net)."
            )
        self._token = access_token
        self._base = (
            f"https://api.atlassian.com/ex/jira/{cloud_id}"
            if cloud_id
            else site_url.rstrip("/")
        )

    def pull(self, path: str, *, limit: int = 50) -> list[ConnectorItem]:
        """Search issues via JQL or project-key shortcut."""
        jql = path if any(k in path for k in ("=", " ", "~")) else f"project = {path}"
        url = f"{self._base}/rest/api/3/search"
        params = {
            "jql": jql,
            "maxResults": min(limit, 100),
            "fields": "summary,description,status,assignee,priority,labels,issuetype,updated",
        }
        data = self._get(url, params)
        out: list[ConnectorItem] = []
        for issue in data.get("issues", []):
            f = issue.get("fields", {})
            assignee = (f.get("assignee") or {}).get("displayName") or "(unassigned)"
            content = self._issue_to_text(issue)
            out.append(ConnectorItem(
                id=issue["key"],
                name=f.get("summary", ""),
                content=content,
                mime_type="text/markdown",
                metadata={
                    "status": (f.get("status") or {}).get("name"),
                    "type": (f.get("issuetype") or {}).get("name"),
                    "priority": (f.get("priority") or {}).get("name"),
                    "assignee": assignee,
                    "updated": f.get("updated"),
                    "labels": f.get("labels", []),
                },
            ))
        return out

    def push(self, path: str, data: ConnectorItem | dict[str, Any]) -> dict[str, Any]:
        """Create a Jira issue inside project `path`."""
        if isinstance(data, dict):
            data = ConnectorItem(**data)
        body = data.content if isinstance(data.content, str) else str(data.content)
        meta = data.metadata or {}
        payload = {
            "fields": {
                "project": {"key": path},
                "summary": (data.name or "(no title)")[:255],
                "issuetype": {"name": meta.get("issuetype", "Task")},
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [{
                        "type": "paragraph",
                        "content": [{"type": "text", "text": body[:30000]}],
                    }],
                },
            }
        }
        if meta.get("labels"):
            payload["fields"]["labels"] = list(meta["labels"])
        if meta.get("priority"):
            payload["fields"]["priority"] = {"name": meta["priority"]}
        url = f"{self._base}/rest/api/3/issue"
        result = self._post(url, payload)
        return {"key": result["key"], "id": result["id"], "url": result.get("self")}

    @staticmethod
    def _issue_to_text(issue: dict) -> str:
        f = issue.get("fields", {})
        desc = f.get("description")
        if isinstance(desc, dict):
            # Atlassian Document Format → flat text
            desc = "".join(
                c.get("text", "")
                for blk in (desc.get("content") or [])
                for c in (blk.get("content") or [])
            )
        return f"# {f.get('summary', '')}\n\n{desc or ''}"

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
