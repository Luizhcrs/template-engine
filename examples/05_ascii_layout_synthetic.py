"""05 — POC: ASCII layout via PNG sintético (sem LibreOffice).

Cria PNG estilo documento via Pillow puro (heading, parágrafos, tabela, placeholder).
Roda image_to_ascii + detect_layout_features. Mostra POC sem dep externa.

Run:
    python examples/05_ascii_layout_synthetic.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from engine.ascii_layout import detect_layout_features, image_to_ascii, summarize_layout


def make_synthetic_doc(path: Path, width: int = 800, height: int = 1100) -> None:
    """Desenha um documento sintético: heading, parágrafos, tabela, placeholders."""
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)

    try:
        font_h = ImageFont.truetype("arial.ttf", 36)
        font_b = ImageFont.truetype("arial.ttf", 16)
    except OSError:
        font_h = ImageFont.load_default()
        font_b = ImageFont.load_default()

    # Heading 1 (denso)
    draw.rectangle((40, 40, 760, 90), fill="black")
    draw.text((50, 48), "RELATORIO TECNICO", fill="white", font=font_h)

    # Section 1
    y = 130
    draw.text((40, y), "1. OBJETIVO", fill="black", font=font_b)
    draw.line((40, y + 22, 200, y + 22), fill="black", width=2)
    y += 40
    for line in [
        "Este documento descreve o procedimento padrao de auditoria",
        "interna conforme normas ABNT e ISO 9001:2015.",
    ]:
        draw.text((40, y), line, fill="black", font=font_b)
        y += 22

    # Section break (espaço)
    y += 60

    # Heading section 2
    draw.text((40, y), "2. PROCEDIMENTOS", fill="black", font=font_b)
    draw.line((40, y + 22, 250, y + 22), fill="black", width=2)
    y += 40

    # Tabela 4 linhas x 3 colunas (uniforme)
    table_top = y
    table_bottom = y + 120
    col_x = [40, 240, 480, 760]
    row_h = 30
    # bordas verticais
    for x in col_x:
        draw.line((x, table_top, x, table_bottom), fill="black", width=1)
    # bordas horizontais
    for r in range(5):
        yy = table_top + r * row_h
        draw.line((40, yy, 760, yy), fill="black", width=1)
    # conteudo
    headers = ["ID", "Etapa", "Responsavel"]
    for i, h in enumerate(headers):
        draw.text((col_x[i] + 8, table_top + 6), h, fill="black", font=font_b)
    for r in range(1, 4):
        for c in range(3):
            draw.text(
                (col_x[c] + 8, table_top + r * row_h + 6),
                f"v{r}{c}",
                fill="black",
                font=font_b,
            )

    y = table_bottom + 60

    # Section 3 + placeholder
    draw.text((40, y), "3. ASSINATURA", fill="black", font=font_b)
    draw.line((40, y + 22, 220, y + 22), fill="black", width=2)
    y += 40
    draw.text((40, y), "Nome:", fill="black", font=font_b)
    # placeholder underscore
    draw.line((110, y + 18, 600, y + 18), fill="black", width=2)
    y += 40
    draw.text((40, y), "Data:", fill="black", font=font_b)
    draw.line((110, y + 18, 300, y + 18), fill="black", width=2)

    img.save(path, "PNG")


def main() -> None:
    out_dir = Path(tempfile.mkdtemp(prefix="te-poc-"))
    png = out_dir / "synthetic.png"
    make_synthetic_doc(png)
    print(f"PNG sintetico criado em: {png}\n")

    # ASCII grid 80x60. Ramp ASCII puro pra compatibilidade com Windows cp1252.
    ascii_ramp = "@#%*+=-:. "
    grid = image_to_ascii(png, cols=80, rows=60, ramp=ascii_ramp)
    print("=" * 80)
    print("ASCII GRID (80x60, ramp ASCII):")
    print("=" * 80)
    print(grid)
    print()

    # Features
    features = detect_layout_features(grid, ramp=ascii_ramp)
    print("=" * 80)
    print("LAYOUT FEATURES DETECTADAS:")
    print("=" * 80)
    print(summarize_layout(features))
    print()

    print("=" * 80)
    print("VEREDITO:")
    print("=" * 80)
    print(f"  - Heading detectado:        {'OK' if features.headings else 'FAIL'} ({len(features.headings)})")
    print(f"  - Tabela detectada:         {'OK' if features.tables else 'FAIL'} ({len(features.tables)})")
    print(
        f"  - Section breaks:           {'OK' if features.section_breaks else 'FAIL'} ({len(features.section_breaks)})"
    )
    print(
        f"  - Placeholders detectados:  {'OK' if features.placeholders else 'FAIL'} ({len(features.placeholders)})"
    )
    print(f"  - Densidade geral:          {features.overall_density:.3f}")


if __name__ == "__main__":
    main()
