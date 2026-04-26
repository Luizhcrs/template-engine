"""06 — POC multi-page: gera 3 PNGs sintéticos diferentes (página 1/2/3) e roda
detect_layout_features_multipage. Sem LibreOffice.

Página 1: heading + parágrafos + tabela
Página 2: só parágrafos (texto corrido)
Página 3: heading + tabela + placeholders (assinaturas)

Run:
    python examples/06_multipage_poc.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from engine.ascii_layout import (
    detect_layout_features_multipage,
    image_to_ascii,
    summarize_multipage,
)


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def make_page1(path: Path, width: int = 800, height: int = 1100) -> None:
    img = Image.new("RGB", (width, height), color="white")
    d = ImageDraw.Draw(img)
    f_h = _font(36)
    f_b = _font(16)

    d.rectangle((40, 40, 760, 90), fill="black")
    d.text((50, 48), "PAGE 1 - INTRO", fill="white", font=f_h)

    y = 130
    d.text((40, y), "1. OBJETIVO", fill="black", font=f_b)
    d.line((40, y + 22, 200, y + 22), fill="black", width=2)
    y += 40
    for line in [
        "Documento gerado para validar pipeline multi-pagina.",
        "Cobre tres tipos de layout em paginas distintas.",
    ]:
        d.text((40, y), line, fill="black", font=f_b)
        y += 22

    # tabela 3x3
    y += 50
    table_top = y
    table_bottom = y + 90
    col_x = [40, 280, 520, 760]
    for x in col_x:
        d.line((x, table_top, x, table_bottom), fill="black", width=1)
    for r in range(4):
        yy = table_top + r * 30
        d.line((40, yy, 760, yy), fill="black", width=1)

    img.save(path, "PNG")


def make_page2(path: Path, width: int = 800, height: int = 1100) -> None:
    img = Image.new("RGB", (width, height), color="white")
    d = ImageDraw.Draw(img)
    f_h = _font(36)
    f_b = _font(16)

    d.rectangle((40, 40, 760, 90), fill="black")
    d.text((50, 48), "PAGE 2 - BODY", fill="white", font=f_h)

    y = 130
    for _ in range(20):
        d.text(
            (40, y),
            "Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod.",
            fill="black",
            font=f_b,
        )
        y += 22

    img.save(path, "PNG")


def make_page3(path: Path, width: int = 800, height: int = 1100) -> None:
    img = Image.new("RGB", (width, height), color="white")
    d = ImageDraw.Draw(img)
    f_h = _font(36)
    f_b = _font(16)

    d.rectangle((40, 40, 760, 90), fill="black")
    d.text((50, 48), "PAGE 3 - SIGN", fill="white", font=f_h)

    y = 200
    d.text((40, y), "Assinaturas:", fill="black", font=f_b)
    y += 60
    for label in ["Responsavel:", "Aprovador:", "Data:"]:
        d.text((40, y), label, fill="black", font=f_b)
        d.line((180, y + 18, 600, y + 18), fill="black", width=2)
        y += 60

    img.save(path, "PNG")


def main() -> None:
    out_dir = Path(tempfile.mkdtemp(prefix="te-multipage-"))
    pages = [out_dir / f"page{i}.png" for i in (1, 2, 3)]
    make_page1(pages[0])
    make_page2(pages[1])
    make_page3(pages[2])

    print(f"PNGs sinteticos em: {out_dir}\n")

    ascii_ramp = "@#%*+=-:. "
    grids = [image_to_ascii(p, cols=80, rows=60, ramp=ascii_ramp) for p in pages]

    multi = detect_layout_features_multipage(grids, ramp=ascii_ramp)

    print("=" * 80)
    print("MULTI-PAGE LAYOUT FEATURES:")
    print("=" * 80)
    print(summarize_multipage(multi))
    print()

    print("=" * 80)
    print("VEREDITO POR PAGINA:")
    print("=" * 80)
    for i, page in enumerate(multi.pages, start=1):
        h = "OK" if page.headings else "FAIL"
        t = "OK" if page.tables else "skip"
        s = "OK" if page.section_breaks else "skip"
        ph = "OK" if page.placeholders else "skip"
        print(
            f"Page {i}: heading={h} ({len(page.headings)})  "
            f"table={t} ({len(page.tables)})  "
            f"sections={s} ({len(page.section_breaks)})  "
            f"placeholders={ph} ({len(page.placeholders)})"
        )

    print()
    print("=" * 80)
    print("AGGREGATE TOTALS:")
    print("=" * 80)
    print(f"  pages={multi.page_count}")
    print(f"  total_headings={multi.total_headings}")
    print(f"  total_tables={multi.total_tables}")
    print(f"  total_section_breaks={multi.total_section_breaks}")
    print(f"  total_placeholders={multi.total_placeholders}")
    print(f"  average_density={multi.average_density:.3f}")


if __name__ == "__main__":
    main()
