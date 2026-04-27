"""Contrato bilateral simples (Wave H).

Formato generico de contrato bilateral entre pessoa juridica contratante e
pessoa juridica contratada. Cobre objeto + valor + vigencia + foro.

Nao e um formato regulado especifico (cada area tem suas particularidades —
trabalhista CLT, locacao Lei 8.245, prestacao de servicos CC art 593+, etc).
Use como base; estenda os schemas pra clausulas especificas.

Campos esperados:

- TITULO_CONTRATO
- CONTRATANTE, CNPJ_CONTRATANTE
- CONTRATADA, CNPJ_CONTRATADA
- OBJETO, VALOR, VIGENCIA
- FORO, DATA_ASSINATURA
"""

from __future__ import annotations

from engine.formats._base import Format
from engine.schema_inference import FieldSchema

_SCHEMAS: list[FieldSchema] = [
    FieldSchema(
        "TITULO_CONTRATO",
        "{{TITULO_CONTRATO}}",
        "mustache",
        field_type="freetext",
        required=True,
    ),
    FieldSchema("CONTRATANTE", "{{CONTRATANTE}}", "mustache", field_type="freetext", required=True),
    FieldSchema(
        "CNPJ_CONTRATANTE",
        "{{CNPJ_CONTRATANTE}}",
        "mustache",
        field_type="freetext",
        format_hint="00.000.000/0000-00",
        required=True,
    ),
    FieldSchema("CONTRATADA", "{{CONTRATADA}}", "mustache", field_type="freetext", required=True),
    FieldSchema(
        "CNPJ_CONTRATADA",
        "{{CNPJ_CONTRATADA}}",
        "mustache",
        field_type="freetext",
        format_hint="00.000.000/0000-00",
        required=True,
    ),
    FieldSchema("OBJETO", "{{OBJETO}}", "mustache", field_type="freetext", required=True),
    FieldSchema(
        "VALOR",
        "{{VALOR}}",
        "mustache",
        field_type="decimal_br",
        format_hint="R$ 0.000,00",
        required=True,
    ),
    FieldSchema("VIGENCIA", "{{VIGENCIA}}", "mustache", field_type="freetext", required=True),
    FieldSchema("FORO", "{{FORO}}", "mustache", field_type="freetext", required=True),
    FieldSchema(
        "DATA_ASSINATURA",
        "{{DATA_ASSINATURA}}",
        "mustache",
        field_type="iso_date",
        required=True,
    ),
]

_FIELD_EXAMPLES: dict[str, list[str]] = {
    "TITULO_CONTRATO": [
        "Contrato de prestacao de servicos de auditoria tecnica",
        "Contrato de fornecimento de equipamentos industriais",
        "Contrato de licenca de software corporativo",
    ],
    "CONTRATANTE": [
        "ACME Industria Ltda",
        "Globex Manufatura S/A",
        "Hooli Tecnologia ME",
    ],
    "CNPJ_CONTRATANTE": [
        "12.345.678/0001-99",
        "98.765.432/0001-11",
        "11.222.333/0001-44",
    ],
    "CONTRATADA": [
        "TechServ Solucoes ME",
        "ConsultPro Engenharia Ltda",
        "DevHouse Software S/A",
    ],
    "CNPJ_CONTRATADA": [
        "55.666.777/0001-88",
        "44.555.666/0001-77",
        "33.444.555/0001-66",
    ],
    "OBJETO": [
        "Prestacao de servicos de auditoria tecnica em sistemas de gestao da contratante.",
        "Fornecimento, instalacao e comissionamento de equipamentos industriais conforme escopo anexo.",
        "Licenca de uso de software corporativo de gestao financeira para 100 usuarios.",
    ],
    "VALOR": ["45.000,00", "250.000,00", "12.500,00"],
    "VIGENCIA": [
        "12 meses a partir da assinatura, prorrogaveis por igual periodo.",
        "24 meses a partir da assinatura, sem prorrogacao automatica.",
        "36 meses a partir da assinatura, com renovacao mediante aditivo.",
    ],
    "FORO": [
        "Recife - PE",
        "Sao Paulo - SP",
        "Rio de Janeiro - RJ",
    ],
    "DATA_ASSINATURA": ["2026-01-15", "2026-04-26", "2026-07-30"],
}


def _gold(i: int) -> str:
    e = {k: v[i] for k, v in _FIELD_EXAMPLES.items()}
    return f"""Titulo contrato: {e["TITULO_CONTRATO"]}

Contratante: {e["CONTRATANTE"]}
CNPJ contratante: {e["CNPJ_CONTRATANTE"]}

Contratada: {e["CONTRATADA"]}
CNPJ contratada: {e["CNPJ_CONTRATADA"]}

Objeto: {e["OBJETO"]}

Valor: {e["VALOR"]}

Vigencia: {e["VIGENCIA"]}

Foro: {e["FORO"]}

Data assinatura: {e["DATA_ASSINATURA"]}

E por estarem assim justas e contratadas, as partes assinam o presente em 2 vias de igual teor.
"""


_GOLD_DOCS: list[str] = [_gold(0), _gold(1), _gold(2)]


FORMAT = Format(
    name="contrato_simples",
    title="Contrato bilateral simples",
    description=(
        "Formato generico de contrato bilateral entre pessoas juridicas. "
        "Cobre objeto, valor, vigencia, rescisao e foro. Use como base; "
        "estenda os schemas para clausulas especificas da sua area."
    ),
    spec="generico",
    schemas=_SCHEMAS,
    field_examples=_FIELD_EXAMPLES,
    gold_docs=_GOLD_DOCS,
    conformity_weights={
        "text": 0.30,
        "structural": 0.20,
        "visual": 0.05,
        "design": 0.05,
        "technical": 0.40,
    },
    required_headings=["OBJETO", "VALOR", "VIGENCIA", "FORO"],
    recommended_threshold=0.85,
)
