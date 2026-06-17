"""PPTX → per-slide PNG rendering for the vision-LLM review loop.

Renders each slide of a .pptx as a separate PNG image so a vision
LLM can critique typography, palette, layout, density, and
hierarchy slide by slide.

Pipeline:
    .pptx  ──[LibreOffice headless]──▶ .pdf  ──[pypdfium2]──▶ slide-NN.png

LibreOffice is required (no pure-Python alternative produces
faithful PowerPoint rendering). pypdfium2 is required for the
PDF→PNG step — it's a small Python wheel wrapping Google's
PDFium and has no system dependencies of its own.

Both pieces are optional installs. If either is missing, the
caller gets a :class:`RuntimeError` with explicit install
instructions, which the surrounding ``render_document`` tool
turns into a graceful "review skipped" tool result.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

_log = logging.getLogger(__name__)


# Standard install paths to probe when `soffice` isn't on PATH.
# Windows installers don't add LibreOffice to PATH by default, so
# checking the canonical install dirs catches the typical user.
_WIN_SOFFICE_PATHS = (
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
)
_MAC_SOFFICE_PATH = "/Applications/LibreOffice.app/Contents/MacOS/soffice"


def find_soffice() -> str | None:
    """Locate LibreOffice's soffice binary.

    Returns the absolute path if found, otherwise ``None``. Tries
    ``soffice``, ``libreoffice``, then platform-specific install
    locations.
    """
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    for candidate in _WIN_SOFFICE_PATHS:
        if Path(candidate).exists():
            return candidate
    if Path(_MAC_SOFFICE_PATH).exists():
        return _MAC_SOFFICE_PATH
    return None


def check_dependencies() -> tuple[bool, str]:
    """Return (ok, reason). Used by callers that want to surface a
    user-friendly "review skipped because X is missing" message
    without trying the actual conversion."""
    if not find_soffice():
        return False, (
            "LibreOffice (soffice binary) not found. Install from "
            "https://www.libreoffice.org/ — required for PPTX → PDF "
            "step of the vision review."
        )
    try:
        import pypdfium2  # noqa: F401
    except ImportError:
        return False, (
            "pypdfium2 is not installed. Run `pip install pypdfium2` — "
            "required for the PDF → PNG step of the vision review."
        )
    return True, ""


def render_pptx_to_pngs(
    pptx_path: Path,
    out_dir: Path | None = None,
    *,
    dpi: int = 100,
    timeout: int = 120,
) -> list[Path]:
    """Render each slide of ``pptx_path`` as a PNG.

    Args:
        pptx_path: source .pptx
        out_dir: where to write the PNGs. Created if missing.
            Default: a fresh temp directory the caller is
            responsible for cleaning up.
        dpi: rasterisation DPI for the PDF → PNG step. 100 is a
            good balance — high enough for a vision LLM to read
            14-point body text, low enough that one slide fits in
            a single LLM image attachment.
        timeout: per-step subprocess timeout in seconds.

    Returns the PNG paths in slide order. Raises
    :class:`RuntimeError` if either LibreOffice or pypdfium2 is
    missing, with install instructions in the message.
    """
    soffice = find_soffice()
    if not soffice:
        raise RuntimeError(
            "LibreOffice (soffice) is required for PPTX rendering. "
            "Install from https://www.libreoffice.org/."
        )
    try:
        import pypdfium2  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "pypdfium2 is required for PPTX → PNG rendering. "
            "Install with: pip install pypdfium2"
        ) from e

    out_dir = out_dir or Path(tempfile.mkdtemp(prefix="praxia-review-"))
    out_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: PPTX → PDF (LibreOffice headless).
    with tempfile.TemporaryDirectory(prefix="praxia-soffice-") as tmp:
        tmp_dir = Path(tmp)
        try:
            subprocess.run(
                [
                    soffice,
                    "--headless",
                    "--convert-to", "pdf",
                    "--outdir", str(tmp_dir),
                    str(pptx_path),
                ],
                check=True,
                capture_output=True,
                timeout=timeout,
            )
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or b"").decode(errors="ignore")[:500]
            raise RuntimeError(
                f"LibreOffice failed to convert {pptx_path.name} to PDF: "
                f"{stderr or '<no stderr>'}"
            ) from e
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(
                f"LibreOffice timed out after {timeout}s converting "
                f"{pptx_path.name}"
            ) from e

        pdf_path = tmp_dir / f"{pptx_path.stem}.pdf"
        if not pdf_path.exists():
            raise RuntimeError(
                f"LibreOffice did not produce a PDF for {pptx_path.name}. "
                f"Check that the file is a valid .pptx."
            )

        # Step 2: PDF → PNG per page (pypdfium2).
        pdf = pypdfium2.PdfDocument(str(pdf_path))
        try:
            scale = dpi / 72.0
            png_paths: list[Path] = []
            for i, page in enumerate(pdf):
                bitmap = page.render(scale=scale)
                pil_image = bitmap.to_pil()
                png_path = out_dir / f"slide-{i + 1:02d}.png"
                pil_image.save(png_path, format="PNG", optimize=True)
                png_paths.append(png_path)
        finally:
            pdf.close()
    return png_paths
