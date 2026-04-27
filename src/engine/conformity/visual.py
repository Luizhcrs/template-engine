"""Visual dimension — text-rendered ascii_layout fingerprint compare (Wave F).

Strategy: avoid LibreOffice. Take the extracted text of each docx, render it
into a synthetic PNG via PIL (monospace font, fixed canvas), feed both into the
existing :mod:`engine.ascii_layout` pipeline, and compare the resulting
:class:`~engine.ascii_layout.LayoutFeatures`.

This is **structural-visual** not pixel-perfect — it captures heading positions,
table-like density bands, and overall page density, which is exactly what the
template-conformity question asks ("does the layout match?"). Pixel-perfect
design fidelity belongs to the ``design`` dimension (multimodal LLM).

Skipped gracefully when Pillow is not installed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import structlog

from engine.conformity.report import DimensionResult, Failure
from engine.extractor import extract

if TYPE_CHECKING:
    from pathlib import Path

log = structlog.get_logger(__name__)

_DEFAULT_CANVAS: Final[tuple[int, int]] = (800, 1100)
_DEFAULT_GRID: Final[tuple[int, int]] = (80, 60)


def _pillow_available() -> bool:
    try:
        import PIL  # noqa: F401

        return True
    except ImportError:
        return False


def _render_text_png(text: str, output_path: Path, size: tuple[int, int] = _DEFAULT_CANVAS) -> Path:
    """Render plain text as a PNG using PIL with a monospace font."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", size, color="white")
    draw = ImageDraw.Draw(img)

    font: ImageFont.FreeTypeFont | ImageFont.ImageFont
    try:
        font = ImageFont.truetype("consola.ttf", 14)
    except OSError:
        try:
            font = ImageFont.truetype("DejaVuSansMono.ttf", 14)
        except OSError:
            font = ImageFont.load_default()

    margin = 30
    line_h = 18
    y = margin
    max_chars = max(20, (size[0] - 2 * margin) // 8)

    for raw_line in text.splitlines():
        if y + line_h > size[1] - margin:
            break
        line = raw_line[:max_chars]
        draw.text((margin, y), line, fill="black", font=font)
        y += line_h

    img.save(output_path, "PNG")
    return output_path


def _features_from_text(text: str, tmp_dir: Path, name: str):  # type: ignore[no-untyped-def]
    from engine.ascii_layout import detect_layout_features, image_to_ascii

    png = tmp_dir / f"{name}.png"
    _render_text_png(text, png)
    grid = image_to_ascii(png, cols=_DEFAULT_GRID[0], rows=_DEFAULT_GRID[1])
    return detect_layout_features(grid)


def check_visual(
    template_path: Path,
    candidate_path: Path,
    *,
    max_acceptable_failures: float = 4.0,
) -> DimensionResult:
    """Run the visual dimension. Skipped when Pillow is unavailable."""
    if not _pillow_available():
        return DimensionResult(
            dimension="visual",
            score=1.0,
            skipped=True,
            skip_reason="Pillow not installed (pip install 'template-engine-ia[poc]')",
        )

    import tempfile

    template_text = extract(template_path).text
    candidate_text = extract(candidate_path).text

    with tempfile.TemporaryDirectory(prefix="conformity-visual-") as td:
        from pathlib import Path as _P

        tmp = _P(td)
        t_feats = _features_from_text(template_text, tmp, "template")
        c_feats = _features_from_text(candidate_text, tmp, "candidate")

    failures: list[Failure] = []

    # Density
    density_diff = abs(t_feats.overall_density - c_feats.overall_density)
    if density_diff > 0.10:
        failures.append(
            Failure(
                dimension="visual",
                field_or_excerpt="overall_density",
                expected=f"{t_feats.overall_density:.3f}",
                actual=f"{c_feats.overall_density:.3f}",
                severity="warning" if density_diff < 0.20 else "critical",
                note=f"density delta {density_diff:.3f}",
            )
        )

    # Heading count
    if abs(len(t_feats.headings) - len(c_feats.headings)) > 1:
        failures.append(
            Failure(
                dimension="visual",
                field_or_excerpt="headings_count",
                expected=str(len(t_feats.headings)),
                actual=str(len(c_feats.headings)),
                severity="warning",
                note="heading count mismatch",
            )
        )

    # Tables count
    if abs(len(t_feats.tables) - len(c_feats.tables)) > 1:
        failures.append(
            Failure(
                dimension="visual",
                field_or_excerpt="tables_count",
                expected=str(len(t_feats.tables)),
                actual=str(len(c_feats.tables)),
                severity="warning",
                note="table-like region count mismatch",
            )
        )

    # Placeholder regions (might catch unfilled blanks)
    if len(c_feats.placeholders) > len(t_feats.placeholders) + 2:
        failures.append(
            Failure(
                dimension="visual",
                field_or_excerpt="placeholders_count",
                expected=str(len(t_feats.placeholders)),
                actual=str(len(c_feats.placeholders)),
                severity="critical",
                note="candidate has more placeholder-like regions than template",
            )
        )

    weight = sum(1.0 if f.severity == "critical" else 0.4 for f in failures)
    raw = 1.0 - (weight / max_acceptable_failures)
    score = max(0.0, min(1.0, raw))

    log.info("conformity.visual", score=score, failures=len(failures))
    return DimensionResult(dimension="visual", score=score, failures=failures)
