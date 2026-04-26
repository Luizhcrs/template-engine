"""10 — POC: doc com branding (logo, cores de marca, tipografia mista, footer).

Stress-test do ASCII layout em docs com design real:
- Header colorido com pseudo-logo (block) + nome da marca
- Accent vertical (sidebar de cor) na esquerda
- Tipografia mista: title condensed + body regular + monospace pra códigos
- Tabela com header colorido + zebra rows
- Footer com versão + paginação + linha fina

Hipótese: ASCII layout (luminance grayscale) IGNORA cor — mas estrutura via
luminance fica igual. Com PNG colorido convertido pra L (grayscale), bordas e
preenchimentos viram densidade. Detector continua acertando.

Run:
    python examples/10_styled_brand_doc.py [--out-dir out/branded]
"""

from __future__ import annotations

import argparse
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from engine.ascii_layout import detect_layout_features, image_to_ascii

# ===== Brand palette =====
BRAND_PRIMARY = (255, 122, 42)  # laranja
BRAND_DARK = (17, 24, 39)
BRAND_LIGHT = (249, 250, 251)
BRAND_ACCENT = (200, 60, 30)
ZEBRA = (245, 245, 245)


def _font(size: int, mono: bool = False) -> ImageFont.ImageFont:
    name = "consola.ttf" if mono else "arial.ttf"
    try:
        return ImageFont.truetype(name, size)
    except OSError:
        return ImageFont.load_default()


# ===== Generators =====


def make_template(path: Path, w: int = 800, h: int = 1100) -> dict[str, str]:
    img = Image.new("RGB", (w, h), color=BRAND_LIGHT)
    d = ImageDraw.Draw(img)
    f_title = _font(28)
    f_brand = _font(18)
    f_body = _font(14)
    f_mono = _font(13, mono=True)
    f_small = _font(10)

    # Brand sidebar (accent vertical bar)
    d.rectangle((0, 0, 14, h), fill=BRAND_PRIMARY)

    # Header bar com pseudo-logo + brand name
    d.rectangle((14, 0, w, 90), fill=BRAND_DARK)
    # Pseudo-logo (block geometric)
    d.rectangle((35, 25, 75, 65), fill=BRAND_PRIMARY)
    d.rectangle((50, 40, 90, 80), fill=BRAND_LIGHT, outline=BRAND_PRIMARY, width=2)
    d.text((110, 28), "ACME / RELATORIO", fill=BRAND_LIGHT, font=f_brand)
    d.text((110, 55), "documento corporativo", fill=BRAND_PRIMARY, font=f_small)

    # Title block colorido
    y = 120
    d.rectangle((30, y, w - 30, y + 50), fill=BRAND_PRIMARY)
    d.text((50, y + 12), "RELATORIO MENSAL", fill=BRAND_LIGHT, font=f_title)

    y += 80
    # Header com 3 campos em formato cartão
    d.text((30, y), "Codigo:", fill=BRAND_DARK, font=f_body)
    d.text((110, y), "[CODIGO]", fill=BRAND_ACCENT, font=f_mono)
    d.text((350, y), "Periodo:", fill=BRAND_DARK, font=f_body)
    d.text((430, y), "[PERIODO]", fill=BRAND_ACCENT, font=f_mono)
    d.text((600, y), "Versao:", fill=BRAND_DARK, font=f_body)
    d.text((670, y), "[VERSAO]", fill=BRAND_ACCENT, font=f_mono)

    y += 40
    d.line((30, y, w - 30, y), fill=BRAND_PRIMARY, width=2)

    y += 30
    # Section heading com bullet
    d.rectangle((30, y, 38, y + 20), fill=BRAND_PRIMARY)
    d.text((48, y + 1), "RESUMO EXECUTIVO", fill=BRAND_DARK, font=f_body)
    y += 35
    d.text((30, y), "[RESUMO_TEXTO]", fill=BRAND_DARK, font=f_body)

    y += 50
    # Section
    d.rectangle((30, y, 38, y + 20), fill=BRAND_PRIMARY)
    d.text((48, y + 1), "INDICADORES", fill=BRAND_DARK, font=f_body)
    y += 35

    # Tabela colorida com header laranja + zebra
    table_top = y
    col_x = [30, 250, 470, 770]
    rows_data = [
        ("Metrica", "Valor", "Status"),
        ("[METRICA_1]", "[VALOR_1]", "[STATUS_1]"),
        ("[METRICA_2]", "[VALOR_2]", "[STATUS_2]"),
        ("[METRICA_3]", "[VALOR_3]", "[STATUS_3]"),
    ]
    row_h = 32
    for r, row in enumerate(rows_data):
        yy = table_top + r * row_h
        if r == 0:
            d.rectangle((col_x[0], yy, col_x[-1], yy + row_h), fill=BRAND_PRIMARY)
            text_color = BRAND_LIGHT
        elif r % 2 == 0:
            d.rectangle((col_x[0], yy, col_x[-1], yy + row_h), fill=ZEBRA)
            text_color = BRAND_DARK
        else:
            text_color = BRAND_DARK
        for c, val in enumerate(row):
            d.text((col_x[c] + 8, yy + 8), val, fill=text_color, font=f_body)
    # Borders
    for x in col_x:
        d.line((x, table_top, x, table_top + len(rows_data) * row_h), fill=BRAND_DARK)
    for r in range(len(rows_data) + 1):
        yy = table_top + r * row_h
        d.line((col_x[0], yy, col_x[-1], yy), fill=BRAND_DARK)

    y = table_top + len(rows_data) * row_h + 40

    # Section observacoes
    d.rectangle((30, y, 38, y + 20), fill=BRAND_PRIMARY)
    d.text((48, y + 1), "OBSERVACOES", fill=BRAND_DARK, font=f_body)
    y += 35
    d.text((30, y), "[OBSERVACOES]", fill=BRAND_DARK, font=f_body)

    # Footer
    d.line((30, h - 60, w - 30, h - 60), fill=BRAND_PRIMARY, width=1)
    d.text((30, h - 50), "ACME Corp - confidencial", fill=BRAND_DARK, font=f_small)
    d.text((w - 110, h - 50), "v[VERSAO] | pag 1/1", fill=BRAND_DARK, font=f_small)

    img.save(path, "PNG")
    return {
        "CODIGO": "[CODIGO]",
        "PERIODO": "[PERIODO]",
        "VERSAO": "[VERSAO]",
        "RESUMO_TEXTO": "[RESUMO_TEXTO]",
        "METRICA_1": "[METRICA_1]",
        "VALOR_1": "[VALOR_1]",
        "STATUS_1": "[STATUS_1]",
        "OBSERVACOES": "[OBSERVACOES]",
    }


_SOURCE_LINES = [
    "Briefing mensal - 26/04/2026",
    "",
    "Codigo do relatorio: REL-2026-04",
    "Periodo de cobertura: abril/2026",
    "Versao corrente: 1.2",
    "",
    "Resumo geral:",
    "Trimestre superou meta em 12 porcento, foco em reducao de custos.",
    "",
    "Indicadores principais:",
    "  Receita - 1.250.000 - acima",
    "  Custo - 870.000 - dentro",
    "  Margem - 30.4% - acima",
    "",
    "Observacoes finais:",
    "Recomenda-se manter estrategia atual e revisar fornecedores no Q3.",
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
    img = Image.new("RGB", (w, h), color=BRAND_LIGHT)
    d = ImageDraw.Draw(img)
    f_title = _font(28)
    f_brand = _font(18)
    f_body = _font(14)
    f_mono = _font(13, mono=True)
    f_small = _font(10)

    d.rectangle((0, 0, 14, h), fill=BRAND_PRIMARY)
    d.rectangle((14, 0, w, 90), fill=BRAND_DARK)
    d.rectangle((35, 25, 75, 65), fill=BRAND_PRIMARY)
    d.rectangle((50, 40, 90, 80), fill=BRAND_LIGHT, outline=BRAND_PRIMARY, width=2)
    d.text((110, 28), "ACME / RELATORIO", fill=BRAND_LIGHT, font=f_brand)
    d.text((110, 55), "documento corporativo", fill=BRAND_PRIMARY, font=f_small)

    y = 120
    d.rectangle((30, y, w - 30, y + 50), fill=BRAND_PRIMARY)
    d.text((50, y + 12), "RELATORIO MENSAL", fill=BRAND_LIGHT, font=f_title)

    y += 80
    d.text((30, y), "Codigo:", fill=BRAND_DARK, font=f_body)
    d.text((110, y), data["CODIGO"], fill=BRAND_ACCENT, font=f_mono)
    d.text((350, y), "Periodo:", fill=BRAND_DARK, font=f_body)
    d.text((430, y), data["PERIODO"], fill=BRAND_ACCENT, font=f_mono)
    d.text((600, y), "Versao:", fill=BRAND_DARK, font=f_body)
    d.text((670, y), data["VERSAO"], fill=BRAND_ACCENT, font=f_mono)

    y += 40
    d.line((30, y, w - 30, y), fill=BRAND_PRIMARY, width=2)

    y += 30
    d.rectangle((30, y, 38, y + 20), fill=BRAND_PRIMARY)
    d.text((48, y + 1), "RESUMO EXECUTIVO", fill=BRAND_DARK, font=f_body)
    y += 35
    d.text((30, y), data["RESUMO_TEXTO"], fill=BRAND_DARK, font=f_body)

    y += 50
    d.rectangle((30, y, 38, y + 20), fill=BRAND_PRIMARY)
    d.text((48, y + 1), "INDICADORES", fill=BRAND_DARK, font=f_body)
    y += 35

    table_top = y
    col_x = [30, 250, 470, 770]
    rows_data = [
        ("Metrica", "Valor", "Status"),
        ("Receita", "1.250.000", "acima"),
        ("Custo", "870.000", "dentro"),
        ("Margem", "30.4%", "acima"),
    ]
    row_h = 32
    for r, row in enumerate(rows_data):
        yy = table_top + r * row_h
        if r == 0:
            d.rectangle((col_x[0], yy, col_x[-1], yy + row_h), fill=BRAND_PRIMARY)
            text_color = BRAND_LIGHT
        elif r % 2 == 0:
            d.rectangle((col_x[0], yy, col_x[-1], yy + row_h), fill=ZEBRA)
            text_color = BRAND_DARK
        else:
            text_color = BRAND_DARK
        for c, val in enumerate(row):
            d.text((col_x[c] + 8, yy + 8), val, fill=text_color, font=f_body)
    for x in col_x:
        d.line((x, table_top, x, table_top + len(rows_data) * row_h), fill=BRAND_DARK)
    for r in range(len(rows_data) + 1):
        yy = table_top + r * row_h
        d.line((col_x[0], yy, col_x[-1], yy), fill=BRAND_DARK)

    y = table_top + len(rows_data) * row_h + 40

    d.rectangle((30, y, 38, y + 20), fill=BRAND_PRIMARY)
    d.text((48, y + 1), "OBSERVACOES", fill=BRAND_DARK, font=f_body)
    y += 35
    d.text((30, y), data["OBSERVACOES"], fill=BRAND_DARK, font=f_body)

    d.line((30, h - 60, w - 30, h - 60), fill=BRAND_PRIMARY, width=1)
    d.text((30, h - 50), "ACME Corp - confidencial", fill=BRAND_DARK, font=f_small)
    d.text((w - 110, h - 50), f"v{data['VERSAO']} | pag 1/1", fill=BRAND_DARK, font=f_small)

    img.save(path, "PNG")


@dataclass
class ReplicationResult:
    extracted_data: dict[str, str]
    fields_filled: int
    fields_total: int


_FIELD_PATTERNS: dict[str, re.Pattern] = {
    "CODIGO": re.compile(r"Codigo do relatorio:\s*([A-Z]+-\d{4}-\d{2})", re.I),
    "PERIODO": re.compile(r"Periodo de cobertura:\s*([a-z]+/\d{4})", re.I),
    "VERSAO": re.compile(r"Versao corrente:\s*(\d+\.\d+)", re.I),
    "RESUMO_TEXTO": re.compile(r"Resumo geral:\s*\n([^\n]+)", re.I),
    "OBSERVACOES": re.compile(r"Observacoes finais:\s*\n([^\n]+)", re.I),
}


def replicate(template_phs: dict[str, str], source_text: str) -> ReplicationResult:
    extracted: dict[str, str] = {}
    for k, pat in _FIELD_PATTERNS.items():
        m = pat.search(source_text)
        if m:
            extracted[k] = m.group(1).strip()
    return ReplicationResult(
        extracted_data=extracted,
        fields_filled=len(extracted),
        fields_total=len(_FIELD_PATTERNS),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()

    if args.out_dir:
        out_dir = args.out_dir.resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
    else:
        out_dir = Path(tempfile.mkdtemp(prefix="te-branded-"))

    template_png = out_dir / "template.png"
    source_png = out_dir / "source.png"
    replica_png = out_dir / "replica.png"

    template_phs = make_template(template_png)
    make_source(source_png)

    rep = replicate(template_phs, "\n".join(_SOURCE_LINES))
    full = {
        "CODIGO": rep.extracted_data.get("CODIGO", "?"),
        "PERIODO": rep.extracted_data.get("PERIODO", "?"),
        "VERSAO": rep.extracted_data.get("VERSAO", "?"),
        "RESUMO_TEXTO": rep.extracted_data.get("RESUMO_TEXTO", "?"),
        "OBSERVACOES": rep.extracted_data.get("OBSERVACOES", "?"),
    }
    make_replica(replica_png, full)

    ramp = "@#%*+=-:. "
    grid_t = image_to_ascii(template_png, cols=80, rows=60, ramp=ramp)
    grid_s = image_to_ascii(source_png, cols=80, rows=60, ramp=ramp)
    grid_r = image_to_ascii(replica_png, cols=80, rows=60, ramp=ramp)

    feat_t = detect_layout_features(grid_t, ramp=ramp)
    feat_s = detect_layout_features(grid_s, ramp=ramp)
    feat_r = detect_layout_features(grid_r, ramp=ramp)

    print(f"PNGs em: {out_dir}")
    print()
    print("=" * 80)
    print("ESTRUTURA — doc com BRANDING colorido")
    print("=" * 80)
    print(f"{'Métrica':<22} | {'TEMPLATE':>10} | {'SOURCE':>10} | {'REPLICA':>10}")
    print("-" * 80)
    print(
        f"{'headings':<22} | {len(feat_t.headings):>10} | {len(feat_s.headings):>10} | {len(feat_r.headings):>10}"
    )
    print(f"{'tables':<22} | {len(feat_t.tables):>10} | {len(feat_s.tables):>10} | {len(feat_r.tables):>10}")
    print(
        f"{'section_breaks':<22} | {len(feat_t.section_breaks):>10} | {len(feat_s.section_breaks):>10} | {len(feat_r.section_breaks):>10}"
    )
    print(
        f"{'placeholders':<22} | {len(feat_t.placeholders):>10} | {len(feat_s.placeholders):>10} | {len(feat_r.placeholders):>10}"
    )
    print(
        f"{'density':<22} | {feat_t.overall_density:>10.3f} | {feat_s.overall_density:>10.3f} | {feat_r.overall_density:>10.3f}"
    )
    print()

    print("=" * 80)
    print("CAMPOS REPLICADOS (regex puro, ZERO LLM)")
    print("=" * 80)
    for k in _FIELD_PATTERNS:
        v = rep.extracted_data.get(k, "(NOT FOUND)")
        print(f"  {k:<18} -> {v}")
    print()
    print(f"Score: {rep.fields_filled}/{rep.fields_total} campos preenchidos")
    print()

    print("=" * 80)
    print("HIPOTESE: cor/branding NAO atrapalha ASCII layout (luminance only)")
    print("=" * 80)
    structure_match = len(feat_t.headings) == len(feat_r.headings) and len(feat_t.tables) == len(
        feat_r.tables
    )
    print(f"Estrutura preservada (T == R):  {'PASS' if structure_match else 'FAIL'}")


if __name__ == "__main__":
    main()
