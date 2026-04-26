"""Tests for engine.ascii_layout — POC for layout detection without LLM."""

from pathlib import Path

import pytest

from engine.ascii_layout import (
    HeadingHint,
    LayoutFeatures,
    PlaceholderHint,
    TableHint,
    _detect_tables,
    _row_density,
    _row_width_ratio,
    detect_layout_features,
    image_to_ascii,
    summarize_layout,
)


def _make_png(tmp_path: Path, name: str, width: int = 80, height: int = 60, pattern: str = "checker") -> Path:
    """Create a simple test PNG with a known pattern."""
    pytest.importorskip("PIL")
    from PIL import Image

    img = Image.new("L", (width, height), color=255)  # white bg
    pixels = img.load()
    if pattern == "heading_then_blank":
        # Top 3 rows dense black, rest white
        for y in range(3):
            for x in range(width):
                pixels[x, y] = 0
    elif pattern == "table":
        # Rows 10-30 are uniform-density grid
        for y in range(10, 30):
            for x in range(width):
                if x % 8 < 4:
                    pixels[x, y] = 50  # darker
    elif pattern == "section_break":
        # Top 5 rows black, then 10 blank, then bottom 5 black
        for y in list(range(5)) + list(range(15, 20)):
            for x in range(width):
                pixels[x, y] = 0
    elif pattern == "underline":
        # Row 5: long underscore-like dark line on right half
        for x in range(width // 2, width):
            pixels[x, 5] = 0
    path = tmp_path / name
    img.save(path, "PNG")
    return path


def test_image_to_ascii_returns_grid_with_correct_dimensions(tmp_path):
    png = _make_png(tmp_path, "blank.png", width=40, height=20)
    grid = image_to_ascii(png, cols=40, rows=20)
    lines = grid.split("\n")
    assert len(lines) == 20
    assert all(len(line) == 40 for line in lines)


def test_image_to_ascii_blank_image_is_all_light(tmp_path):
    png = _make_png(tmp_path, "blank.png", width=20, height=10)
    grid = image_to_ascii(png, cols=20, rows=10)
    # default ramp's last char is space (lightest)
    last_char = " "
    assert all(c == last_char for line in grid.split("\n") for c in line)


def test_image_to_ascii_full_black_is_all_dense(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image

    img = Image.new("L", (20, 10), color=0)
    png = tmp_path / "black.png"
    img.save(png, "PNG")
    grid = image_to_ascii(png, cols=20, rows=10)
    # default ramp's first char is the densest (█)
    first_char = "█"
    assert all(c == first_char for line in grid.split("\n") for c in line)


def test_image_to_ascii_invert_flag(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image

    img = Image.new("L", (10, 5), color=0)
    png = tmp_path / "black.png"
    img.save(png, "PNG")
    grid = image_to_ascii(png, cols=10, rows=5, invert=True)
    # inverted: black input becomes light output
    assert all(c == " " for line in grid.split("\n") for c in line)


def test_image_to_ascii_rejects_short_ramp(tmp_path):
    png = _make_png(tmp_path, "x.png")
    with pytest.raises(ValueError, match="at least 2 chars"):
        image_to_ascii(png, ramp="X")


# ===== row helpers =====


def test_row_density_default_ramp():
    # With default ramp "█▓▒░ ", dense chars are "█▓" (first half)
    assert _row_density("██████") == 1.0
    assert _row_density("      ") == 0.0
    assert _row_density("███░░░") == 0.5


def test_row_width_ratio():
    # Light char is " " (last in ramp)
    assert _row_width_ratio("        ") == 0.0
    assert _row_width_ratio("█       ") == 1 / 8
    assert _row_width_ratio("  ███   ") == 3 / 8
    assert _row_width_ratio("████████") == 1.0


# ===== detect_layout_features =====


def test_detect_features_finds_heading(tmp_path):
    png = _make_png(tmp_path, "heading.png", pattern="heading_then_blank")
    grid = image_to_ascii(png, cols=80, rows=60)
    features = detect_layout_features(grid)
    assert len(features.headings) >= 1
    assert features.headings[0].row <= 5  # heading near top


def test_detect_features_finds_section_break(tmp_path):
    png = _make_png(tmp_path, "break.png", pattern="section_break", height=40)
    grid = image_to_ascii(png, cols=80, rows=40)
    features = detect_layout_features(grid)
    assert len(features.section_breaks) >= 1


def test_detect_features_blank_image_no_features(tmp_path):
    png = _make_png(tmp_path, "blank.png")
    grid = image_to_ascii(png)
    features = detect_layout_features(grid)
    assert features.headings == []
    assert features.tables == []
    assert features.placeholders == []
    assert features.overall_density == 0.0


def test_detect_features_finds_placeholder():
    """ASCII grid synthesized directly to ensure placeholder run is detected."""
    grid = "\n".join(
        [
            "    ████████        ",  # row 0: long run of █ (placeholder)
            "                    ",
            "                    ",
        ]
    )
    features = detect_layout_features(grid)
    assert len(features.placeholders) >= 1
    assert features.placeholders[0].row == 0
    assert features.placeholders[0].pattern.startswith("█")


def test_detect_tables_finds_uniform_density_band():
    # 10 rows of similar density (0.5)
    densities = [0.0, 0.0, 0.5, 0.51, 0.49, 0.5, 0.5, 0.52, 0.48, 0.5, 0.0, 0.0]
    hints = _detect_tables(densities)
    assert len(hints) >= 1
    assert hints[0].start_row == 2
    assert hints[0].end_row >= 7


# ===== summarize_layout =====


def test_summarize_layout_text_format():
    features = LayoutFeatures(
        rows=60,
        cols=80,
        headings=[HeadingHint(row=1, density=0.7, width_ratio=0.9, text_preview="x")],
        tables=[TableHint(start_row=10, end_row=25, column_count_estimate=0)],
        section_breaks=[],
        placeholders=[PlaceholderHint(row=5, pattern="████", column_start=10)],
        overall_density=0.4,
    )
    out = summarize_layout(features)
    assert "60x80" in out
    assert "Headings detected: 1" in out
    assert "Tables detected: 1" in out
    assert "Placeholders: 1" in out


def test_summarize_layout_json_format():
    features = LayoutFeatures(rows=10, cols=20, overall_density=0.1)
    out = summarize_layout(features, fmt="json")
    import json

    parsed = json.loads(out)
    assert parsed["rows"] == 10
    assert parsed["cols"] == 20
    assert parsed["headings"] == []
