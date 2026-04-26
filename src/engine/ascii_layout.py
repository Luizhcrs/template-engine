"""ASCII-art layout extraction — POC for structure detection without multi-modal LLMs.

Hypothesis: a rendered document image (PNG) downsampled to a fixed-size character grid
preserves *layout* structure (headings, tables, sections, placeholders) while losing
fine-grained content. Heuristics over the resulting string detect features without OCR
or vision models.

Pipeline: ``.docx/.pdf`` -> render (LibreOffice) -> PNG -> ascii grid -> heuristics.

This module deliberately has no external deps beyond Pillow (already in ``[visual]``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path  # noqa: TC003 - runtime needed by image_to_ascii signature
from typing import Literal

import structlog

log = structlog.get_logger(__name__)


# Char ramp from dark (dense) to light (empty). Block-style preserves grid alignment.
_DEFAULT_RAMP = "█▓▒░ "

# Threshold tuning constants
_DEFAULT_COLS = 80
_DEFAULT_ROWS = 60
_DENSE_LINE_RATIO = 0.55  # row with >55% non-space chars = candidate heading/divider
_TABLE_MIN_RUN = 4  # consecutive rows of similar density = table band
_SECTION_BREAK_BLANK_ROWS = 2  # >=2 contiguous near-blank rows = section break


@dataclass(frozen=True)
class HeadingHint:
    row: int
    density: float
    width_ratio: float  # 0-1, how wide the text block extends
    text_preview: str  # raw ascii row for inspection


@dataclass(frozen=True)
class TableHint:
    start_row: int
    end_row: int
    column_count_estimate: int  # rough — based on aligned column edges


@dataclass(frozen=True)
class SectionBreak:
    row: int
    blank_run_length: int


@dataclass(frozen=True)
class PlaceholderHint:
    row: int
    pattern: str  # e.g. "____" or "[ DEFINIR ]"
    column_start: int


@dataclass(frozen=True)
class LayoutFeatures:
    """Output of layout heuristics over the ASCII grid."""

    rows: int
    cols: int
    headings: list[HeadingHint] = field(default_factory=list)
    tables: list[TableHint] = field(default_factory=list)
    section_breaks: list[SectionBreak] = field(default_factory=list)
    placeholders: list[PlaceholderHint] = field(default_factory=list)
    overall_density: float = 0.0  # 0-1


def image_to_ascii(
    png_path: Path,
    cols: int = _DEFAULT_COLS,
    rows: int = _DEFAULT_ROWS,
    ramp: str = _DEFAULT_RAMP,
    invert: bool = False,
) -> str:
    """Convert a PNG to an ASCII grid (rows lines x cols chars).

    Args:
        png_path: PNG file path.
        cols: target width in characters.
        rows: target height in characters (effectively 2x denser since chars are taller).
        ramp: chars from densest to lightest. Length must be >= 2.
        invert: if True, dark pixels map to light chars (useful for dark-bg images).

    Returns:
        ASCII grid as a single ``str``, lines joined by ``\\n``.
    """
    try:
        from PIL import Image
    except ImportError as e:  # pragma: no cover - optional dep
        raise ImportError("Pillow not installed. Install with: pip install 'template-engine[visual]'") from e

    if len(ramp) < 2:
        raise ValueError("ramp must have at least 2 chars")

    img = Image.open(png_path).convert("L")  # grayscale
    img = img.resize((cols, rows), Image.Resampling.LANCZOS)
    pixels = img.load()
    if pixels is None:
        raise RuntimeError(f"failed to load pixels from {png_path}")

    n = len(ramp) - 1
    lines: list[str] = []
    for y in range(rows):
        chars: list[str] = []
        for x in range(cols):
            raw = pixels[x, y]  # type: ignore[index]
            v = int(raw) if not isinstance(raw, tuple) else int(raw[0])
            if invert:
                v = 255 - v
            # density: 0=light/empty, 1=dark/dense; map via ramp
            idx = round((v / 255) * n)
            chars.append(ramp[idx])
        lines.append("".join(chars))
    return "\n".join(lines)


def _row_density(row: str, ramp: str = _DEFAULT_RAMP) -> float:
    """Fraction of chars in row that are 'dense' (the leftmost half of ramp)."""
    if not row:
        return 0.0
    dense_chars = set(ramp[: max(1, len(ramp) // 2)])
    return sum(1 for c in row if c in dense_chars) / len(row)


def _row_width_ratio(row: str, ramp: str = _DEFAULT_RAMP) -> float:
    """Fraction of row spanned by content (first non-light to last non-light char)."""
    if not row:
        return 0.0
    light = ramp[-1]
    stripped_idx = [i for i, c in enumerate(row) if c != light]
    if not stripped_idx:
        return 0.0
    return (stripped_idx[-1] - stripped_idx[0] + 1) / len(row)


def detect_layout_features(ascii_grid: str, ramp: str = _DEFAULT_RAMP) -> LayoutFeatures:
    """Run heuristics over an ASCII grid and return categorized hints.

    Heuristics:

    - **Heading**: dense row (>55%) followed by lighter row.
    - **Table**: >=4 consecutive rows with similar density (low variance) and aligned column edges.
    - **Section break**: >=2 contiguous near-blank rows.
    - **Placeholder**: long runs of identical underscore-like or bracket char (handled in output).
    """
    lines = ascii_grid.split("\n")
    if not lines:
        return LayoutFeatures(rows=0, cols=0)

    rows = len(lines)
    cols = max(len(line) for line in lines) if lines else 0
    densities = [_row_density(line, ramp) for line in lines]
    overall_density = sum(densities) / max(1, len(densities))

    headings: list[HeadingHint] = []
    section_breaks: list[SectionBreak] = []
    placeholders: list[PlaceholderHint] = []

    blank_run = 0
    blank_threshold = 0.05
    for i, (line, dens) in enumerate(zip(lines, densities, strict=False)):
        # heading: dense row followed by much lighter row
        if dens >= _DENSE_LINE_RATIO and i + 1 < rows:
            next_dens = densities[i + 1]
            if next_dens < dens * 0.6:
                headings.append(
                    HeadingHint(
                        row=i,
                        density=round(dens, 3),
                        width_ratio=round(_row_width_ratio(line, ramp), 3),
                        text_preview=line[:80],
                    )
                )

        # placeholder: long run of repeating char (3+) other than space/light
        for char in set(line):
            if char in (" ", ramp[-1]):
                continue
            run_len = 0
            run_start = -1
            for j, c in enumerate(line):
                if c == char:
                    if run_len == 0:
                        run_start = j
                    run_len += 1
                else:
                    if run_len >= 4:
                        placeholders.append(
                            PlaceholderHint(
                                row=i,
                                pattern=char * run_len,
                                column_start=run_start,
                            )
                        )
                    run_len = 0
            if run_len >= 4:
                placeholders.append(
                    PlaceholderHint(
                        row=i,
                        pattern=char * run_len,
                        column_start=run_start,
                    )
                )

        # section break: contiguous blank rows
        if dens <= blank_threshold:
            blank_run += 1
        else:
            if blank_run >= _SECTION_BREAK_BLANK_ROWS:
                section_breaks.append(SectionBreak(row=i - blank_run, blank_run_length=blank_run))
            blank_run = 0
    if blank_run >= _SECTION_BREAK_BLANK_ROWS:
        section_breaks.append(SectionBreak(row=rows - blank_run, blank_run_length=blank_run))

    tables_dense = _detect_tables(densities)
    tables_sparse = _detect_tables_via_columns(lines, ramp=ramp)
    tables = _merge_table_hints(tables_dense + tables_sparse)

    log.info(
        "ascii_layout.features",
        rows=rows,
        cols=cols,
        headings=len(headings),
        tables=len(tables),
        tables_dense=len(tables_dense),
        tables_sparse=len(tables_sparse),
        section_breaks=len(section_breaks),
        placeholders=len(placeholders),
        overall_density=round(overall_density, 3),
    )

    return LayoutFeatures(
        rows=rows,
        cols=cols,
        headings=headings,
        tables=tables,
        section_breaks=section_breaks,
        placeholders=_dedupe_placeholders(placeholders),
        overall_density=round(overall_density, 3),
    )


def _detect_tables(densities: list[float]) -> list[TableHint]:
    """Find runs of >=4 rows with similar density (low variance) — likely full table bands.

    Catches dense tables (filled cells). For sparse tables (borders only, empty cells),
    use ``_detect_tables_via_columns`` which scans vertical edges.
    """
    hints: list[TableHint] = []
    if len(densities) < _TABLE_MIN_RUN:
        return hints

    start = 0
    while start < len(densities) - _TABLE_MIN_RUN:
        if densities[start] < 0.1:  # skip blank
            start += 1
            continue
        end = start
        ref = densities[start]
        for j in range(start + 1, len(densities)):
            if abs(densities[j] - ref) <= 0.08:
                end = j
            else:
                break
        if end - start + 1 >= _TABLE_MIN_RUN:
            hints.append(
                TableHint(
                    start_row=start,
                    end_row=end,
                    column_count_estimate=0,
                )
            )
            start = end + 1
        else:
            start += 1
    return hints


def _detect_tables_via_columns(
    lines: list[str],
    ramp: str = _DEFAULT_RAMP,
    min_height: int = 5,
    min_columns: int = 2,
    edge_strictness: Literal["dense", "any-non-light"] = "any-non-light",
) -> list[TableHint]:
    """Detect sparse tables (border-only, empty cells) by scanning vertical edges.

    Algorithm:
    1. For each column index, count contiguous runs of "edge" chars (vertical lines).
    2. A column with a run >= min_height = candidate table edge.
    3. >= min_columns aligned candidates within proximity = table band.

    edge_strictness:
        - "dense": only chars in first half of ramp (matches solid lines).
        - "any-non-light": any char except space or last ramp char (matches thin/aliased borders).
        Default "any-non-light" is more permissive — works for resized images where 1px borders
        anti-alias to mid-tones.
    """
    if not lines:
        return []
    cols = max(len(line) for line in lines)
    if cols == 0:
        return []

    if edge_strictness == "dense":
        edge_chars = set(ramp[: max(1, len(ramp) // 2)])
    else:
        # Any non-light character = potential edge
        light_char = ramp[-1]
        edge_chars = set(ramp) - {light_char, " "}

    # For each column, find longest contiguous vertical run of edge chars
    col_runs: list[tuple[int, int, int]] = []
    for c in range(cols):
        run_start = -1
        run_len = 0
        best_run = (-1, -1, 0)
        for r, line in enumerate(lines):
            char = line[c] if c < len(line) else " "
            if char in edge_chars:
                if run_len == 0:
                    run_start = r
                run_len += 1
                if run_len > best_run[2]:
                    best_run = (run_start, r, run_len)
            else:
                run_len = 0
        if best_run[2] >= min_height:
            col_runs.append((c, best_run[0], best_run[1]))

    if len(col_runs) < min_columns:
        return []

    # Cluster column runs that overlap vertically (same band)
    col_runs.sort(key=lambda r: r[0])
    bands: list[list[tuple[int, int, int]]] = []
    for run in col_runs:
        c, start, end = run
        placed = False
        for band in bands:
            # overlap: max start <= min end
            band_start = max(b[1] for b in band)
            band_end = min(b[2] for b in band)
            if max(band_start, start) <= min(band_end, end):
                band.append(run)
                placed = True
                break
        if not placed:
            bands.append([run])

    # Bands with >= min_columns vertical edges = tables
    hints: list[TableHint] = []
    for band in bands:
        if len(band) < min_columns:
            continue
        start_row = max(b[1] for b in band)
        end_row = min(b[2] for b in band)
        if end_row - start_row + 1 < min_height:
            continue
        hints.append(
            TableHint(
                start_row=start_row,
                end_row=end_row,
                column_count_estimate=len(band),
            )
        )
    return hints


def _merge_table_hints(hints: list[TableHint]) -> list[TableHint]:
    """Merge overlapping/adjacent table hints from dense + sparse detectors.

    Two hints overlap if their row ranges intersect or touch. Result preserves
    the max column_count_estimate (sparse detector's output is preferred when present).
    """
    if not hints:
        return []
    sorted_hints = sorted(hints, key=lambda h: h.start_row)
    merged: list[TableHint] = [sorted_hints[0]]
    for h in sorted_hints[1:]:
        last = merged[-1]
        if h.start_row <= last.end_row + 1:
            merged[-1] = TableHint(
                start_row=last.start_row,
                end_row=max(last.end_row, h.end_row),
                column_count_estimate=max(last.column_count_estimate, h.column_count_estimate),
            )
        else:
            merged.append(h)
    return merged


def _dedupe_placeholders(placeholders: list[PlaceholderHint]) -> list[PlaceholderHint]:
    """Keep at most 1 placeholder per (row, pattern_char). Avoids reporting same run multiple times."""
    seen: set[tuple[int, str]] = set()
    out: list[PlaceholderHint] = []
    for ph in placeholders:
        key = (ph.row, ph.pattern[0] if ph.pattern else "")
        if key in seen:
            continue
        seen.add(key)
        out.append(ph)
    return out


# Provider-style summary: emit a compact text representation of the layout
# Useful for feeding to a text-only LLM as a cheaper alternative to vision

LayoutSummaryFormat = Literal["text", "json"]


def summarize_layout(features: LayoutFeatures, fmt: LayoutSummaryFormat = "text") -> str:
    """Produce a compact summary of detected layout features."""
    if fmt == "json":
        import json

        payload = {
            "rows": features.rows,
            "cols": features.cols,
            "overall_density": features.overall_density,
            "headings": [
                {"row": h.row, "density": h.density, "width_ratio": h.width_ratio} for h in features.headings
            ],
            "tables": [{"start_row": t.start_row, "end_row": t.end_row} for t in features.tables],
            "section_breaks": [
                {"row": s.row, "blank_rows": s.blank_run_length} for s in features.section_breaks
            ],
            "placeholders": [
                {"row": p.row, "pattern": p.pattern, "column_start": p.column_start}
                for p in features.placeholders
            ],
        }
        return json.dumps(payload, indent=2, ensure_ascii=False)

    parts: list[str] = []
    parts.append(f"Grid: {features.rows}x{features.cols}, density={features.overall_density:.2f}")
    parts.append(f"Headings detected: {len(features.headings)}")
    for h in features.headings[:10]:
        parts.append(f"  row={h.row:>3} density={h.density:.2f} width={h.width_ratio:.2f}")
    parts.append(f"Tables detected: {len(features.tables)}")
    for t in features.tables[:10]:
        parts.append(f"  rows {t.start_row}-{t.end_row}")
    parts.append(f"Section breaks: {len(features.section_breaks)}")
    for s in features.section_breaks[:10]:
        parts.append(f"  row={s.row} blank_rows={s.blank_run_length}")
    parts.append(f"Placeholders: {len(features.placeholders)}")
    for p in features.placeholders[:10]:
        parts.append(f"  row={p.row} col={p.column_start} pattern={p.pattern[:20]!r}")
    return "\n".join(parts)
