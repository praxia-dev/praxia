"""HTML exporter — minimal Markdown-to-HTML renderer (no external deps).

Supports headings (#..######), bold (**), italic (*), inline code (`),
fenced code blocks (```), unordered lists (-), ordered lists (1.),
blockquotes (>), links ([t](u)), and paragraphs. Good enough for
delivering skill output to the browser without pulling in `markdown`.
"""
from __future__ import annotations

import html
import re
from typing import Any


_DEFAULT_CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       max-width: 760px; margin: 2rem auto; padding: 0 1rem; color: #222; line-height: 1.6; }
h1, h2, h3, h4 { color: #111; margin-top: 1.6em; }
code { background: #f4f4f4; padding: 0.15em 0.4em; border-radius: 3px;
       font-family: 'SFMono-Regular', Consolas, monospace; font-size: 0.92em; }
pre { background: #f4f4f4; padding: 1em; border-radius: 6px; overflow-x: auto; }
pre code { background: none; padding: 0; }
blockquote { border-left: 3px solid #ccc; margin: 1em 0; padding-left: 1em; color: #555; }
table { border-collapse: collapse; }
th, td { border: 1px solid #ddd; padding: 0.4em 0.7em; }
a { color: #0066cc; }
""".strip()


class HtmlExporter:
    format = "html"
    extensions = ("html", "htm")

    def __init__(
        self,
        *,
        title: str = "Praxia Output",
        css: str | None = None,
        wrap_in_document: bool = True,
        lang: str = "en",
    ) -> None:
        self.title = title
        self.css = css if css is not None else _DEFAULT_CSS
        self.wrap_in_document = wrap_in_document
        self.lang = lang

    def export(self, content: Any) -> bytes:
        if isinstance(content, dict):
            content = self._dict_to_md(content)
        elif not isinstance(content, str):
            content = str(content)

        body_html = self._md_to_html(content)
        if not self.wrap_in_document:
            return body_html.encode("utf-8")

        doc = (
            f"<!DOCTYPE html>\n"
            f'<html lang="{html.escape(self.lang)}">\n'
            f"<head>\n"
            f'<meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f"<title>{html.escape(self.title)}</title>\n"
            f"<style>{self.css}</style>\n"
            f"</head>\n<body>\n{body_html}\n</body>\n</html>\n"
        )
        return doc.encode("utf-8")

    @staticmethod
    def _dict_to_md(d: dict[str, Any]) -> str:
        from praxia.io.exporters.md_exporter import MarkdownExporter
        return MarkdownExporter._dict_to_md(d)

    def _md_to_html(self, md: str) -> str:
        out: list[str] = []
        in_code = False
        code_lang = ""
        code_buf: list[str] = []
        list_stack: list[str] = []  # "ul" / "ol"

        def flush_lists() -> None:
            while list_stack:
                out.append(f"</{list_stack.pop()}>")

        for raw_line in md.splitlines():
            line = raw_line.rstrip()

            # Fenced code block
            if line.startswith("```"):
                if in_code:
                    out.append(
                        f'<pre><code class="lang-{html.escape(code_lang)}">'
                        f"{html.escape(chr(10).join(code_buf))}</code></pre>"
                    )
                    in_code = False
                    code_lang = ""
                    code_buf = []
                else:
                    flush_lists()
                    in_code = True
                    code_lang = line[3:].strip()
                continue
            if in_code:
                code_buf.append(line)
                continue

            stripped = line.lstrip()
            indent = len(line) - len(stripped)

            # Headings
            m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
            if m:
                flush_lists()
                level = len(m.group(1))
                text = self._inline(m.group(2))
                out.append(f"<h{level}>{text}</h{level}>")
                continue

            # Blockquote
            if stripped.startswith(">"):
                flush_lists()
                out.append(f"<blockquote>{self._inline(stripped[1:].strip())}</blockquote>")
                continue

            # Unordered list
            if re.match(r"^[-*+]\s+", stripped):
                if not list_stack or list_stack[-1] != "ul":
                    flush_lists()
                    out.append("<ul>")
                    list_stack.append("ul")
                item = re.sub(r"^[-*+]\s+", "", stripped)
                out.append(f"  <li>{self._inline(item)}</li>")
                continue

            # Ordered list
            if re.match(r"^\d+\.\s+", stripped):
                if not list_stack or list_stack[-1] != "ol":
                    flush_lists()
                    out.append("<ol>")
                    list_stack.append("ol")
                item = re.sub(r"^\d+\.\s+", "", stripped)
                out.append(f"  <li>{self._inline(item)}</li>")
                continue

            # Blank line
            if not stripped:
                flush_lists()
                continue

            # Paragraph
            flush_lists()
            out.append(f"<p>{self._inline(stripped)}</p>")

        if in_code:
            out.append(
                f"<pre><code>{html.escape(chr(10).join(code_buf))}</code></pre>"
            )
        flush_lists()
        return "\n".join(out)

    @staticmethod
    def _inline(text: str) -> str:
        text = html.escape(text, quote=False)
        # Code spans
        text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
        # Bold
        text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", text)
        # Italic
        text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
        # Links
        text = re.sub(
            r"\[([^\]]+)\]\(([^)]+)\)",
            lambda m: f'<a href="{html.escape(m.group(2), quote=True)}">{m.group(1)}</a>',
            text,
        )
        return text
