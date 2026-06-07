"""PDF parser — uses pypdf for text extraction + pypdfium2 to
rasterize each page as a JPEG so the vision LLM can see charts /
figures embedded in the PDF (alpha20+).

Rasterization is gated on the optional `pypdfium2` import — if it's
not installed the parser still works, it just emits text only. That
keeps the lean install path working (text-only RAG over PDFs).
"""
from __future__ import annotations

import base64
import io
from typing import Any

from praxia.io.parsers.base import ParsedFile

# Rasterization controls. Calibrated so a 50-page PDF lands under
# ~10 MB of base64'd JPEGs in the parsed payload — enough to ride
# along in a single ChromaDB metadata blob without hitting size caps.
#
# - 100 DPI: good enough to OCR-by-eye charts + bar labels in most
#   business docs. Lower (72) loses small text; higher (144+) doubles
#   payload for marginal vision gain.
# - 1280 px max dimension: cap so a 22"x34" architectural sheet
#   doesn't produce a 8000px image that the LLM will downscale anyway.
# - JPEG quality 75: standard photo quality. Charts compress smaller
#   than this would suggest because they have flat color regions.
# - 25 pages max rasterized: cap so a 500-page doc doesn't blow
#   ~150 MB into one record. Pages after the cap get text only.
_PDF_RASTER_DPI = 100
_PDF_RASTER_MAX_PX = 1280
_PDF_RASTER_JPEG_QUALITY = 75
_PDF_MAX_PAGES_TO_RASTER = 25


def _rasterize_pdf(data: bytes) -> list[dict[str, Any]]:
    """Render each page as a JPEG; return list of
    `{page_num, mime, data (base64), bytes_size, width, height}`.
    Returns [] if pypdfium2 isn't available or rendering fails."""
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return []
    try:
        from PIL import Image
    except ImportError:
        return []

    pages_out: list[dict[str, Any]] = []
    try:
        pdf = pdfium.PdfDocument(io.BytesIO(data))
    except Exception:
        return []

    try:
        for i, page in enumerate(pdf, start=1):
            if i > _PDF_MAX_PAGES_TO_RASTER:
                break
            try:
                # scale = dpi / 72 (PDF native is 72 DPI)
                bitmap = page.render(scale=_PDF_RASTER_DPI / 72.0)
                pil = bitmap.to_pil()
            except Exception:
                continue

            # Downscale if either side exceeds the cap. thumbnail()
            # preserves aspect ratio and uses LANCZOS by default.
            if pil.width > _PDF_RASTER_MAX_PX or pil.height > _PDF_RASTER_MAX_PX:
                pil.thumbnail((_PDF_RASTER_MAX_PX, _PDF_RASTER_MAX_PX), Image.LANCZOS)

            # Force RGB — PDF renderer sometimes hands us RGBA which
            # JPEG can't encode.
            if pil.mode != "RGB":
                pil = pil.convert("RGB")

            buf = io.BytesIO()
            pil.save(buf, format="JPEG", quality=_PDF_RASTER_JPEG_QUALITY, optimize=True)
            jpeg_bytes = buf.getvalue()

            pages_out.append({
                "page_num": i,
                "mime": "image/jpeg",
                "data": base64.b64encode(jpeg_bytes).decode("ascii"),
                "bytes_size": len(jpeg_bytes),
                "width": pil.width,
                "height": pil.height,
            })
    finally:
        try:
            pdf.close()
        except Exception:
            pass

    return pages_out


class PdfParser:
    name = "pdf"

    def parse(self, data: bytes, *, filename: str, **kwargs: Any) -> ParsedFile:
        try:
            from pypdf import PdfReader
        except ImportError as e:
            raise ImportError(
                "PDF parsing requires `pypdf`. Install with:\n"
                '  pip install "praxia[office]"'
            ) from e

        reader = PdfReader(io.BytesIO(data))
        sections: list[tuple[str, str]] = []
        full_text: list[str] = []
        for i, page in enumerate(reader.pages, start=1):
            try:
                page_text = page.extract_text() or ""
            except Exception:
                page_text = ""
            sections.append((f"Page {i}", page_text))
            full_text.append(f"--- Page {i} ---\n{page_text}")

        # Rasterize pages for vision LLM input (alpha20+). The text we
        # just extracted is still the primary content; the page images
        # are extra evidence the commander can attach when retrieving.
        page_images = _rasterize_pdf(data)

        meta = reader.metadata
        return ParsedFile(
            filename=filename,
            content="\n\n".join(full_text),
            metadata={
                "page_count": len(reader.pages),
                "title": (str(meta.title) if meta and meta.title else None),
                "author": (str(meta.author) if meta and meta.author else None),
                "encrypted": reader.is_encrypted,
                "page_images": page_images,
                "page_image_count": len(page_images),
                "page_images_truncated": len(reader.pages) > _PDF_MAX_PAGES_TO_RASTER,
            },
            sections=sections,
        )
