"""Notion connector — pull database rows / pages, push child pages.

Path semantics:
    pull:  database_id (UUID-style, with or without hyphens)
    push:  parent page_id (creates a child page with title + markdown body)
"""
from __future__ import annotations

from typing import Any

from praxia.connectors.base import Connector, ConnectorItem, _require


class NotionConnector:
    name = "notion"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        user_id: str | None = None,
    ) -> None:
        notion_client = _require("notion_client", "pip install notion-client")
        if user_id and not api_key:
            from praxia.connectors.oauth import oauth_token_for
            api_key = oauth_token_for(user_id, "notion").access_token
        if not api_key:
            raise ValueError(
                "Provide api_key or user_id (with a stored OAuth token)."
            )
        self._client = notion_client.Client(auth=api_key)

    def pull(self, path: str, *, limit: int = 100) -> list[ConnectorItem]:
        """Query a Notion database; emit one ConnectorItem per row."""
        results = self._client.databases.query(
            database_id=path, page_size=min(limit, 100)
        )
        out: list[ConnectorItem] = []
        for page in results.get("results", []):
            title = self._extract_title(page)
            content = self._page_to_text(page)
            out.append(ConnectorItem(
                id=page["id"],
                name=title or page["id"],
                content=content,
                mime_type="text/markdown",
                metadata={
                    "notion_url": page.get("url"),
                    "kind": "database_row",
                    "last_edited_time": page.get("last_edited_time"),
                },
            ))
        return out

    def push(self, path: str, data: ConnectorItem | dict[str, Any]) -> dict[str, Any]:
        """Create a child page under `path` (parent page id)."""
        if isinstance(data, dict):
            data = ConnectorItem(**data)
        title = data.name or "Untitled"
        body = data.content if isinstance(data.content, str) else str(data.content)
        result = self._client.pages.create(
            parent={"page_id": path},
            properties={"title": [{"text": {"content": title[:200]}}]},
            children=self._markdown_to_blocks(body),
        )
        return {"id": result["id"], "url": result.get("url")}

    @staticmethod
    def _extract_title(page: dict) -> str:
        props = page.get("properties", {})
        for prop in props.values():
            if prop.get("type") == "title":
                title_arr = prop.get("title", [])
                return "".join(t.get("plain_text", "") for t in title_arr)
        return ""

    @staticmethod
    def _page_to_text(page: dict) -> str:
        # Light-weight: serialize properties as YAML-like front-matter
        lines = []
        for name, prop in (page.get("properties") or {}).items():
            kind = prop.get("type")
            if kind == "title":
                txt = "".join(t.get("plain_text", "") for t in prop.get("title", []))
            elif kind == "rich_text":
                txt = "".join(t.get("plain_text", "") for t in prop.get("rich_text", []))
            elif kind == "select":
                txt = (prop.get("select") or {}).get("name", "")
            elif kind == "multi_select":
                txt = ", ".join(s.get("name", "") for s in prop.get("multi_select", []))
            elif kind == "date":
                txt = (prop.get("date") or {}).get("start", "")
            elif kind == "number":
                txt = str(prop.get("number", ""))
            elif kind == "checkbox":
                txt = "✓" if prop.get("checkbox") else ""
            else:
                txt = ""
            if txt:
                lines.append(f"{name}: {txt}")
        return "\n".join(lines)

    @staticmethod
    def _markdown_to_blocks(md: str) -> list[dict[str, Any]]:
        """Minimal Markdown → Notion blocks. One paragraph block per line."""
        blocks: list[dict[str, Any]] = []
        for line in (md or "").splitlines():
            line = line.rstrip()
            if not line:
                continue
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": line[:2000]}}],
                },
            })
        return blocks or [{
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": ""}}]},
        }]
