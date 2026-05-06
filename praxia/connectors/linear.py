"""Linear connector — pull issues via GraphQL, push (create) issues.

Path semantics:
    pull:  team_key (e.g. "ENG")  — recent issues in that team
           "search:<query>"        — fuzzy search across issues
    push:  team_key                — create an issue in that team
"""
from __future__ import annotations

import json
from typing import Any
from urllib import request

from praxia.connectors.base import Connector, ConnectorItem


LINEAR_GRAPHQL = "https://api.linear.app/graphql"


class LinearConnector:
    name = "linear"

    def __init__(
        self,
        *,
        access_token: str | None = None,
        api_key: str | None = None,
        user_id: str | None = None,
    ) -> None:
        if user_id and not (access_token or api_key):
            from praxia.connectors.oauth import oauth_token_for
            access_token = oauth_token_for(user_id, "linear").access_token
        token = access_token or api_key
        if not token:
            raise ValueError(
                "Provide access_token, api_key, or user_id (with OAuth token)."
            )
        # Linear accepts both "Bearer <oauth>" and the raw API key
        self._auth = (
            f"Bearer {token}" if access_token else token
        )

    def pull(self, path: str, *, limit: int = 50) -> list[ConnectorItem]:
        if path.startswith("search:"):
            return self._search(path[len("search:"):], limit=limit)
        return self._team_issues(path, limit=limit)

    def push(self, path: str, data: ConnectorItem | dict[str, Any]) -> dict[str, Any]:
        if isinstance(data, dict):
            data = ConnectorItem(**data)
        # Look up team id by key
        team = self._gql(
            "query($key:String!){ teams(filter:{key:{eq:$key}}){ nodes{ id key name } } }",
            {"key": path},
        )
        nodes = (team.get("data", {}).get("teams", {}) or {}).get("nodes", [])
        if not nodes:
            raise RuntimeError(f"Linear team key not found: {path}")
        team_id = nodes[0]["id"]

        body = data.content if isinstance(data.content, str) else str(data.content)
        meta = data.metadata or {}
        result = self._gql(
            """
            mutation($input: IssueCreateInput!) {
              issueCreate(input: $input) {
                success
                issue { id identifier title url }
              }
            }
            """,
            {"input": {
                "teamId": team_id,
                "title": (data.name or "(no title)")[:255],
                "description": body,
                "priority": int(meta.get("priority", 0)) or None,
            }},
        )
        issue = result["data"]["issueCreate"]["issue"]
        return {"id": issue["id"], "identifier": issue["identifier"], "url": issue["url"]}

    # --- helpers ---------------------------------------------------------

    def _team_issues(self, team_key: str, *, limit: int) -> list[ConnectorItem]:
        result = self._gql(
            """
            query($key: String!, $first: Int!) {
              team(id: $key) {
                issues(first: $first, orderBy: updatedAt) {
                  nodes {
                    id identifier title description state { name } priority url updatedAt
                    assignee { name }
                    labels { nodes { name } }
                  }
                }
              }
            }
            """,
            {"key": team_key, "first": min(limit, 50)},
        )
        nodes = (result.get("data", {}).get("team") or {}).get("issues", {}).get("nodes", []) or []
        return [self._issue_to_item(n) for n in nodes]

    def _search(self, query: str, *, limit: int) -> list[ConnectorItem]:
        result = self._gql(
            """
            query($q: String!, $first: Int!) {
              issueSearch(query: $q, first: $first) {
                nodes {
                  id identifier title description state { name } priority url updatedAt
                  assignee { name }
                  labels { nodes { name } }
                }
              }
            }
            """,
            {"q": query, "first": min(limit, 50)},
        )
        nodes = (result.get("data", {}).get("issueSearch") or {}).get("nodes", []) or []
        return [self._issue_to_item(n) for n in nodes]

    @staticmethod
    def _issue_to_item(n: dict) -> ConnectorItem:
        labels = [l["name"] for l in ((n.get("labels") or {}).get("nodes") or [])]
        return ConnectorItem(
            id=n["identifier"],
            name=n.get("title", ""),
            content=n.get("description", "") or "",
            mime_type="text/markdown",
            metadata={
                "state": (n.get("state") or {}).get("name"),
                "priority": n.get("priority"),
                "labels": labels,
                "assignee": (n.get("assignee") or {}).get("name"),
                "url": n.get("url"),
                "updated_at": n.get("updatedAt"),
            },
        )

    def _gql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps({"query": query, "variables": variables}).encode()
        req = request.Request(
            LINEAR_GRAPHQL,
            data=body,
            headers={
                "Authorization": self._auth,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        if "errors" in data:
            raise RuntimeError(f"Linear GraphQL error: {data['errors']}")
        return data
