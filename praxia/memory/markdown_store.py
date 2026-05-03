"""Markdown + git frozen layer (Layer 4).

Once a shared block has been reviewed and stabilized, it can be "frozen" into
a Markdown file in a repo for PR-driven curation. Format is GitHub-Copilot /
Cursor-rules compatible so AI tools pick it up automatically.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def _import_frontmatter():  # type: ignore[no-untyped-def]
    """Lazy import — only required when freezing/listing entries."""
    try:
        import frontmatter  # type: ignore[import-untyped]
        return frontmatter
    except ImportError as e:  # pragma: no cover
        raise ImportError(
            "python-frontmatter is required for MarkdownStore. "
            "Install with: pip install praxia"
        ) from e


@dataclass
class FrozenEntry:
    title: str
    description: str
    body: str
    tags: list[str]
    path: Path


class MarkdownStore:
    """Writes promoted knowledge to versioned Markdown files.

    Layout:
        instructions/
            <topic>.md           — generic guidance
        playbooks/
            <topic>.md           — multi-step procedures
        skills/
            <skill_name>/SKILL.md — promoted skills

    Each file uses YAML frontmatter:
        ---
        title: ...
        description: ...
        tags: [sales, manufacturing]
        ---
        body...
    """

    def __init__(self, root_dir: Path | str = ".praxia/frozen") -> None:
        self.root = Path(root_dir)
        for sub in ("instructions", "playbooks", "skills"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    def freeze_instruction(
        self,
        *,
        title: str,
        description: str,
        body: str,
        tags: list[str] | None = None,
    ) -> Path:
        return self._write("instructions", title, description, body, tags or [])

    def freeze_playbook(
        self,
        *,
        title: str,
        description: str,
        body: str,
        tags: list[str] | None = None,
    ) -> Path:
        return self._write("playbooks", title, description, body, tags or [])

    def freeze_skill(
        self,
        *,
        skill_name: str,
        description: str,
        body: str,
        tags: list[str] | None = None,
    ) -> Path:
        target = self.root / "skills" / skill_name
        target.mkdir(parents=True, exist_ok=True)
        path = target / "SKILL.md"
        frontmatter = _import_frontmatter()
        post = frontmatter.Post(
            body,
            title=skill_name,
            description=description,
            tags=tags or [],
        )
        with path.open("w", encoding="utf-8") as f:
            f.write(frontmatter.dumps(post))
        return path

    def _write(
        self,
        bucket: str,
        title: str,
        description: str,
        body: str,
        tags: list[str],
    ) -> Path:
        slug = "".join(c if c.isalnum() else "_" for c in title.lower()).strip("_")
        path = self.root / bucket / f"{slug}.md"
        frontmatter = _import_frontmatter()
        post = frontmatter.Post(body, title=title, description=description, tags=tags)
        with path.open("w", encoding="utf-8") as f:
            f.write(frontmatter.dumps(post))
        return path

    def list_all(self) -> list[FrozenEntry]:
        frontmatter = _import_frontmatter()
        out: list[FrozenEntry] = []
        for path in self.root.rglob("*.md"):
            try:
                post = frontmatter.load(path)
            except Exception:
                continue
            out.append(
                FrozenEntry(
                    title=post.metadata.get("title", path.stem),
                    description=post.metadata.get("description", ""),
                    body=post.content,
                    tags=post.metadata.get("tags", []),
                    path=path,
                )
            )
        return out
