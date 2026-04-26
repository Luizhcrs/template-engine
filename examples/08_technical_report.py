"""08 — POC: laudo técnico (caso real B2B).

Estrutura típica de laudo:
- Header c/ 5 campos (código, revisão, data, responsável, classe)
- Section OBJETIVO
- Tabela PROCEDIMENTO (etapas × responsável × status)
- Tabela HISTÓRICO DE REVISÕES (rev × data × alteração)
- Section ASSINATURA + placeholders

Caso de uso real: empresa tem 100+ laudos a emitir/ano, mesma estrutura, dados
diferentes. Replicação automática SEM LLM via regex.

Run:
    python examples/08_technical_report.py [--out-dir out/laudo]
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


# ===== Generators =====


def make_template(path: Path, w: int = 800, h: int = 1200) -> dict[str, str]:
    img = Image.new("RGB", (w, h), color="white")
    d = ImageDraw.Draw(img)
    fh = _font(28)
    fb = _font(15)

    # Title bar
    d.rectangle((40, 40, 760, 90), fill="black")
    d.text((50, 50), "LAUDO TECNICO", fill="white", font=fh)

    # Header table 2x5 (label | value)
    table_top = 110
    rows_h = [
        ("Codigo:", "[CODIGO]"),
        ("Revisao:", "[REVISAO]"),
        ("Data:", "[DATA]"),
        ("Responsavel:", "[RESPONSAVEL]"),
        ("Classe:", "[CLASSE]"),
    ]
    for x in (40, 220, 760):
        d.line((x, table_top, x, table_top + 5 * 28), fill="black")
    for i, (label, ph) in enumerate(rows_h):
        yy = table_top + i * 28
        d.line((40, yy, 760, yy), fill="black")
        d.text((48, yy + 6), label, fill="black", font=fb)
        d.text((228, yy + 6), ph, fill="black", font=fb)
    d.line((40, table_top + 5 * 28, 760, table_top + 5 * 28), fill="black")

    y = table_top + 5 * 28 + 30

    # OBJETIVO
    d.text((40, y), "1. OBJETIVO", fill="black", font=fb)
    d.line((40, y + 20, 200, y + 20), fill="black", width=2)
    y += 35
    d.text((40, y), "[OBJETIVO_TEXTO]", fill="black", font=fb)
    y += 50

    # PROCEDIMENTO (table 4 rows x 3 cols)
    d.text((40, y), "2. PROCEDIMENTO", fill="black", font=fb)
    d.line((40, y + 20, 250, y + 20), fill="black", width=2)
    y += 35
    proc_top = y
    col_x = [40, 240, 520, 760]
    for x in col_x:
        d.line((x, proc_top, x, proc_top + 4 * 32), fill="black")
    for r in range(5):
        d.line((40, proc_top + r * 32, 760, proc_top + r * 32), fill="black")
    d.text((48, proc_top + 6), "Etapa", fill="black", font=fb)
    d.text((248, proc_top + 6), "Responsavel", fill="black", font=fb)
    d.text((528, proc_top + 6), "Status", fill="black", font=fb)
    for r in range(1, 4):
        d.text((48, proc_top + r * 32 + 6), f"[ETAPA_{r}]", fill="black", font=fb)
        d.text((248, proc_top + r * 32 + 6), f"[RESP_{r}]", fill="black", font=fb)
        d.text((528, proc_top + r * 32 + 6), f"[STATUS_{r}]", fill="black", font=fb)

    y = proc_top + 4 * 32 + 30

    # HISTÓRICO DE REVISÕES
    d.text((40, y), "3. HISTORICO DE REVISOES", fill="black", font=fb)
    d.line((40, y + 20, 320, y + 20), fill="black", width=2)
    y += 35
    hist_top = y
    hcol_x = [40, 140, 280, 760]
    for x in hcol_x:
        d.line((x, hist_top, x, hist_top + 3 * 28), fill="black")
    for r in range(4):
        d.line((40, hist_top + r * 28, 760, hist_top + r * 28), fill="black")
    d.text((48, hist_top + 6), "Rev", fill="black", font=fb)
    d.text((148, hist_top + 6), "Data", fill="black", font=fb)
    d.text((288, hist_top + 6), "Alteracao", fill="black", font=fb)
    for r in range(1, 3):
        d.text((48, hist_top + r * 28 + 6), f"[REV_{r}]", fill="black", font=fb)
        d.text((148, hist_top + r * 28 + 6), f"[DATA_R_{r}]", fill="black", font=fb)
        d.text((288, hist_top + r * 28 + 6), f"[ALT_{r}]", fill="black", font=fb)

    y = hist_top + 3 * 28 + 40

    # Section break + assinatura
    d.text((40, y), "4. ASSINATURA", fill="black", font=fb)
    d.line((40, y + 20, 200, y + 20), fill="black", width=2)
    y += 50
    d.text((40, y), "Aprovado por:", fill="black", font=fb)
    d.line((180, y + 18, 600, y + 18), fill="black", width=2)

    img.save(path, "PNG")
    return {
        "CODIGO": "[CODIGO]",
        "REVISAO": "[REVISAO]",
        "DATA": "[DATA]",
        "RESPONSAVEL": "[RESPONSAVEL]",
        "CLASSE": "[CLASSE]",
        "OBJETIVO_TEXTO": "[OBJETIVO_TEXTO]",
    }


_SOURCE_LINES = [
    "REGISTRO INTERNO - 26/04/2026",
    "",
    "Codigo do laudo: LAUDO-2026-042",
    "Revisao corrente: 03",
    "Data de emissao: 2026-04-26",
    "Engenheiro responsavel: Maria Souza",
    "Classe operacional: A",
    "",
    "Sobre o objetivo:",
    "Avaliar conformidade do equipamento ABC-9 conforme ISO 9001.",
    "",
    "Procedimento aplicado:",
    "Etapa 1: Coletar amostras (Joao Silva, concluido)",
    "Etapa 2: Analisar resultados (Maria Souza, em andamento)",
    "Etapa 3: Emitir parecer final (Carlos Lima, pendente)",
    "",
    "Historico de revisoes:",
    "01 em 2026-04-10: criacao do laudo.",
    "02 em 2026-04-18: ajuste no objetivo.",
    "",
    "Aprovacao final pendente.",
]


def make_source(path: Path, w: int = 800, h: int = 1200) -> dict[str, str]:
    img = Image.new("RGB", (w, h), color="white")
    d = ImageDraw.Draw(img)
    fb = _font(15)

    y = 60
    for line in _SOURCE_LINES:
        d.text((40, y), line, fill="black", font=fb)
        y += 22

    img.save(path, "PNG")
    return {
        "CODIGO": "LAUDO-2026-042",
        "REVISAO": "03",
        "DATA": "2026-04-26",
        "RESPONSAVEL": "Maria Souza",
        "CLASSE": "A",
        "OBJETIVO_TEXTO": "Avaliar conformidade do equipamento ABC-9 conforme ISO 9001.",
    }


def make_replica(path: Path, data: dict[str, str], w: int = 800, h: int = 1200) -> None:
    img = Image.new("RGB", (w, h), color="white")
    d = ImageDraw.Draw(img)
    fh = _font(28)
    fb = _font(15)

    d.rectangle((40, 40, 760, 90), fill="black")
    d.text((50, 50), "LAUDO TECNICO", fill="white", font=fh)

    table_top = 110
    rows_h = [
        ("Codigo:", data["CODIGO"]),
        ("Revisao:", data["REVISAO"]),
        ("Data:", data["DATA"]),
        ("Responsavel:", data["RESPONSAVEL"]),
        ("Classe:", data["CLASSE"]),
    ]
    for x in (40, 220, 760):
        d.line((x, table_top, x, table_top + 5 * 28), fill="black")
    for i, (label, val) in enumerate(rows_h):
        yy = table_top + i * 28
        d.line((40, yy, 760, yy), fill="black")
        d.text((48, yy + 6), label, fill="black", font=fb)
        d.text((228, yy + 6), val, fill="black", font=fb)
    d.line((40, table_top + 5 * 28, 760, table_top + 5 * 28), fill="black")

    y = table_top + 5 * 28 + 30
    d.text((40, y), "1. OBJETIVO", fill="black", font=fb)
    d.line((40, y + 20, 200, y + 20), fill="black", width=2)
    y += 35
    d.text((40, y), data["OBJETIVO_TEXTO"], fill="black", font=fb)
    y += 50

    d.text((40, y), "2. PROCEDIMENTO", fill="black", font=fb)
    d.line((40, y + 20, 250, y + 20), fill="black", width=2)
    y += 35
    proc_top = y
    col_x = [40, 240, 520, 760]
    for x in col_x:
        d.line((x, proc_top, x, proc_top + 4 * 32), fill="black")
    for r in range(5):
        d.line((40, proc_top + r * 32, 760, proc_top + r * 32), fill="black")
    d.text((48, proc_top + 6), "Etapa", fill="black", font=fb)
    d.text((248, proc_top + 6), "Responsavel", fill="black", font=fb)
    d.text((528, proc_top + 6), "Status", fill="black", font=fb)
    proc_rows = [
        ("Coletar amostras", "Joao Silva", "concluido"),
        ("Analisar resultados", "Maria Souza", "andamento"),
        ("Emitir parecer", "Carlos Lima", "pendente"),
    ]
    for r, row in enumerate(proc_rows, start=1):
        for c, val in enumerate(row):
            d.text((col_x[c] + 8, proc_top + r * 32 + 6), val, fill="black", font=fb)

    y = proc_top + 4 * 32 + 30
    d.text((40, y), "3. HISTORICO DE REVISOES", fill="black", font=fb)
    d.line((40, y + 20, 320, y + 20), fill="black", width=2)
    y += 35
    hist_top = y
    hcol_x = [40, 140, 280, 760]
    for x in hcol_x:
        d.line((x, hist_top, x, hist_top + 3 * 28), fill="black")
    for r in range(4):
        d.line((40, hist_top + r * 28, 760, hist_top + r * 28), fill="black")
    d.text((48, hist_top + 6), "Rev", fill="black", font=fb)
    d.text((148, hist_top + 6), "Data", fill="black", font=fb)
    d.text((288, hist_top + 6), "Alteracao", fill="black", font=fb)
    rev_rows = [
        ("01", "2026-04-10", "criacao do laudo"),
        ("02", "2026-04-18", "ajuste no objetivo"),
    ]
    for r, row in enumerate(rev_rows, start=1):
        for c, val in enumerate(row):
            d.text((hcol_x[c] + 8, hist_top + r * 28 + 6), val, fill="black", font=fb)

    y = hist_top + 3 * 28 + 40
    d.text((40, y), "4. ASSINATURA", fill="black", font=fb)
    d.line((40, y + 20, 200, y + 20), fill="black", width=2)
    y += 50
    d.text((40, y), f"Aprovado por: {data['RESPONSAVEL']}", fill="black", font=fb)
    d.line((180, y + 18, 600, y + 18), fill="black", width=2)

    img.save(path, "PNG")


# ===== Replication via regex puro =====


@dataclass
class ReplicationResult:
    extracted_data: dict[str, str]
    placeholders_filled: int
    placeholders_total: int


_FIELD_PATTERNS: dict[str, re.Pattern] = {
    "CODIGO": re.compile(r"Codigo do laudo:\s*([A-Z]+-\d{4}-\d{3})", re.I),
    "REVISAO": re.compile(r"Revisao corrente:\s*(\d{2})", re.I),
    "DATA": re.compile(r"Data de emissao:\s*(\d{4}-\d{2}-\d{2})", re.I),
    "RESPONSAVEL": re.compile(r"Engenheiro responsavel:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", re.I),
    "CLASSE": re.compile(r"Classe operacional:\s*([A-Z])\b", re.I),
    "OBJETIVO_TEXTO": re.compile(r"Sobre o objetivo:\s*\n([^\n]+)", re.I),
}


def replicate(template_phs: dict[str, str], source_text: str) -> ReplicationResult:
    extracted: dict[str, str] = {}
    for key, pattern in _FIELD_PATTERNS.items():
        m = pattern.search(source_text)
        if m:
            extracted[key] = m.group(1).strip()
    filled = sum(1 for k in template_phs if k in extracted)
    return ReplicationResult(
        extracted_data=extracted,
        placeholders_filled=filled,
        placeholders_total=len(template_phs),
    )


# ===== Main =====


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=None, help="Output dir (default: tempdir)")
    args = parser.parse_args()

    if args.out_dir:
        out_dir = args.out_dir.resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
    else:
        out_dir = Path(tempfile.mkdtemp(prefix="te-laudo-"))

    template_png = out_dir / "template.png"
    source_png = out_dir / "source.png"
    replica_png = out_dir / "replica.png"

    template_phs = make_template(template_png)
    source_data = make_source(source_png)
    make_replica(replica_png, source_data)

    ramp = "@#%*+=-:. "
    grid_t = image_to_ascii(template_png, cols=80, rows=60, ramp=ramp)
    grid_s = image_to_ascii(source_png, cols=80, rows=60, ramp=ramp)
    grid_r = image_to_ascii(replica_png, cols=80, rows=60, ramp=ramp)

    feat_t = detect_layout_features(grid_t, ramp=ramp)
    feat_s = detect_layout_features(grid_s, ramp=ramp)
    feat_r = detect_layout_features(grid_r, ramp=ramp)

    source_text = "\n".join(_SOURCE_LINES)
    rep = replicate(template_phs, source_text)

    print(f"PNGs em: {out_dir}\n")
    print("=" * 80)
    print("ESTRUTURA")
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
    for k, ph in template_phs.items():
        v = rep.extracted_data.get(k, "(NOT FOUND)")
        print(f"  {k:<18} | {ph:<24} -> {v}")
    print()
    print(f"Score: {rep.placeholders_filled}/{rep.placeholders_total} campos preenchidos")


if __name__ == "__main__":
    main()
