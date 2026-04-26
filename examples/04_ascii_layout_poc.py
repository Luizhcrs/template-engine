"""04 — POC: layout detection without LLM via ASCII-art rendering.

Hypothesis: rendering a .docx -> PNG -> ASCII grid preserves enough layout
structure (headings, tables, sections, placeholders) for heuristics to detect
features without OCR or vision-LLM.

Run:
    python examples/04_ascii_layout_poc.py

Requires LibreOffice on PATH (for .docx -> PNG via visual_validator).
"""

from __future__ import annotations

import sys
from pathlib import Path

from engine.ascii_layout import detect_layout_features, image_to_ascii, summarize_layout
from engine.visual_validator import docx_to_png


def main() -> None:
    fixtures = Path(__file__).parent.parent / "tests" / "fixtures"
    targets = [
        fixtures / "template_sample.docx",
        fixtures / "gold_sample_01.docx",
        fixtures / "gold_sample_02.docx",
        fixtures / "fonte_sample.docx",
    ]
    targets = [p for p in targets if p.exists()]

    if not targets:
        print("ERROR: no fixtures found", file=sys.stderr)
        sys.exit(1)

    for docx_path in targets:
        print("=" * 80)
        print(f"DOC: {docx_path.name}")
        print("=" * 80)

        try:
            png = docx_to_png(docx_path)
        except RuntimeError as e:
            print(f"  [skip] {e}")
            continue

        # generate ASCII grid
        grid = image_to_ascii(png, cols=80, rows=60)

        # show grid (truncated)
        print("\n--- ASCII grid (first 30 rows) ---")
        for line in grid.split("\n")[:30]:
            print(line)

        # detect features
        features = detect_layout_features(grid)
        print("\n--- detected features ---")
        print(summarize_layout(features))
        print()


if __name__ == "__main__":
    main()
