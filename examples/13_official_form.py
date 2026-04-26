"""13 — POC: formulario oficial (grid rigido, checkboxes, campos compactos).

Stress-test em design tipo Receita Federal / formularios governamentais:
- Grid rigido com bordas espessas
- Multiplos campos pequenos lado a lado
- Checkboxes / toggles
- Codigo de barras simulado
- Cabecalho com brasao + numero do formulario

Run:
    python examples/13_official_form.py [--out-dir out/form]
"""

from __future__ import annotations

import argparse
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from engine.ascii_layout import detect_layout_features, image_to_ascii
from engine.pattern_inference import apply_inferred, infer_field_patterns


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _checkbox(d: ImageDraw.ImageDraw, x: int, y: int, checked: bool = False) -> None:
    d.rectangle((x, y, x + 14, y + 14), outline="black", width=1)
    if checked:
        d.line((x + 2, y + 7, x + 6, y + 11), fill="black", width=2)
        d.line((x + 6, y + 11, x + 12, y + 3), fill="black", width=2)


def make_template(path: Path, w: int = 800, h: int = 1100) -> dict[str, str]:
    img = Image.new("RGB", (w, h), color="white")
    d = ImageDraw.Draw(img)
    f_big = _font(20)
    f_body = _font(13)
    f_small = _font(10)

    # Top brasao box
    d.rectangle((40, 40, 130, 130), outline="black", width=2)
    d.text((55, 75), "BRASAO", fill="black", font=f_small)

    # Form title + numero
    d.text((150, 60), "FORMULARIO OFICIAL", fill="black", font=f_big)
    d.text((150, 95), "FORM N: [FORM_N]", fill="black", font=f_body)
    d.text((150, 115), "PROTOCOLO: [PROTOCOLO]", fill="black", font=f_body)

    # Pseudo barcode
    barcode_x = 600
    for i, w_bar in enumerate([2, 1, 3, 1, 2, 4, 1, 2, 3, 2, 1, 3]):
        d.rectangle((barcode_x + i * 8, 50, barcode_x + i * 8 + w_bar, 100), fill="black")

    # Section 1 - Identificacao
    y = 170
    d.rectangle((40, y, 760, y + 30), outline="black", width=2)
    d.text((50, y + 8), "1. IDENTIFICACAO DO REQUERENTE", fill="black", font=f_body)
    y += 30

    # Linha 1: Nome (full width) + checkbox tipo
    d.rectangle((40, y, 600, y + 35), outline="black")
    d.text((48, y + 4), "NOME COMPLETO", fill="black", font=f_small)
    d.text((48, y + 18), "[NOME]", fill="black", font=f_body)

    d.rectangle((600, y, 760, y + 35), outline="black")
    d.text((608, y + 4), "TIPO", fill="black", font=f_small)
    _checkbox(d, 608, y + 18)
    d.text((628, y + 18), "[TIPO_PF]", fill="black", font=f_small)
    _checkbox(d, 690, y + 18)
    d.text((710, y + 18), "[TIPO_PJ]", fill="black", font=f_small)
    y += 35

    # Linha 2: CPF + RG + Data nascimento
    d.rectangle((40, y, 280, y + 35), outline="black")
    d.text((48, y + 4), "CPF", fill="black", font=f_small)
    d.text((48, y + 18), "[CPF]", fill="black", font=f_body)

    d.rectangle((280, y, 520, y + 35), outline="black")
    d.text((288, y + 4), "RG", fill="black", font=f_small)
    d.text((288, y + 18), "[RG]", fill="black", font=f_body)

    d.rectangle((520, y, 760, y + 35), outline="black")
    d.text((528, y + 4), "DATA NASCIMENTO", fill="black", font=f_small)
    d.text((528, y + 18), "[DATA_NASC]", fill="black", font=f_body)
    y += 35

    # Section 2 - Endereco
    y += 20
    d.rectangle((40, y, 760, y + 30), outline="black", width=2)
    d.text((50, y + 8), "2. ENDERECO", fill="black", font=f_body)
    y += 30

    d.rectangle((40, y, 600, y + 35), outline="black")
    d.text((48, y + 4), "RUA", fill="black", font=f_small)
    d.text((48, y + 18), "[RUA]", fill="black", font=f_body)

    d.rectangle((600, y, 760, y + 35), outline="black")
    d.text((608, y + 4), "NUMERO", fill="black", font=f_small)
    d.text((608, y + 18), "[NUMERO_END]", fill="black", font=f_body)
    y += 35

    d.rectangle((40, y, 400, y + 35), outline="black")
    d.text((48, y + 4), "CIDADE", fill="black", font=f_small)
    d.text((48, y + 18), "[CIDADE]", fill="black", font=f_body)

    d.rectangle((400, y, 500, y + 35), outline="black")
    d.text((408, y + 4), "UF", fill="black", font=f_small)
    d.text((408, y + 18), "[UF]", fill="black", font=f_body)

    d.rectangle((500, y, 760, y + 35), outline="black")
    d.text((508, y + 4), "CEP", fill="black", font=f_small)
    d.text((508, y + 18), "[CEP]", fill="black", font=f_body)

    # Section 3 - Declaracao
    y += 60
    d.rectangle((40, y, 760, y + 30), outline="black", width=2)
    d.text((50, y + 8), "3. DECLARACAO", fill="black", font=f_body)
    y += 35

    _checkbox(d, 48, y)
    d.text((68, y), "Declaro que as informacoes acima sao verdadeiras", fill="black", font=f_body)

    # Footer
    y = h - 120
    d.line((40, y, 350, y), fill="black", width=1)
    d.text((40, y + 8), "Assinatura do requerente", fill="black", font=f_small)
    d.text((40, y + 25), "Data: [DATA_ASSINATURA]", fill="black", font=f_body)

    img.save(path, "PNG")
    return {
        "FORM_N": "[FORM_N]",
        "PROTOCOLO": "[PROTOCOLO]",
        "NOME": "[NOME]",
        "CPF": "[CPF]",
        "RG": "[RG]",
        "DATA_NASC": "[DATA_NASC]",
        "RUA": "[RUA]",
        "NUMERO_END": "[NUMERO_END]",
        "CIDADE": "[CIDADE]",
        "UF": "[UF]",
        "CEP": "[CEP]",
        "DATA_ASSINATURA": "[DATA_ASSINATURA]",
    }


_SOURCE_LINES = [
    "Cadastro recebido - 2026-04-26",
    "",
    "Formulario numero: F-2026-0042",
    "Protocolo unico: PROT-99887766",
    "",
    "Dados pessoais:",
    "Nome completo: Joao da Silva Santos",
    "CPF: 123.456.789-00",
    "RG: 12.345.678-9",
    "Data de nascimento: 1985-03-15",
    "",
    "Endereco residencial:",
    "Rua: Avenida Boa Viagem",
    "Numero: 1234",
    "Cidade: Recife",
    "UF: PE",
    "CEP: 51011-000",
    "",
    "Data da assinatura: 2026-04-26",
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
    f_big = _font(20)
    f_body = _font(13)
    f_small = _font(10)

    d.rectangle((40, 40, 130, 130), outline="black", width=2)
    d.text((55, 75), "BRASAO", fill="black", font=f_small)
    d.text((150, 60), "FORMULARIO OFICIAL", fill="black", font=f_big)
    d.text((150, 95), f"FORM N: {data['FORM_N']}", fill="black", font=f_body)
    d.text((150, 115), f"PROTOCOLO: {data['PROTOCOLO']}", fill="black", font=f_body)

    barcode_x = 600
    for i, w_bar in enumerate([2, 1, 3, 1, 2, 4, 1, 2, 3, 2, 1, 3]):
        d.rectangle((barcode_x + i * 8, 50, barcode_x + i * 8 + w_bar, 100), fill="black")

    y = 170
    d.rectangle((40, y, 760, y + 30), outline="black", width=2)
    d.text((50, y + 8), "1. IDENTIFICACAO DO REQUERENTE", fill="black", font=f_body)
    y += 30

    d.rectangle((40, y, 600, y + 35), outline="black")
    d.text((48, y + 4), "NOME COMPLETO", fill="black", font=f_small)
    d.text((48, y + 18), data["NOME"], fill="black", font=f_body)
    d.rectangle((600, y, 760, y + 35), outline="black")
    d.text((608, y + 4), "TIPO", fill="black", font=f_small)
    _checkbox(d, 608, y + 18, checked=True)
    d.text((628, y + 18), "PF", fill="black", font=f_small)
    _checkbox(d, 690, y + 18)
    d.text((710, y + 18), "PJ", fill="black", font=f_small)
    y += 35

    d.rectangle((40, y, 280, y + 35), outline="black")
    d.text((48, y + 4), "CPF", fill="black", font=f_small)
    d.text((48, y + 18), data["CPF"], fill="black", font=f_body)
    d.rectangle((280, y, 520, y + 35), outline="black")
    d.text((288, y + 4), "RG", fill="black", font=f_small)
    d.text((288, y + 18), data["RG"], fill="black", font=f_body)
    d.rectangle((520, y, 760, y + 35), outline="black")
    d.text((528, y + 4), "DATA NASCIMENTO", fill="black", font=f_small)
    d.text((528, y + 18), data["DATA_NASC"], fill="black", font=f_body)
    y += 55

    d.rectangle((40, y, 760, y + 30), outline="black", width=2)
    d.text((50, y + 8), "2. ENDERECO", fill="black", font=f_body)
    y += 30

    d.rectangle((40, y, 600, y + 35), outline="black")
    d.text((48, y + 4), "RUA", fill="black", font=f_small)
    d.text((48, y + 18), data["RUA"], fill="black", font=f_body)
    d.rectangle((600, y, 760, y + 35), outline="black")
    d.text((608, y + 4), "NUMERO", fill="black", font=f_small)
    d.text((608, y + 18), data["NUMERO_END"], fill="black", font=f_body)
    y += 35

    d.rectangle((40, y, 400, y + 35), outline="black")
    d.text((48, y + 4), "CIDADE", fill="black", font=f_small)
    d.text((48, y + 18), data["CIDADE"], fill="black", font=f_body)
    d.rectangle((400, y, 500, y + 35), outline="black")
    d.text((408, y + 4), "UF", fill="black", font=f_small)
    d.text((408, y + 18), data["UF"], fill="black", font=f_body)
    d.rectangle((500, y, 760, y + 35), outline="black")
    d.text((508, y + 4), "CEP", fill="black", font=f_small)
    d.text((508, y + 18), data["CEP"], fill="black", font=f_body)
    y += 60

    d.rectangle((40, y, 760, y + 30), outline="black", width=2)
    d.text((50, y + 8), "3. DECLARACAO", fill="black", font=f_body)
    y += 35
    _checkbox(d, 48, y, checked=True)
    d.text((68, y), "Declaro que as informacoes acima sao verdadeiras", fill="black", font=f_body)

    y = h - 120
    d.line((40, y, 350, y), fill="black", width=1)
    d.text((40, y + 8), "Assinatura do requerente", fill="black", font=f_small)
    d.text((40, y + 25), f"Data: {data['DATA_ASSINATURA']}", fill="black", font=f_body)

    img.save(path, "PNG")


@dataclass
class ReplicationResult:
    extracted_data: dict[str, str]
    fields_filled: int
    fields_total: int


_GOLD_DOCS = [
    "\n".join(_SOURCE_LINES),
    """Cadastro recebido - 2026-01-10

Formulario numero: F-2026-0007
Protocolo unico: PROT-12345678

Dados pessoais:
Nome completo: Maria de Fatima Lima
CPF: 987.654.321-00
RG: 98.765.432-1
Data de nascimento: 1990-07-22

Endereco residencial:
Rua: Rua das Flores
Numero: 567
Cidade: Curitiba
UF: PR
CEP: 80010-000

Data da assinatura: 2026-01-10
""",
    """Cadastro recebido - 2026-09-15

Formulario numero: F-2026-0150
Protocolo unico: PROT-55667788

Dados pessoais:
Nome completo: Carlos Eduardo Santos
CPF: 555.444.333-22
RG: 33.222.111-0
Data de nascimento: 1978-11-03

Endereco residencial:
Rua: Avenida Paulista
Numero: 2001
Cidade: Sao
UF: SP
CEP: 01310-200

Data da assinatura: 2026-09-15
""",
]

_FIELD_EXAMPLES = {
    "FORM_N": ["F-2026-0042", "F-2026-0007", "F-2026-0150"],
    "PROTOCOLO": ["PROT-99887766", "PROT-12345678", "PROT-55667788"],
    "NOME": ["Joao da Silva Santos", "Maria de Fatima Lima", "Carlos Eduardo Santos"],
    "CPF": ["123.456.789-00", "987.654.321-00", "555.444.333-22"],
    "RG": ["12.345.678-9", "98.765.432-1", "33.222.111-0"],
    "DATA_NASC": ["1985-03-15", "1990-07-22", "1978-11-03"],
    "RUA": ["Avenida Boa Viagem", "Rua das Flores", "Avenida Paulista"],
    "NUMERO_END": ["1234", "567", "2001"],
    "CIDADE": ["Recife", "Curitiba", "Sao"],
    "UF": ["PE", "PR", "SP"],
    "CEP": ["51011-000", "80010-000", "01310-200"],
    "DATA_ASSINATURA": ["2026-04-26", "2026-01-10", "2026-09-15"],
}

_INFERRED = infer_field_patterns(gold_docs=_GOLD_DOCS, field_examples=_FIELD_EXAMPLES)


def replicate(template_phs: dict[str, str], source_text: str) -> ReplicationResult:
    extracted = apply_inferred(_INFERRED, source_text)
    return ReplicationResult(extracted, len(extracted), len(_FIELD_EXAMPLES))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()

    out_dir = args.out_dir.resolve() if args.out_dir else Path(tempfile.mkdtemp(prefix="te-form-"))
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
    print("ESTRUTURA - FORMULARIO OFICIAL (grid rigido + checkboxes + barcode)")
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
        print(f"  {k:<18} -> {v}")


if __name__ == "__main__":
    main()
