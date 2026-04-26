"""09 — POC: contrato 3 páginas (multi-page).

Template:
  Página 1: cabeçalho + cláusulas 1-3
  Página 2: tabela de partes contratantes + cláusulas 4-7
  Página 3: assinaturas + testemunhas + data

Source: 1 doc com dados de um contrato específico (texto livre).
Replica: 3 PNGs reproduzindo o template + dados extraídos.

Run:
    python examples/09_multipage_contract.py [--out-dir out/contrato]
"""

from __future__ import annotations

import argparse
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from engine.ascii_layout import (
    detect_layout_features_multipage,
    image_to_ascii,
    summarize_multipage,
)
from engine.pattern_inference import apply_inferred, infer_field_patterns


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _draw_header(d: ImageDraw.ImageDraw, page_num: int) -> None:
    """Cabeçalho repetido em todas páginas."""
    fh = _font(22)
    fs = _font(11)
    d.rectangle((40, 30, 760, 75), fill="black")
    d.text((50, 38), "CONTRATO DE PRESTACAO DE SERVICOS", fill="white", font=fh)
    d.text((650, 80), f"pag {page_num}/3", fill="black", font=fs)


def _draw_footer(d: ImageDraw.ImageDraw, w: int, h: int) -> None:
    """Rodapé repetido."""
    fs = _font(10)
    d.line((40, h - 50, w - 40, h - 50), fill="black")
    d.text((40, h - 40), "Confidencial - uso interno", fill="black", font=fs)


def make_template_p1(path: Path, w: int = 800, h: int = 1100) -> None:
    img = Image.new("RGB", (w, h), color="white")
    d = ImageDraw.Draw(img)
    fb = _font(14)
    _draw_header(d, 1)

    y = 110
    # Header fields
    d.text((40, y), "Contrato N°: [CONTRATO_N]", fill="black", font=fb)
    y += 22
    d.text((40, y), "Data: [DATA]", fill="black", font=fb)
    y += 22
    d.text((40, y), "Local: [LOCAL]", fill="black", font=fb)

    y += 50
    d.text((40, y), "CLAUSULA 1 - DAS PARTES", fill="black", font=fb)
    d.line((40, y + 18, 280, y + 18), fill="black", width=2)
    y += 30
    d.text((40, y), "Contratante: [CONTRATANTE]", fill="black", font=fb)
    y += 22
    d.text((40, y), "Contratada: [CONTRATADA]", fill="black", font=fb)

    y += 50
    d.text((40, y), "CLAUSULA 2 - DO OBJETO", fill="black", font=fb)
    d.line((40, y + 18, 280, y + 18), fill="black", width=2)
    y += 30
    d.text((40, y), "[OBJETO_DESCRICAO]", fill="black", font=fb)

    y += 80
    d.text((40, y), "CLAUSULA 3 - DO VALOR", fill="black", font=fb)
    d.line((40, y + 18, 270, y + 18), fill="black", width=2)
    y += 30
    d.text((40, y), "Valor total: R$ [VALOR]", fill="black", font=fb)

    _draw_footer(d, w, h)
    img.save(path, "PNG")


def make_template_p2(path: Path, w: int = 800, h: int = 1100) -> None:
    img = Image.new("RGB", (w, h), color="white")
    d = ImageDraw.Draw(img)
    fb = _font(14)
    _draw_header(d, 2)

    y = 110
    d.text((40, y), "TABELA DAS PARTES", fill="black", font=fb)
    d.line((40, y + 18, 220, y + 18), fill="black", width=2)
    y += 30

    table_top = y
    col_x = [40, 220, 480, 760]
    for x in col_x:
        d.line((x, table_top, x, table_top + 4 * 32), fill="black")
    for r in range(5):
        d.line((40, table_top + r * 32, 760, table_top + r * 32), fill="black")
    d.text((48, table_top + 6), "Tipo", fill="black", font=fb)
    d.text((228, table_top + 6), "Nome", fill="black", font=fb)
    d.text((488, table_top + 6), "CNPJ/CPF", fill="black", font=fb)
    for r in range(1, 4):
        d.text((48, table_top + r * 32 + 6), f"[TIPO_{r}]", fill="black", font=fb)
        d.text((228, table_top + r * 32 + 6), f"[NOME_{r}]", fill="black", font=fb)
        d.text((488, table_top + r * 32 + 6), f"[DOC_{r}]", fill="black", font=fb)

    y = table_top + 4 * 32 + 40
    d.text((40, y), "CLAUSULA 4 - DO PRAZO", fill="black", font=fb)
    d.line((40, y + 18, 270, y + 18), fill="black", width=2)
    y += 30
    d.text((40, y), "Vigencia: [VIGENCIA]", fill="black", font=fb)

    y += 50
    d.text((40, y), "CLAUSULA 5 - DA RESCISAO", fill="black", font=fb)
    d.line((40, y + 18, 320, y + 18), fill="black", width=2)
    y += 30
    d.text((40, y), "[RESCISAO_TEXTO]", fill="black", font=fb)

    y += 80
    d.text((40, y), "CLAUSULA 6 - DO FORO", fill="black", font=fb)
    d.line((40, y + 18, 260, y + 18), fill="black", width=2)
    y += 30
    d.text((40, y), "Foro eleito: [FORO]", fill="black", font=fb)

    _draw_footer(d, w, h)
    img.save(path, "PNG")


def make_template_p3(path: Path, w: int = 800, h: int = 1100) -> None:
    img = Image.new("RGB", (w, h), color="white")
    d = ImageDraw.Draw(img)
    fb = _font(14)
    _draw_header(d, 3)

    y = 200
    d.text((40, y), "Por estarem assim ajustadas as partes assinam abaixo:", fill="black", font=fb)
    y += 60

    d.text((40, y), "Contratante:", fill="black", font=fb)
    d.line((180, y + 18, 600, y + 18), fill="black", width=2)
    y += 60
    d.text((40, y), "Contratada:", fill="black", font=fb)
    d.line((180, y + 18, 600, y + 18), fill="black", width=2)
    y += 100

    d.text((40, y), "Testemunha 1:", fill="black", font=fb)
    d.line((180, y + 18, 600, y + 18), fill="black", width=2)
    y += 60
    d.text((40, y), "Testemunha 2:", fill="black", font=fb)
    d.line((180, y + 18, 600, y + 18), fill="black", width=2)
    y += 100

    d.text((40, y), "Local e data: [LOCAL_DATA]", fill="black", font=fb)

    _draw_footer(d, w, h)
    img.save(path, "PNG")


_SOURCE_LINES = [
    "Solicitacao de contrato - 26/04/2026",
    "",
    "Numero do contrato: CT-2026-0042",
    "Data de assinatura: 2026-04-26",
    "Local de assinatura: Recife-PE",
    "",
    "Partes envolvidas:",
    "Contratante: ACME Industria Ltda",
    "Contratada: TechServ Solucoes ME",
    "",
    "Objeto do contrato:",
    "Prestacao de servicos de auditoria tecnica em sistemas de gestao.",
    "",
    "Valor total: R$ 45.000,00",
    "Vigencia: 12 meses a partir da assinatura.",
    "",
    "Rescisao: ambas as partes podem rescindir com aviso previo de 30 dias.",
    "Foro eleito: comarca de Recife-PE.",
    "",
    "Partes detalhadas:",
    "  Contratante - ACME Industria Ltda - CNPJ 12.345.678/0001-90",
    "  Contratada - TechServ Solucoes ME - CNPJ 98.765.432/0001-01",
    "  Testemunha - Joao Silva - CPF 111.222.333-44",
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


def make_replica_p1(path: Path, data: dict[str, str], w: int = 800, h: int = 1100) -> None:
    img = Image.new("RGB", (w, h), color="white")
    d = ImageDraw.Draw(img)
    fb = _font(14)
    _draw_header(d, 1)

    y = 110
    d.text((40, y), f"Contrato N°: {data['CONTRATO_N']}", fill="black", font=fb)
    y += 22
    d.text((40, y), f"Data: {data['DATA']}", fill="black", font=fb)
    y += 22
    d.text((40, y), f"Local: {data['LOCAL']}", fill="black", font=fb)

    y += 50
    d.text((40, y), "CLAUSULA 1 - DAS PARTES", fill="black", font=fb)
    d.line((40, y + 18, 280, y + 18), fill="black", width=2)
    y += 30
    d.text((40, y), f"Contratante: {data['CONTRATANTE']}", fill="black", font=fb)
    y += 22
    d.text((40, y), f"Contratada: {data['CONTRATADA']}", fill="black", font=fb)

    y += 50
    d.text((40, y), "CLAUSULA 2 - DO OBJETO", fill="black", font=fb)
    d.line((40, y + 18, 280, y + 18), fill="black", width=2)
    y += 30
    d.text((40, y), data["OBJETO_DESCRICAO"], fill="black", font=fb)

    y += 80
    d.text((40, y), "CLAUSULA 3 - DO VALOR", fill="black", font=fb)
    d.line((40, y + 18, 270, y + 18), fill="black", width=2)
    y += 30
    d.text((40, y), f"Valor total: R$ {data['VALOR']}", fill="black", font=fb)

    _draw_footer(d, w, h)
    img.save(path, "PNG")


def make_replica_p2(path: Path, data: dict[str, str], w: int = 800, h: int = 1100) -> None:
    img = Image.new("RGB", (w, h), color="white")
    d = ImageDraw.Draw(img)
    fb = _font(14)
    _draw_header(d, 2)

    y = 110
    d.text((40, y), "TABELA DAS PARTES", fill="black", font=fb)
    d.line((40, y + 18, 220, y + 18), fill="black", width=2)
    y += 30

    table_top = y
    col_x = [40, 220, 480, 760]
    for x in col_x:
        d.line((x, table_top, x, table_top + 4 * 32), fill="black")
    for r in range(5):
        d.line((40, table_top + r * 32, 760, table_top + r * 32), fill="black")
    d.text((48, table_top + 6), "Tipo", fill="black", font=fb)
    d.text((228, table_top + 6), "Nome", fill="black", font=fb)
    d.text((488, table_top + 6), "CNPJ/CPF", fill="black", font=fb)
    rows = [
        ("Contratante", data["CONTRATANTE"], "12.345.678/0001-90"),
        ("Contratada", data["CONTRATADA"], "98.765.432/0001-01"),
        ("Testemunha", "Joao Silva", "111.222.333-44"),
    ]
    for r, row in enumerate(rows, start=1):
        for c, val in enumerate(row):
            d.text((col_x[c] + 8, table_top + r * 32 + 6), val[:25], fill="black", font=fb)

    y = table_top + 4 * 32 + 40
    d.text((40, y), "CLAUSULA 4 - DO PRAZO", fill="black", font=fb)
    d.line((40, y + 18, 270, y + 18), fill="black", width=2)
    y += 30
    d.text((40, y), f"Vigencia: {data['VIGENCIA']}", fill="black", font=fb)

    y += 50
    d.text((40, y), "CLAUSULA 5 - DA RESCISAO", fill="black", font=fb)
    d.line((40, y + 18, 320, y + 18), fill="black", width=2)
    y += 30
    d.text((40, y), data["RESCISAO_TEXTO"], fill="black", font=fb)

    y += 80
    d.text((40, y), "CLAUSULA 6 - DO FORO", fill="black", font=fb)
    d.line((40, y + 18, 260, y + 18), fill="black", width=2)
    y += 30
    d.text((40, y), f"Foro eleito: {data['FORO']}", fill="black", font=fb)

    _draw_footer(d, w, h)
    img.save(path, "PNG")


def make_replica_p3(path: Path, data: dict[str, str], w: int = 800, h: int = 1100) -> None:
    img = Image.new("RGB", (w, h), color="white")
    d = ImageDraw.Draw(img)
    fb = _font(14)
    _draw_header(d, 3)

    y = 200
    d.text((40, y), "Por estarem assim ajustadas as partes assinam abaixo:", fill="black", font=fb)
    y += 60

    d.text((40, y), f"Contratante: {data['CONTRATANTE']}", fill="black", font=fb)
    d.line((400, y + 18, 600, y + 18), fill="black", width=2)
    y += 60
    d.text((40, y), f"Contratada: {data['CONTRATADA']}", fill="black", font=fb)
    d.line((400, y + 18, 600, y + 18), fill="black", width=2)
    y += 100

    d.text((40, y), "Testemunha 1: Joao Silva", fill="black", font=fb)
    d.line((400, y + 18, 600, y + 18), fill="black", width=2)
    y += 60
    d.text((40, y), "Testemunha 2: Maria Souza", fill="black", font=fb)
    d.line((400, y + 18, 600, y + 18), fill="black", width=2)
    y += 100

    d.text((40, y), f"Local e data: {data['LOCAL']} - {data['DATA']}", fill="black", font=fb)

    _draw_footer(d, w, h)
    img.save(path, "PNG")


@dataclass
class ReplicationResult:
    extracted_data: dict[str, str]
    fields_filled: int
    fields_total: int


# Gold variants pra inferencia
_GOLD_DOCS = [
    "\n".join(_SOURCE_LINES),
    """Solicitacao de contrato - 12/02/2026

Numero do contrato: CT-2026-0019
Data de assinatura: 2026-02-12
Local de assinatura: Sao-Paulo

Partes envolvidas:
Contratante: Globex Comercio Ltda
Contratada: Initech Servicos ME

Objeto do contrato:
Desenvolvimento de plataforma web sob demanda.

Valor total: R$ 120.000,00
Vigencia: 18 meses a partir da assinatura.

Rescisao: rescisao mediante notificacao 60 dias antes.
Foro eleito: comarca de Sao-Paulo.
""",
    """Solicitacao de contrato - 05/06/2026

Numero do contrato: CT-2026-0078
Data de assinatura: 2026-06-05
Local de assinatura: Belo-Horizonte

Partes envolvidas:
Contratante: Hooli Industrias Ltda
Contratada: Pied Piper ME

Objeto do contrato:
Consultoria em otimizacao de processos industriais.

Valor total: R$ 78.500,00
Vigencia: 6 meses renovaveis.

Rescisao: rescindivel a qualquer momento por escrito.
Foro eleito: comarca de Belo-Horizonte.
""",
]

_FIELD_EXAMPLES = {
    "CONTRATO_N": ["CT-2026-0042", "CT-2026-0019", "CT-2026-0078"],
    "DATA": ["2026-04-26", "2026-02-12", "2026-06-05"],
    "LOCAL": ["Recife-PE", "Sao-Paulo", "Belo-Horizonte"],
    "CONTRATANTE": ["ACME Industria Ltda", "Globex Comercio Ltda", "Hooli Industrias Ltda"],
    "CONTRATADA": ["TechServ Solucoes ME", "Initech Servicos ME", "Pied Piper ME"],
    "OBJETO_DESCRICAO": [
        "Prestacao de servicos de auditoria tecnica em sistemas de gestao.",
        "Desenvolvimento de plataforma web sob demanda.",
        "Consultoria em otimizacao de processos industriais.",
    ],
    "VALOR": ["45.000,00", "120.000,00", "78.500,00"],
    "VIGENCIA": [
        "12 meses a partir da assinatura",
        "18 meses a partir da assinatura",
        "6 meses renovaveis",
    ],
    "RESCISAO_TEXTO": [
        "ambas as partes podem rescindir com aviso previo de 30 dias.",
        "rescisao mediante notificacao 60 dias antes.",
        "rescindivel a qualquer momento por escrito.",
    ],
    "FORO": ["Recife-PE", "Sao-Paulo", "Belo-Horizonte"],
}

_INFERRED = infer_field_patterns(gold_docs=_GOLD_DOCS, field_examples=_FIELD_EXAMPLES)
_TOTAL_FIELDS = list(_FIELD_EXAMPLES.keys())


def replicate(source_text: str) -> ReplicationResult:
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
        out_dir = Path(tempfile.mkdtemp(prefix="te-contrato-"))

    template_pages = [out_dir / f"template-p{i}.png" for i in (1, 2, 3)]
    replica_pages = [out_dir / f"replica-p{i}.png" for i in (1, 2, 3)]
    source_png = out_dir / "source.png"

    make_template_p1(template_pages[0])
    make_template_p2(template_pages[1])
    make_template_p3(template_pages[2])
    make_source(source_png)

    src_text = "\n".join(_SOURCE_LINES)
    rep = replicate(src_text)
    data = rep.extracted_data
    # Fill defaults for missing fields (so replica draws ok)
    defaults = {
        "CONTRATO_N": "?",
        "DATA": "?",
        "LOCAL": "?",
        "CONTRATANTE": "?",
        "CONTRATADA": "?",
        "OBJETO_DESCRICAO": "?",
        "VALOR": "?",
        "VIGENCIA": "?",
        "RESCISAO_TEXTO": "?",
        "FORO": "?",
    }
    full = {**defaults, **data}

    make_replica_p1(replica_pages[0], full)
    make_replica_p2(replica_pages[1], full)
    make_replica_p3(replica_pages[2], full)

    ramp = "@#%*+=-:. "
    grids_t = [image_to_ascii(p, cols=80, rows=60, ramp=ramp) for p in template_pages]
    grids_r = [image_to_ascii(p, cols=80, rows=60, ramp=ramp) for p in replica_pages]
    multi_t = detect_layout_features_multipage(grids_t, ramp=ramp)
    multi_r = detect_layout_features_multipage(grids_r, ramp=ramp)

    print(f"PNGs em: {out_dir}\n")

    print("=" * 80)
    print("ESTRUTURA TEMPLATE (3 paginas)")
    print("=" * 80)
    print(summarize_multipage(multi_t))
    print()

    print("=" * 80)
    print("ESTRUTURA REPLICA (3 paginas)")
    print("=" * 80)
    print(summarize_multipage(multi_r))
    print()

    print("=" * 80)
    print("CAMPOS REPLICADOS (regex puro, ZERO LLM)")
    print("=" * 80)
    for k in _TOTAL_FIELDS:
        v = data.get(k, "(NOT FOUND)")
        ok = "OK" if k in data else "MISS"
        print(f"  [{ok:<4}] {k:<20} -> {v}")
    print()
    print(f"Score: {rep.fields_filled}/{rep.fields_total} campos preenchidos")

    print()
    print("=" * 80)
    print("VEREDITO")
    print("=" * 80)
    structure_ok = (
        multi_t.total_headings == multi_r.total_headings and multi_t.total_tables == multi_r.total_tables
    )
    print(f"Estrutura preservada (T == R):  {'PASS' if structure_ok else 'FAIL'}")
    print(f"  template H={multi_t.total_headings} T={multi_t.total_tables}")
    print(f"  replica  H={multi_r.total_headings} T={multi_r.total_tables}")
    print(f"Replicacao de campos:            {rep.fields_filled}/{rep.fields_total}")


if __name__ == "__main__":
    main()
