"""Style constants for Praxia-generated decks.

A small, opinionated palette + type scale that the LLM doesn't have to
re-invent on every export. Applied uniformly across cover, section,
KPI, chart, and bullets templates so the resulting deck reads as one
designed artifact rather than a stack of default-Office slides.

Rationale:
    - Decks generated from a markdown blob default to Calibri 18 pt
      on a white background. That looks like the LLM gave up halfway.
    - Hand-built decks (see the Q3-revenue-review reference deck in
      `tmp/build_q3_sales_review.py`) used indigo+amber with serif-
      free Yu Gothic / Segoe UI and read as polished.
    - Capturing that as a Python module lets every template in
      `slide_templates` and the markdown exporter pull from one
      source of truth.

Override knob:
    Construct a :class:`SlideStyle` with field overrides if a caller
    wants a different palette per deck. The default constants below
    are what `PptxExporter` uses when no style is supplied.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# RGB triplets — python-pptx wants RGBColor(r, g, b).
INDIGO = (31, 58, 138)     # Praxia primary
INDIGO_DARK = (23, 37, 84)
AMBER = (245, 158, 11)     # Praxia accent
AMBER_DARK = (180, 83, 9)

GRAY_900 = (17, 24, 39)    # body text
GRAY_700 = (55, 65, 81)    # secondary body
GRAY_500 = (107, 114, 128)  # captions / labels
GRAY_300 = (209, 213, 219)  # rules / dividers
GRAY_100 = (243, 244, 246)  # cards / panel backgrounds
WHITE = (255, 255, 255)


# Font families. Falls back to safe defaults if the named family
# is missing on the host. We use system-standard fonts so the
# resulting deck looks correct without requiring a font install:
#   - Yu Gothic / Yu Gothic UI ship with Windows 10+ and macOS
#   - Segoe UI ships with Windows; falls back to "Inter" on others
JA_FONT = "Yu Gothic"
JA_FONT_BOLD = "Yu Gothic UI Semibold"
EN_FONT = "Segoe UI"
EN_FONT_BOLD = "Segoe UI Semibold"


def font_for(text: str) -> tuple[str, str]:
    """Pick (regular, bold) font names based on the text's script.

    Detection heuristic: any CJK character → JA font set. Everything
    else uses the EN font set. We don't try to disambiguate JA / ZH /
    KO further because Yu Gothic covers all three reasonably and the
    user's locale picker on the desktop side handles it more
    precisely if they care.
    """
    if not text:
        return EN_FONT, EN_FONT_BOLD
    for ch in text:
        if "぀" <= ch <= "鿿" or "　" <= ch <= "〿":
            return JA_FONT, JA_FONT_BOLD
        if "＀" <= ch <= "￯":  # halfwidth/fullwidth forms
            return JA_FONT, JA_FONT_BOLD
    return EN_FONT, EN_FONT_BOLD


@dataclass
class SlideStyle:
    """Palette + typography knobs. Defaults match Praxia brand.

    Pass a custom instance to :class:`PptxExporter` or any helper in
    :mod:`praxia.io.slide_templates` to override the deck-wide look
    without forking the helpers themselves.
    """

    # Palette
    primary: tuple[int, int, int] = INDIGO
    primary_dark: tuple[int, int, int] = INDIGO_DARK
    accent: tuple[int, int, int] = AMBER
    accent_dark: tuple[int, int, int] = AMBER_DARK
    text: tuple[int, int, int] = GRAY_900
    text_muted: tuple[int, int, int] = GRAY_500
    panel_bg: tuple[int, int, int] = GRAY_100
    background: tuple[int, int, int] = WHITE

    # Typography (in points)
    title_pt: int = 36          # slide titles
    cover_title_pt: int = 56    # cover slide H1
    section_pt: int = 44        # section divider
    body_pt: int = 18           # bullets / paragraphs
    kpi_value_pt: int = 40      # KPI big number
    kpi_label_pt: int = 14      # KPI caption
    caption_pt: int = 12        # footnotes / page numbers

    # Layout (inches; python-pptx's Inches() unit)
    margin_left: float = 0.6
    margin_top: float = 0.5
    margin_right: float = 0.6
    margin_bottom: float = 0.5
    body_line_spacing: float = 1.25

    # Chart palette — series 0/1/2/3 cycle through these.
    # Picked so neighbouring bars/lines read as distinct categories
    # but stay inside the Praxia palette.
    chart_series: list[tuple[int, int, int]] = field(default_factory=lambda: [
        INDIGO,
        AMBER,
        (96, 165, 250),    # blue 400 — secondary
        (16, 185, 129),    # green 500 — positive accent
        (239, 68, 68),     # red 500 — negative accent
    ])


# The constant used when callers don't pass their own SlideStyle.
DEFAULT_STYLE = SlideStyle()


def style_summary_for_prompt(style: SlideStyle = DEFAULT_STYLE) -> str:
    """Return a short text block describing the style — used inside
    the agent's system prompt so the LLM's drafted content matches
    the visual rendering.

    Output is plain text (no markdown) since it goes into a system
    message and is rendered as-is.
    """
    return (
        "Deck style preset (applied automatically — write your draft so "
        "it reads well in this visual frame):\n"
        f"  Palette: indigo #{style.primary[0]:02x}{style.primary[1]:02x}{style.primary[2]:02x} "
        f"primary, amber #{style.accent[0]:02x}{style.accent[1]:02x}{style.accent[2]:02x} accent\n"
        f"  Fonts: Yu Gothic for Japanese, Segoe UI for English (auto-picked)\n"
        f"  Type scale: cover {style.cover_title_pt}pt, section {style.section_pt}pt, "
        f"slide title {style.title_pt}pt, body {style.body_pt}pt\n"
        "  Layout: one idea per slide, headlines as full sentences "
        "(not nouns), at most 5 bullets per slide.\n"
        "  Prefer KPI numbers + a chart over bullet lists of figures. "
        "Section dividers between major topics. Cover slide first."
    )
