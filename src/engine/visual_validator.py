"""Visual validation — compare a rendered .docx against a gold doc using a multi-modal LLM.

Pipeline: ``.docx`` -> PDF (LibreOffice headless) -> PNG (pdf2image) -> base64 ->
multi-modal LLM with structured output schema.

Returns a ``VisualValidationResult`` with overall score + categorized issues
(alignment, spacing, typography, section_order, other).

Requires:

- LibreOffice installed and available as ``soffice`` on PATH
- ``template-engine[visual]`` extra (``pdf2image`` + ``pillow``)
- A multi-modal provider implementing ``VisualLLMProvider`` (e.g. ``GeminiVisionProvider``)
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import structlog

if TYPE_CHECKING:
    from engine.llm.base import VisualLLMProvider


log = structlog.get_logger(__name__)


IssueCategory = Literal["alignment", "spacing", "typography", "section_order", "other"]
IssueSeverity = Literal["low", "medium", "high"]

_VALID_CATEGORIES: frozenset[str] = frozenset(
    ["alignment", "spacing", "typography", "section_order", "other"]
)
_VALID_SEVERITIES: frozenset[str] = frozenset(["low", "medium", "high"])


@dataclass(frozen=True)
class VisualIssue:
    category: IssueCategory
    severity: IssueSeverity
    description: str


@dataclass(frozen=True)
class VisualValidationResult:
    """Outcome of a visual comparison.

    - ``score``: 0.0-1.0 overall similarity (higher = closer to gold)
    - ``issues``: discrete divergences flagged by the LLM
    - ``summary``: free-text 1-2 sentence overview from the LLM
    - ``gold_image``/``output_image``: rendered PNGs (kept for inspection/debug)
    - ``raw_response``: full JSON from the LLM (escape hatch)
    """

    score: float
    issues: list[VisualIssue]
    summary: str
    gold_image: Path
    output_image: Path
    raw_response: dict


_VALIDATION_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "score": {"type": "number", "minimum": 0, "maximum": 1},
        "summary": {"type": "string"},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["alignment", "spacing", "typography", "section_order", "other"],
                    },
                    "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                    "description": {"type": "string"},
                },
                "required": ["category", "severity", "description"],
            },
        },
    },
    "required": ["score", "summary", "issues"],
}


_PROMPT = """You are a document layout reviewer. Two images are shown:

1. **GOLD** — the reference template with the desired visual standard.
2. **OUTPUT** — a rendered document we want to validate against the gold.

Compare visually and return a JSON object describing how well OUTPUT matches GOLD.

Focus on:

- Heading levels, alignment, and indentation
- Spacing between sections and paragraphs
- Typography: font weights, sizes, italic/bold use
- Order and presence of sections, headers, footers
- Tables: row/column alignment, borders

Return:

- ``score`` 0.0-1.0 (1.0 = visually identical, 0.0 = unrelated)
- ``summary`` 1-2 sentences high-level diagnosis
- ``issues`` array (may be empty); each item has ``category`` (alignment | spacing |
  typography | section_order | other), ``severity`` (low | medium | high), and
  ``description`` (short, specific, actionable)

Be conservative: only flag concrete visual differences, not content differences.
"""


def _check_soffice() -> str:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise RuntimeError(
            "LibreOffice not found. Install it and ensure 'soffice' is on PATH. "
            "On Linux: apt install libreoffice. On macOS: brew install libreoffice. "
            "On Windows: download from libreoffice.org and add to PATH."
        )
    return soffice


def _docx_to_pdf(docx_path: Path, out_dir: Path) -> Path:
    """Convert a .docx to .pdf via LibreOffice headless. Returns the produced .pdf path."""
    soffice = _check_soffice()
    docx_path = docx_path.resolve()
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    log.info("visual.docx_to_pdf.start", source=str(docx_path), out_dir=str(out_dir))
    result = subprocess.run(
        [
            soffice,
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(out_dir),
            str(docx_path),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        log.error("visual.docx_to_pdf.failed", stderr=result.stderr[:500])
        raise RuntimeError(f"LibreOffice conversion failed: {result.stderr[:500]}")
    pdf_path = out_dir / (docx_path.stem + ".pdf")
    if not pdf_path.exists():
        raise RuntimeError(f"PDF not produced at expected path: {pdf_path}")
    log.info("visual.docx_to_pdf.ok", pdf=str(pdf_path))
    return pdf_path


def _pdf_to_png(pdf_path: Path, out_dir: Path, dpi: int = 150) -> Path:
    """Render the first page of a PDF to PNG. Returns the PNG path.

    For multi-page rendering, use ``_pdf_to_pngs``.
    """
    pages = _pdf_to_pngs(pdf_path, out_dir, dpi=dpi, first_page=1, last_page=1)
    return pages[0]


def _pdf_to_pngs(
    pdf_path: Path,
    out_dir: Path,
    dpi: int = 150,
    first_page: int = 1,
    last_page: int | None = None,
) -> list[Path]:
    """Render PDF pages to PNGs. Returns list of paths (one per page)."""
    try:
        from pdf2image import convert_from_path
    except ImportError as e:  # pragma: no cover - optional dep
        raise ImportError(
            "pdf2image not installed. Install with: pip install 'template-engine[visual]'"
        ) from e

    out_dir.mkdir(parents=True, exist_ok=True)
    # Build kwargs dynamically: pdf2image accepts None for last_page at runtime
    # ("until end"), but the type stub typing rejects None. Drop key when None.
    kwargs: dict[str, object] = {"dpi": dpi, "first_page": first_page}
    if last_page is not None:
        kwargs["last_page"] = last_page
    images = convert_from_path(str(pdf_path), **kwargs)  # type: ignore[arg-type]
    if not images:
        raise RuntimeError(f"pdf2image returned no pages for {pdf_path}")

    pages: list[Path] = []
    for idx, image in enumerate(images, start=first_page):
        suffix = "" if len(images) == 1 else f"-p{idx:03d}"
        png_path = out_dir / f"{pdf_path.stem}{suffix}.png"
        image.save(png_path, "PNG")
        pages.append(png_path)

    log.info(
        "visual.pdf_to_pngs.ok",
        pdf=str(pdf_path),
        pages_rendered=len(pages),
        first=first_page,
        last=first_page + len(pages) - 1,
    )
    return pages


def docx_to_png(docx_path: Path, out_dir: Path | None = None, dpi: int = 150) -> Path:
    """Render a ``.docx`` to a PNG image (first page only).

    For multi-page rendering, use ``docx_to_pngs``.
    """
    docx_path = Path(docx_path)
    if not docx_path.exists():
        raise FileNotFoundError(f"docx not found: {docx_path}")
    work_dir = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="te-visual-"))
    pdf = _docx_to_pdf(docx_path, work_dir)
    return _pdf_to_png(pdf, work_dir, dpi=dpi)


def docx_to_pngs(
    docx_path: Path,
    out_dir: Path | None = None,
    dpi: int = 150,
    pages: Literal["all"] | int | tuple[int, int] = "all",
) -> list[Path]:
    """Render a ``.docx`` to PNG images, one per page.

    Args:
        docx_path: source .docx file.
        out_dir: output directory (temp dir if None).
        dpi: rasterization DPI.
        pages: ``"all"`` (default), single int (1-indexed), or ``(first, last)`` tuple.

    Returns:
        List of PNG paths in document order.
    """
    docx_path = Path(docx_path)
    if not docx_path.exists():
        raise FileNotFoundError(f"docx not found: {docx_path}")

    # Validate pages spec BEFORE expensive LibreOffice call (fail fast)
    first_page: int
    last_page: int | None
    if pages == "all":
        first_page, last_page = 1, None
    elif isinstance(pages, int):
        first_page = last_page = pages
    elif isinstance(pages, tuple) and len(pages) == 2:
        first_page, last_page = pages
    else:
        raise ValueError(f"invalid pages spec: {pages!r}")

    work_dir = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="te-visual-"))
    pdf = _docx_to_pdf(docx_path, work_dir)
    return _pdf_to_pngs(pdf, work_dir, dpi=dpi, first_page=first_page, last_page=last_page)


async def validate_visual(
    *,
    gold_path: Path,
    output_path: Path,
    llm: VisualLLMProvider,
    dpi: int = 150,
    keep_images_dir: Path | None = None,
) -> VisualValidationResult:
    """Compare two ``.docx`` files visually using a multi-modal LLM.

    Args:
        gold_path: reference .docx (the standard).
        output_path: rendered .docx to validate.
        llm: provider implementing ``VisualLLMProvider``.
        dpi: rasterization DPI (default 150).
        keep_images_dir: if set, generated PNGs are kept here. Otherwise a temp dir is used.

    Returns:
        ``VisualValidationResult`` with score 0-1, structured issues, and the rendered images.

    Raises:
        FileNotFoundError: if any input doesn't exist.
        RuntimeError: if LibreOffice is missing or conversion fails.
        LLMError: on provider failure.
    """
    gold_path = Path(gold_path)
    output_path = Path(output_path)
    if not gold_path.exists():
        raise FileNotFoundError(f"gold_path not found: {gold_path}")
    if not output_path.exists():
        raise FileNotFoundError(f"output_path not found: {output_path}")

    log.info("visual.validate.start", gold=str(gold_path), output=str(output_path))

    # When keep_images_dir is set, caller owns cleanup. Otherwise we use a managed tempdir
    # that survives the function (paths are returned in the result for inspection).
    # Caller can clean up via shutil.rmtree(result.gold_image.parent.parent).
    work_dir = Path(keep_images_dir) if keep_images_dir else Path(tempfile.mkdtemp(prefix="te-visual-"))
    gold_dir = work_dir / "gold"
    output_dir = work_dir / "output"

    gold_png = docx_to_png(gold_path, out_dir=gold_dir, dpi=dpi)
    output_png = docx_to_png(output_path, out_dir=output_dir, dpi=dpi)

    raw = await llm.compare_images(_PROMPT, [gold_png, output_png], _VALIDATION_SCHEMA)

    issues = _parse_issues(raw.get("issues", []))
    score = _clamp_score(raw.get("score", 0.0))
    summary = str(raw.get("summary", ""))

    log.info(
        "visual.validate.ok",
        score=score,
        issues_count=len(issues),
        high_severity=sum(1 for i in issues if i.severity == "high"),
    )

    return VisualValidationResult(
        score=score,
        issues=issues,
        summary=summary,
        gold_image=gold_png,
        output_image=output_png,
        raw_response=raw,
    )


def _clamp_score(value: object) -> float:
    """Coerce LLM score to a clean 0.0-1.0 float. Out-of-range or non-numeric -> 0.0."""
    try:
        score = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        log.warning("visual.score.invalid", raw=repr(value))
        return 0.0
    return max(0.0, min(1.0, score))


def _parse_issues(items: object) -> list[VisualIssue]:
    """Parse raw issues array, validating enums. Out-of-range values are coerced to safe defaults."""
    if not isinstance(items, list):
        return []
    parsed: list[VisualIssue] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        cat_raw = str(item.get("category", "other"))
        sev_raw = str(item.get("severity", "low"))
        cat: IssueCategory = cat_raw if cat_raw in _VALID_CATEGORIES else "other"  # type: ignore[assignment]
        sev: IssueSeverity = sev_raw if sev_raw in _VALID_SEVERITIES else "low"  # type: ignore[assignment]
        if cat_raw != cat or sev_raw != sev:
            log.warning(
                "visual.issue.invalid_enum",
                raw_category=cat_raw,
                raw_severity=sev_raw,
                coerced_category=cat,
                coerced_severity=sev,
            )
        parsed.append(
            VisualIssue(
                category=cat,
                severity=sev,
                description=str(item.get("description", "")),
            )
        )
    return parsed
