"""Document themes — corporate styling for designer-skill outputs.

A `DocumentTheme` is a simple JSON file plus optional sibling assets
(logo, slide-master) stored under `.praxia/themes/<name>/`. The
designer skill passes the theme contents into the meta-prompt so the
LLM-authored python-pptx / python-docx code uses the right colors,
fonts, and brand chrome.

Filesystem layout:

    .praxia/themes/
    ├── ricoh_corporate/
    │   ├── theme.json
    │   ├── logo.png            (optional)
    │   └── master.pptx         (optional, used as base in PptxDesigner)
    ├── pastel_minimal/
    │   └── theme.json
    └── ...

theme.json schema:

    {
        "name": "ricoh_corporate",
        "colors": {
            "primary": "#003c8c",
            "accent": "#e60012",
            "background": "#ffffff",
            "muted": "#6b7280",
            "text": "#1a1a1a"
        },
        "fonts": {
            "heading": "Meiryo",
            "body": "Meiryo",
            "code": "Consolas",
            "heading_size_pt": 28,
            "body_size_pt": 16
        },
        "footer_text": "© 2026 Acme Corp.",
        "layouts": ["title", "bullets", "two_column", "comparison",
                    "matrix_2x2", "image_full"]
    }
"""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


_DEFAULT_LAYOUTS = (
    "title", "bullets", "two_column", "comparison", "matrix_2x2", "image_full",
)

_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


@dataclass
class DocumentTheme:
    """Color / font / asset bundle for designer skills.

    All fields are optional with sensible defaults so the meta-prompt can
    always emit a complete code snippet. Path fields (`logo_path`,
    `slide_master_path`) are absolute when loaded from disk.
    """

    name: str = "default"
    # A *non-neutral* default. The previous default was primary=#1f2937 +
    # background=#ffffff, which the LLM dutifully respected and produced
    # decks identical to the bare exporter: white slides, dark text, no
    # visual chrome. The default theme now has a deeper-blue primary and
    # a warm gold accent so even a minimally-styled output ("title bar +
    # bullets") has obvious brand colour.
    colors: dict[str, str] = field(default_factory=lambda: {
        "primary": "#1f3a8a",      # indigo-900 — strong title bars + heading text
        "accent": "#f59e0b",       # amber-500 — call-out fills, divider rules
        "background": "#f8fafc",   # slate-50  — gentle off-white, hides any seams
        "muted": "#64748b",        # slate-500 — secondary text / captions
        "text": "#0f172a",         # slate-900 — body
    })
    fonts: dict[str, str | int] = field(default_factory=lambda: {
        "heading": "Calibri",
        "body": "Calibri",
        "code": "Consolas",
        "heading_size_pt": 28,
        "body_size_pt": 16,
    })
    logo_path: str | None = None
    footer_text: str | None = None
    slide_master_path: str | None = None
    layouts: list[str] = field(default_factory=lambda: list(_DEFAULT_LAYOUTS))

    # ------------------------------------------------------------------
    # I/O

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DocumentTheme":
        return cls(
            name=str(data.get("name") or "default"),
            colors={
                **cls().colors,
                **{k: str(v) for k, v in (data.get("colors") or {}).items()},
            },
            fonts={
                **cls().fonts,
                **(data.get("fonts") or {}),
            },
            logo_path=data.get("logo_path"),
            footer_text=data.get("footer_text"),
            slide_master_path=data.get("slide_master_path"),
            layouts=list(data.get("layouts") or _DEFAULT_LAYOUTS),
        )

    @classmethod
    def from_json_file(cls, path: Path | str) -> "DocumentTheme":
        p = Path(path)
        with p.open(encoding="utf-8") as f:
            data = json.load(f)
        theme = cls.from_dict(data)
        # Resolve sibling assets relative to the theme.json location.
        base = p.parent
        if theme.logo_path:
            theme.logo_path = str((base / theme.logo_path).resolve()) \
                if not Path(theme.logo_path).is_absolute() else theme.logo_path
        if theme.slide_master_path:
            theme.slide_master_path = str((base / theme.slide_master_path).resolve()) \
                if not Path(theme.slide_master_path).is_absolute() \
                else theme.slide_master_path
        return theme

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_prompt_block(self) -> str:
        """Compact human-readable summary for embedding in the meta-prompt."""
        lines = [f"Theme: {self.name}"]
        lines.append("Colors:")
        for k in ("primary", "accent", "background", "muted", "text"):
            v = self.colors.get(k)
            if v:
                lines.append(f"  {k}: {v}")
        lines.append("Fonts:")
        for k in ("heading", "body", "code"):
            v = self.fonts.get(k)
            if v:
                lines.append(f"  {k}: {v}")
        for k in ("heading_size_pt", "body_size_pt"):
            v = self.fonts.get(k)
            if v is not None:
                lines.append(f"  {k}: {v}")
        if self.logo_path:
            lines.append(f"Logo path: {self.logo_path}")
        if self.footer_text:
            lines.append(f"Footer: {self.footer_text}")
        if self.slide_master_path:
            lines.append(f"Slide master: {self.slide_master_path}")
        if self.layouts:
            lines.append(f"Available layouts: {', '.join(self.layouts)}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Validation

    def validate(self) -> list[str]:
        """Return a list of human-readable validation errors (empty = OK)."""
        errors: list[str] = []
        if not self.name or not re.match(r"^[a-zA-Z0-9_-]+$", self.name):
            errors.append(
                "name must be a-z / 0-9 / _ / - only (used as a directory name)"
            )
        for k, v in self.colors.items():
            if not isinstance(v, str) or not _HEX_COLOR.match(v):
                errors.append(f"colors.{k}={v!r} is not a valid #RRGGBB hex")
        if self.logo_path and not Path(self.logo_path).is_file():
            errors.append(f"logo_path does not exist: {self.logo_path}")
        if self.slide_master_path and not Path(self.slide_master_path).is_file():
            errors.append(f"slide_master_path does not exist: {self.slide_master_path}")
        return errors


# ---------------------------------------------------------------------------
# Storage


class ThemeStore:
    """Manages the collection of themes under `.praxia/themes/`."""

    def __init__(self, base_dir: Path | str = ".praxia/themes") -> None:
        self.base_dir = Path(base_dir)

    # ------------------------------------------------------------------
    # Listing

    def list_names(self) -> list[str]:
        if not self.base_dir.is_dir():
            return []
        return sorted(
            p.name for p in self.base_dir.iterdir()
            if p.is_dir() and (p / "theme.json").is_file()
        )

    def load(self, name: str) -> DocumentTheme:
        path = self.base_dir / name / "theme.json"
        if not path.is_file():
            raise FileNotFoundError(
                f"theme {name!r} not found at {path}. Available: "
                f"{', '.join(self.list_names()) or '(none)'}"
            )
        return DocumentTheme.from_json_file(path)

    def has(self, name: str) -> bool:
        return (self.base_dir / name / "theme.json").is_file()

    # ------------------------------------------------------------------
    # Mutating

    def save(
        self,
        theme: DocumentTheme,
        *,
        logo_bytes: bytes | None = None,
        logo_filename: str | None = None,
        master_bytes: bytes | None = None,
    ) -> Path:
        """Persist `theme` under `<base>/<theme.name>/theme.json`.

        If `logo_bytes` is given, it's written to `logo.<ext>` and the
        theme's `logo_path` field is updated. Same for slide-master.
        """
        errors = theme.validate()
        if errors:
            raise ValueError("invalid theme: " + "; ".join(errors))

        dest = self.base_dir / theme.name
        dest.mkdir(parents=True, exist_ok=True)

        if logo_bytes is not None:
            ext = (
                Path(logo_filename or "logo.png").suffix.lower()
                or ".png"
            )
            logo_file = dest / f"logo{ext}"
            logo_file.write_bytes(logo_bytes)
            theme.logo_path = str(logo_file.resolve())
        if master_bytes is not None:
            master_file = dest / "master.pptx"
            master_file.write_bytes(master_bytes)
            theme.slide_master_path = str(master_file.resolve())

        # Re-validate now that paths point at real files.
        errors = theme.validate()
        if errors:
            raise ValueError("invalid theme after asset attach: " + "; ".join(errors))

        # Store paths relative to the theme dir so the bundle is portable.
        data = theme.to_dict()
        if data.get("logo_path"):
            data["logo_path"] = Path(data["logo_path"]).name
        if data.get("slide_master_path"):
            data["slide_master_path"] = Path(data["slide_master_path"]).name

        out_path = dest / "theme.json"
        out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return out_path

    def delete(self, name: str) -> bool:
        target = self.base_dir / name
        if not target.is_dir():
            return False
        shutil.rmtree(target)
        return True
