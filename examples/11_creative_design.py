"""11 — POC: creative design (gradiente, tipografia mista grande, layout assimetrico).

Stress-test em design moderno tipo agencia/startup:
- Gradient header (simulado via blocos coloridos)
- Tipografia tamanho mix (giant title, micro caption)
- Layout em 2 colunas
- Cards com sombra simulada
- Tags/badges coloridas

Run:
    python examples/11_creative_design.py [--out-dir out/creative]
"""

from __future__ import annotations

import argparse
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from engine.ascii_layout import detect_layout_features, image_to_ascii
from engine.pattern_inference import apply_inferred, infer_field_patterns

C_BG = (15, 15, 25)
C_NEON = (180, 100, 255)
C_PINK = (255, 100, 180)
C_LIGHT = (240, 240, 255)
C_GRAY = (100, 100, 120)


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def make_template(path: Path, w: int = 800, h: int = 1100) -> dict[str, str]:
    img = Image.new("RGB", (w, h), color=C_BG)
    d = ImageDraw.Draw(img)
    f_giant = _font(48)
    f_med = _font(18)
    f_body = _font(14)
    f_micro = _font(10)

    # Pseudo-gradient header (3 bands)
    d.rectangle((0, 0, w, 30), fill=C_NEON)
    d.rectangle((0, 30, w, 60), fill=C_PINK)
    d.rectangle((0, 60, w, 90), fill=C_BG)

    # Giant title
    d.text((40, 130), "[TITLE]", fill=C_LIGHT, font=f_giant)
    d.text((40, 195), "edicao [EDICAO]  -  [DATA]", fill=C_GRAY, font=f_micro)

    # Tag badges
    y = 240
    for i, label in enumerate(["#TAG_1", "#TAG_2", "#TAG_3"]):
        x = 40 + i * 90
        d.rectangle((x, y, x + 75, y + 25), fill=C_NEON)
        d.text((x + 8, y + 4), label, fill=C_BG, font=f_micro)

    y = 290
    # 2-column layout
    col_left = 40
    col_right = 420
    col_w = 350

    # Left column - card 1
    d.rectangle((col_left, y, col_left + col_w, y + 200), fill=C_LIGHT)
    d.rectangle((col_left + 20, y + 20, col_left + 50, y + 50), fill=C_NEON)
    d.text((col_left + 20, y + 65), "DESTAQUE", fill=C_PINK, font=f_med)
    d.text((col_left + 20, y + 95), "[DESTAQUE_TEXTO]", fill=C_BG, font=f_body)

    # Right column - card 2
    d.rectangle((col_right, y, col_right + col_w, y + 200), fill=C_LIGHT)
    d.rectangle((col_right + 20, y + 20, col_right + 50, y + 50), fill=C_PINK)
    d.text((col_right + 20, y + 65), "AUTOR", fill=C_NEON, font=f_med)
    d.text((col_right + 20, y + 95), "[AUTOR_NOME]", fill=C_BG, font=f_body)

    # Quote block (full width)
    y = 530
    d.rectangle((40, y, w - 40, y + 100), fill=C_NEON)
    d.text((60, y + 30), '"[QUOTE]"', fill=C_BG, font=f_med)

    # Footer asymmetric
    y = h - 100
    d.line((40, y, w - 40, y), fill=C_PINK, width=1)
    d.text((40, y + 20), "creative.studio", fill=C_NEON, font=f_micro)
    d.text((w - 100, y + 20), "[ISSN]", fill=C_GRAY, font=f_micro)

    img.save(path, "PNG")
    return {
        "TITLE": "[TITLE]",
        "EDICAO": "[EDICAO]",
        "DATA": "[DATA]",
        "DESTAQUE_TEXTO": "[DESTAQUE_TEXTO]",
        "AUTOR_NOME": "[AUTOR_NOME]",
        "QUOTE": "[QUOTE]",
        "ISSN": "[ISSN]",
    }


_SOURCE_LINES = [
    "Briefing editorial 2026-04",
    "",
    "Titulo da edicao: Quebrando Padroes",
    "Edicao numero: 042",
    "Data de publicacao: 2026-04-26",
    "",
    "Texto destaque:",
    "Trinta projetos de design generativo no semestre.",
    "",
    "Autor responsavel: Marina Costa",
    "",
    "Citacao principal:",
    "O futuro pertence aos que reinventam.",
    "",
    "ISSN: 2026-0042-CR",
]


def make_source(path: Path, w: int = 800, h: int = 1100) -> None:
    img = Image.new("RGB", (w, h), color="white")
    d = ImageDraw.Draw(img)
    fb = _font(14)
    y = 60
    for line in _SOURCE_LINES:
        d.text((40, y), line, fill="black", font=fb)
        y += 22
    img.save(path, "PNG")


def make_replica(path: Path, data: dict[str, str], w: int = 800, h: int = 1100) -> None:
    img = Image.new("RGB", (w, h), color=C_BG)
    d = ImageDraw.Draw(img)
    f_giant = _font(48)
    f_med = _font(18)
    f_body = _font(14)
    f_micro = _font(10)

    d.rectangle((0, 0, w, 30), fill=C_NEON)
    d.rectangle((0, 30, w, 60), fill=C_PINK)
    d.rectangle((0, 60, w, 90), fill=C_BG)

    d.text((40, 130), data["TITLE"][:25], fill=C_LIGHT, font=f_giant)
    d.text((40, 195), f"edicao {data['EDICAO']}  -  {data['DATA']}", fill=C_GRAY, font=f_micro)

    y = 240
    for i, label in enumerate(["#design", "#editorial", "#2026"]):
        x = 40 + i * 90
        d.rectangle((x, y, x + 75, y + 25), fill=C_NEON)
        d.text((x + 8, y + 4), label, fill=C_BG, font=f_micro)

    y = 290
    col_left, col_right, col_w = 40, 420, 350

    d.rectangle((col_left, y, col_left + col_w, y + 200), fill=C_LIGHT)
    d.rectangle((col_left + 20, y + 20, col_left + 50, y + 50), fill=C_NEON)
    d.text((col_left + 20, y + 65), "DESTAQUE", fill=C_PINK, font=f_med)
    d.text((col_left + 20, y + 95), data["DESTAQUE_TEXTO"][:35], fill=C_BG, font=f_body)

    d.rectangle((col_right, y, col_right + col_w, y + 200), fill=C_LIGHT)
    d.rectangle((col_right + 20, y + 20, col_right + 50, y + 50), fill=C_PINK)
    d.text((col_right + 20, y + 65), "AUTOR", fill=C_NEON, font=f_med)
    d.text((col_right + 20, y + 95), data["AUTOR_NOME"], fill=C_BG, font=f_body)

    y = 530
    d.rectangle((40, y, w - 40, y + 100), fill=C_NEON)
    d.text((60, y + 30), f'"{data["QUOTE"][:50]}"', fill=C_BG, font=f_med)

    y = h - 100
    d.line((40, y, w - 40, y), fill=C_PINK, width=1)
    d.text((40, y + 20), "creative.studio", fill=C_NEON, font=f_micro)
    d.text((w - 100, y + 20), data["ISSN"], fill=C_GRAY, font=f_micro)

    img.save(path, "PNG")


@dataclass
class ReplicationResult:
    extracted_data: dict[str, str]
    fields_filled: int
    fields_total: int


_GOLD_DOCS = [
    "\n".join(_SOURCE_LINES),
    """Briefing editorial 2025-12

Titulo da edicao: Linhas e Curvas
Edicao numero: 035
Data de publicacao: 2025-12-10

Texto destaque:
Quinze projetos de tipografia experimental analisados.

Autor responsavel: Lucas Pereira

Citacao principal:
A forma e a primeira linguagem do design.

ISSN: 2025-0035-CR
""",
    """Briefing editorial 2026-08

Titulo da edicao: Cores Vivas
Edicao numero: 050
Data de publicacao: 2026-08-22

Texto destaque:
Especial sobre paletas em ambientes virtuais imersivos.

Autor responsavel: Carla Mendes

Citacao principal:
Cor e emocao codificada em comprimento de onda.

ISSN: 2026-0050-CR
""",
]

_FIELD_EXAMPLES = {
    "TITLE": ["Quebrando Padroes", "Linhas e Curvas", "Cores Vivas"],
    "EDICAO": ["042", "035", "050"],
    "DATA": ["2026-04-26", "2025-12-10", "2026-08-22"],
    "DESTAQUE_TEXTO": [
        "Trinta projetos de design generativo no semestre.",
        "Quinze projetos de tipografia experimental analisados.",
        "Especial sobre paletas em ambientes virtuais imersivos.",
    ],
    "AUTOR_NOME": ["Marina Costa", "Lucas Pereira", "Carla Mendes"],
    "QUOTE": [
        "O futuro pertence aos que reinventam.",
        "A forma e a primeira linguagem do design.",
        "Cor e emocao codificada em comprimento de onda.",
    ],
    "ISSN": ["2026-0042-CR", "2025-0035-CR", "2026-0050-CR"],
}

_INFERRED = infer_field_patterns(gold_docs=_GOLD_DOCS, field_examples=_FIELD_EXAMPLES)


def replicate(template_phs: dict[str, str], source_text: str) -> ReplicationResult:
    extracted = apply_inferred(_INFERRED, source_text)
    return ReplicationResult(
        extracted_data=extracted,
        fields_filled=len(extracted),
        fields_total=len(_FIELD_EXAMPLES),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()

    if args.out_dir:
        out_dir = args.out_dir.resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
    else:
        out_dir = Path(tempfile.mkdtemp(prefix="te-creative-"))

    template_png = out_dir / "template.png"
    source_png = out_dir / "source.png"
    replica_png = out_dir / "replica.png"

    template_phs = make_template(template_png)
    make_source(source_png)
    rep = replicate(template_phs, "\n".join(_SOURCE_LINES))
    full = {**{k: rep.extracted_data.get(k, "?") for k in template_phs}}
    make_replica(replica_png, full)

    ramp = "@#%*+=-:. "
    grid_t = image_to_ascii(template_png, cols=80, rows=60, ramp=ramp)
    grid_r = image_to_ascii(replica_png, cols=80, rows=60, ramp=ramp)
    feat_t = detect_layout_features(grid_t, ramp=ramp)
    feat_r = detect_layout_features(grid_r, ramp=ramp)

    print(f"PNGs: {out_dir}\n")
    print("=" * 80)
    print("ESTRUTURA - design CREATIVE (dark bg + neon + 2 cols)")
    print("=" * 80)
    print(f"{'metric':<22} | {'TEMPLATE':>10} | {'REPLICA':>10}")
    print(f"{'headings':<22} | {len(feat_t.headings):>10} | {len(feat_r.headings):>10}")
    print(f"{'tables':<22} | {len(feat_t.tables):>10} | {len(feat_r.tables):>10}")
    print(f"{'section_breaks':<22} | {len(feat_t.section_breaks):>10} | {len(feat_r.section_breaks):>10}")
    print(f"{'placeholders':<22} | {len(feat_t.placeholders):>10} | {len(feat_r.placeholders):>10}")
    print(f"{'density':<22} | {feat_t.overall_density:>10.3f} | {feat_r.overall_density:>10.3f}")
    print()
    print(f"Campos replicados: {rep.fields_filled}/{rep.fields_total}")
    for k, v in rep.extracted_data.items():
        print(f"  {k:<18} -> {v}")


if __name__ == "__main__":
    main()
