"""Markdown exporter — passthrough with optional frontmatter."""
from __future__ import annotations

from typing import Any


class MarkdownExporter:
    format = "md"
    extensions = ("md", "markdown")

    def __init__(
        self,
        *,
        title: str | None = None,
        author: str | None = None,
        frontmatter: dict[str, Any] | None = None,
    ) -> None:
        self.title = title
        self.author = author
        self.frontmatter = frontmatter or {}

    def export(self, content: Any) -> bytes:
        if isinstance(content, dict):
            content = self._dict_to_md(content)
        elif not isinstance(content, str):
            content = str(content)

        if self.frontmatter or self.title or self.author:
            fm = dict(self.frontmatter)
            if self.title and "title" not in fm:
                fm["title"] = self.title
            if self.author and "author" not in fm:
                fm["author"] = self.author
            header = "---\n"
            for k, v in fm.items():
                header += f"{k}: {v}\n"
            header += "---\n\n"
            content = header + content

        return content.encode("utf-8")

    @staticmethod
    def _dict_to_md(d: dict[str, Any]) -> str:
        lines: list[str] = []
        title = d.get("title")
        if title:
            lines.append(f"# {title}")
            lines.append("")
        for section in d.get("sections", []) or []:
            heading = section.get("heading")
            body = section.get("body", "")
            if heading:
                lines.append(f"## {heading}")
                lines.append("")
            if body:
                lines.append(body)
                lines.append("")
        return "\n".join(lines).strip() + "\n"
