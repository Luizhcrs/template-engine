"""Render a ``.docx`` to per-page PNG images for multimodal LLM input.

Pipeline: ``.docx`` → ``.pdf`` (via ``docx2pdf``, which drives Word COM
on Windows or Pages on macOS) → per-page PNG (via PyMuPDF / ``fitz``).

Used by :mod:`engine.section_mapper.auto_mapper` to attach visual
layout to the LLM prompt — the model can SEE merged cells, table
geometry, embedded logos, etc, instead of inferring everything from a
flat structural JSON.

Both deps are optional. If either is missing, ``render_pages`` returns
``[]`` and the LLM call falls back to text-only mode.
"""

from __future__ import annotations

import base64
import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PageImage:
    """One rendered page of a docx, encoded as PNG bytes + base64 URL."""

    page_index: int  # 0-based
    width: int
    height: int
    png_bytes: bytes

    def as_data_url(self) -> str:
        b64 = base64.b64encode(self.png_bytes).decode("ascii")
        return f"data:image/png;base64,{b64}"


def _have_renderers() -> tuple[bool, bool]:
    try:
        import docx2pdf  # type: ignore[import-not-found,import-untyped]  # noqa: F401

        have_docx2pdf = True
    except ImportError:
        have_docx2pdf = False
    try:
        import fitz  # type: ignore[import-not-found,import-untyped]  # noqa: F401

        have_fitz = True
    except ImportError:
        have_fitz = False
    return have_docx2pdf, have_fitz


def render_pages(
    docx_path: Path,
    *,
    dpi: int = 150,
    max_pages: int | None = None,
) -> list[PageImage]:
    """Render *docx_path* to a list of :class:`PageImage`.

    Returns an empty list when either renderer dependency is missing or
    rendering fails. ``max_pages`` caps the number of pages returned
    (useful when the doc is long and we only need the first few for
    layout context).
    """
    have_docx2pdf, have_fitz = _have_renderers()
    if not (have_docx2pdf and have_fitz):
        log.info(
            "section_mapper.template_renderer.skipped",
            extra={"have_docx2pdf": have_docx2pdf, "have_fitz": have_fitz},
        )
        return []

    import fitz  # type: ignore[import-not-found,import-untyped]
    from docx2pdf import convert  # type: ignore[import-not-found,import-untyped]

    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = Path(tmpdir) / "out.pdf"
        try:
            convert(str(docx_path), str(pdf_path))
        except Exception as exc:
            log.warning(
                "section_mapper.template_renderer.docx2pdf_failed",
                extra={"error": str(exc), "docx": str(docx_path)},
            )
            return []

        if not pdf_path.exists():
            return []

        out: list[PageImage] = []
        try:
            doc = fitz.open(str(pdf_path))
        except Exception as exc:
            log.warning(
                "section_mapper.template_renderer.pdf_open_failed",
                extra={"error": str(exc), "pdf": str(pdf_path)},
            )
            return []

        try:
            for i, page in enumerate(doc):
                if max_pages is not None and i >= max_pages:
                    break
                pix = page.get_pixmap(dpi=dpi)
                out.append(
                    PageImage(
                        page_index=i,
                        width=pix.width,
                        height=pix.height,
                        png_bytes=pix.tobytes("png"),
                    )
                )
        finally:
            doc.close()

        return out


__all__ = [
    "PageImage",
    "render_pages",
]
