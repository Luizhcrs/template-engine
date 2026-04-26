"""12 — POC: minimalist design (zero cor, espacos largos, hairlines).

Stress-test em design ultra-minimal tipo japonese editorial:
- Pure black & white
- Hairline rules (1px)
- Massive whitespace
- Single font, sizes variantes
- Sem icones, sem cores

Run:
    python examples/12_minimalist_design.py [--out-dir out/minimalist]
"""

from __future__ import annotations

import argparse
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from engine.ascii_layout import detect_layout_features, image_to_ascii


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def make_template(path: Path, w: int = 800, h: int = 1100) -> dict[str, str]:
    img = Image.new("RGB", (w, h), color="white")
    d = ImageDraw.Draw(img)
    f_huge = _font(56)
    f_med = _font(20)
    f_body = _font(13)
    f_micro = _font(9)

    # Top hairline
    d.line((100, 80, w - 100, 80), fill="black", width=1)
    d.text((100, 95), "ESTUDIO", fill="black", font=f_micro)
    d.text((w - 200, 95), "[NUMERO]  /  [ANO]", fill="black", font=f_micro)

    # Massive title (centered region)
    y = 250
    d.text((100, y), "[TITULO]", fill="black", font=f_huge)

    y = 360
    d.line((100, y, 200, y), fill="black", width=1)
    y += 30
    d.text((100, y), "[SUBTITULO]", fill="black", font=f_med)

    # Wide whitespace
    y = 520
    d.line((100, y, w - 100, y), fill="black", width=1)
    y += 30
    d.text((100, y), "AUTOR", fill="black", font=f_micro)
    d.text((100, y + 18), "[AUTOR]", fill="black", font=f_body)
    d.text((350, y), "PUBLICADO", fill="black", font=f_micro)
    d.text((350, y + 18), "[PUBLICADO]", fill="black", font=f_body)
    d.text((600, y), "PAGINAS", fill="black", font=f_micro)
    d.text((600, y + 18), "[PAGINAS]", fill="black", font=f_body)

    # Body
    y = 650
    d.line((100, y, 200, y), fill="black", width=1)
    y += 30
    d.text((100, y), "[CORPO_TEXTO]", fill="black", font=f_body)

    # Footer hairline
    d.line((100, h - 80, w - 100, h - 80), fill="black", width=1)
    d.text((100, h - 65), "[REFERENCIA]", fill="black", font=f_micro)

    img.save(path, "PNG")
    return {
        "NUMERO": "[NUMERO]",
        "ANO": "[ANO]",
        "TITULO": "[TITULO]",
        "SUBTITULO": "[SUBTITULO]",
        "AUTOR": "[AUTOR]",
        "PUBLICADO": "[PUBLICADO]",
        "PAGINAS": "[PAGINAS]",
        "CORPO_TEXTO": "[CORPO_TEXTO]",
        "REFERENCIA": "[REFERENCIA]",
    }


_SOURCE_LINES = [
    "Briefing minimalista 2026",
    "",
    "Numero da edicao: 07",
    "Ano de publicacao: 2026",
    "",
    "Titulo: Vazio Pleno",
    "Subtitulo: ensaio sobre o nada",
    "",
    "Autor: Hiroshi Tanaka",
    "Data publicada: 2026-04-26",
    "Total de paginas: 144",
    "",
    "Corpo principal:",
    "O espaco em branco e o protagonista esquecido.",
    "",
    "Referencia bibliografica: ISBN 978-85-0042-0",
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
    img = Image.new("RGB", (w, h), color="white")
    d = ImageDraw.Draw(img)
    f_huge = _font(56)
    f_med = _font(20)
    f_body = _font(13)
    f_micro = _font(9)

    d.line((100, 80, w - 100, 80), fill="black", width=1)
    d.text((100, 95), "ESTUDIO", fill="black", font=f_micro)
    d.text((w - 200, 95), f"{data['NUMERO']}  /  {data['ANO']}", fill="black", font=f_micro)

    d.text((100, 250), data["TITULO"][:14], fill="black", font=f_huge)
    d.line((100, 360, 200, 360), fill="black", width=1)
    d.text((100, 390), data["SUBTITULO"][:30], fill="black", font=f_med)

    y = 520
    d.line((100, y, w - 100, y), fill="black", width=1)
    d.text((100, y + 30), "AUTOR", fill="black", font=f_micro)
    d.text((100, y + 48), data["AUTOR"], fill="black", font=f_body)
    d.text((350, y + 30), "PUBLICADO", fill="black", font=f_micro)
    d.text((350, y + 48), data["PUBLICADO"], fill="black", font=f_body)
    d.text((600, y + 30), "PAGINAS", fill="black", font=f_micro)
    d.text((600, y + 48), data["PAGINAS"], fill="black", font=f_body)

    d.line((100, 650, 200, 650), fill="black", width=1)
    d.text((100, 680), data["CORPO_TEXTO"][:55], fill="black", font=f_body)

    d.line((100, h - 80, w - 100, h - 80), fill="black", width=1)
    d.text((100, h - 65), data["REFERENCIA"], fill="black", font=f_micro)

    img.save(path, "PNG")


@dataclass
class ReplicationResult:
    extracted_data: dict[str, str]
    fields_filled: int
    fields_total: int


_FIELD_PATTERNS: dict[str, re.Pattern] = {
    "NUMERO": re.compile(r"Numero da edicao:\s*(\d+)", re.I),
    "ANO": re.compile(r"Ano de publicacao:\s*(\d{4})", re.I),
    "TITULO": re.compile(r"Titulo:\s*([A-Z][\w\s]+)", re.I),
    "SUBTITULO": re.compile(r"Subtitulo:\s*([a-z][\w\s]+)", re.I),
    "AUTOR": re.compile(r"Autor:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", re.I),
    "PUBLICADO": re.compile(r"Data publicada:\s*(\d{4}-\d{2}-\d{2})", re.I),
    "PAGINAS": re.compile(r"Total de paginas:\s*(\d+)", re.I),
    "CORPO_TEXTO": re.compile(r"Corpo principal:\s*\n([^\n]+)", re.I),
    "REFERENCIA": re.compile(r"Referencia bibliografica:\s*([A-Z0-9\-\s]+)", re.I),
}


def replicate(template_phs: dict[str, str], source_text: str) -> ReplicationResult:
    extracted: dict[str, str] = {}
    for k, pat in _FIELD_PATTERNS.items():
        m = pat.search(source_text)
        if m:
            extracted[k] = m.group(1).strip()
    return ReplicationResult(extracted, len(extracted), len(_FIELD_PATTERNS))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()

    out_dir = args.out_dir.resolve() if args.out_dir else Path(tempfile.mkdtemp(prefix="te-min-"))
    out_dir.mkdir(parents=True, exist_ok=True)

    template_png = out_dir / "template.png"
    source_png = out_dir / "source.png"
    replica_png = out_dir / "replica.png"

    template_phs = make_template(template_png)
    make_source(source_png)
    rep = replicate(template_phs, "\n".join(_SOURCE_LINES))
    full = {k: rep.extracted_data.get(k, "?") for k in template_phs}
    make_replica(replica_png, full)

    ramp = "@#%*+=-:. "
    feat_t = detect_layout_features(image_to_ascii(template_png, cols=80, rows=60, ramp=ramp), ramp=ramp)
    feat_r = detect_layout_features(image_to_ascii(replica_png, cols=80, rows=60, ramp=ramp), ramp=ramp)

    print(f"PNGs: {out_dir}\n")
    print("=" * 80)
    print("ESTRUTURA - design MINIMALIST (B&W + hairlines + whitespace)")
    print("=" * 80)
    for name, t, r in [
        ("headings", len(feat_t.headings), len(feat_r.headings)),
        ("tables", len(feat_t.tables), len(feat_r.tables)),
        ("section_breaks", len(feat_t.section_breaks), len(feat_r.section_breaks)),
        ("placeholders", len(feat_t.placeholders), len(feat_r.placeholders)),
    ]:
        print(f"  {name:<20} T={t:<3} R={r:<3} {'OK' if t == r else 'd=' + str(abs(t - r))}")
    print(f"  density              T={feat_t.overall_density:.3f} R={feat_r.overall_density:.3f}")
    print()
    print(f"Campos replicados: {rep.fields_filled}/{rep.fields_total}")
    for k, v in rep.extracted_data.items():
        print(f"  {k:<14} -> {v}")


if __name__ == "__main__":
    main()
