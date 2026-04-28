"""Procuracao simples - formato generico.

Documento por instrumento particular, geralmente exigindo reconhecimento de
firma. Use como base; estenda os schemas pra clausulas especificas (poderes
especificos, prazo, sub-estabelecimento, etc).
"""

from __future__ import annotations

from engine.formats._base import Format
from engine.schema_inference import FieldSchema

_SCHEMAS: list[FieldSchema] = [
    FieldSchema("OUTORGANTE", "{{OUTORGANTE}}", "mustache", field_type="fullname", required=True),
    FieldSchema(
        "CPF_OUTORGANTE",
        "{{CPF_OUTORGANTE}}",
        "mustache",
        field_type="cpf",
        required=True,
    ),
    FieldSchema("RG_OUTORGANTE", "{{RG_OUTORGANTE}}", "mustache", field_type="freetext", required=True),
    FieldSchema(
        "ENDERECO_OUTORGANTE",
        "{{ENDERECO_OUTORGANTE}}",
        "mustache",
        field_type="freetext",
        required=True,
    ),
    FieldSchema("OUTORGADO", "{{OUTORGADO}}", "mustache", field_type="fullname", required=True),
    FieldSchema(
        "CPF_OUTORGADO",
        "{{CPF_OUTORGADO}}",
        "mustache",
        field_type="cpf",
        required=True,
    ),
    FieldSchema("PODERES", "{{PODERES}}", "mustache", field_type="freetext", required=True),
    FieldSchema("PRAZO", "{{PRAZO}}", "mustache", field_type="freetext", required=True),
    FieldSchema("LOCAL", "{{LOCAL}}", "mustache", field_type="freetext", required=True),
    FieldSchema("DATA", "{{DATA}}", "mustache", field_type="iso_date", required=True),
]

_FIELD_EXAMPLES: dict[str, list[str]] = {
    "OUTORGANTE": [
        "Joao da Silva Santos",
        "Maria Carolina Souza Lima",
        "Pedro Henrique Oliveira",
    ],
    "CPF_OUTORGANTE": [
        "529.982.247-25",
        "111.444.777-35",
        "390.533.447-05",
    ],
    "RG_OUTORGANTE": [
        "1.234.567 SSP-PE",
        "98.765.432-1 SSP-SP",
        "11.222.333-4 SSP-RJ",
    ],
    "ENDERECO_OUTORGANTE": [
        "Rua das Flores, 100, Recife - PE, 50000-000",
        "Av Paulista, 2000, Sao Paulo - SP, 01310-100",
        "Av Atlantica, 500, Rio de Janeiro - RJ, 22021-001",
    ],
    "OUTORGADO": [
        "Carlos Mendes",
        "Ana Beatriz Costa",
        "Bruno Henrique Almeida",
    ],
    "CPF_OUTORGADO": [
        "123.456.789-09",
        "987.654.321-00",
        "111.222.333-96",
    ],
    "PODERES": [
        "representar o Outorgante perante orgaos publicos federais e estaduais.",
        "movimentar contas bancarias do Outorgante na instituicao X.",
        "assinar contratos de prestacao de servicos em nome do Outorgante.",
    ],
    "PRAZO": [
        "12 meses a partir desta data",
        "ate 31 de dezembro de 2026",
        "por prazo indeterminado, ate revogacao expressa",
    ],
    "LOCAL": ["Recife - PE", "Sao Paulo - SP", "Rio de Janeiro - RJ"],
    "DATA": ["2026-01-15", "2026-04-26", "2026-07-30"],
}


def _gold(i: int) -> str:
    e = {k: v[i] for k, v in _FIELD_EXAMPLES.items()}
    return f"""PROCURACAO

Outorgante: {e["OUTORGANTE"]}
CPF outorgante: {e["CPF_OUTORGANTE"]}
RG outorgante: {e["RG_OUTORGANTE"]}
Endereco outorgante: {e["ENDERECO_OUTORGANTE"]}

Outorgado: {e["OUTORGADO"]}
CPF outorgado: {e["CPF_OUTORGADO"]}

Poderes: {e["PODERES"]}

Prazo: {e["PRAZO"]}

Local: {e["LOCAL"]}
Data: {e["DATA"]}

Pelo presente instrumento particular, o Outorgante constitui o Outorgado seu bastante procurador.

____________________________
{e["OUTORGANTE"]}
"""


_GOLD_DOCS: list[str] = [_gold(0), _gold(1), _gold(2)]


FORMAT = Format(
    name="procuracao_simples",
    title="Procuracao simples - instrumento particular",
    description=(
        "Procuracao por instrumento particular generico. CPF do outorgante e "
        "outorgado validados (digito verificador). Estenda os poderes para "
        "casos especificos (bancario, judicial, etc)."
    ),
    spec="generico",
    schemas=_SCHEMAS,
    field_examples=_FIELD_EXAMPLES,
    gold_docs=_GOLD_DOCS,
    conformity_weights={
        "text": 0.25,
        "structural": 0.15,
        "visual": 0.05,
        "design": 0.05,
        "technical": 0.50,
    },
    required_headings=["PODERES", "PRAZO"],
    recommended_threshold=0.90,
)
