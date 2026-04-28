"""NR-13 - Laudo de inspecao em caldeiras e vasos de pressao.

Spec: Norma Regulamentadora 13 (Portaria MTE) - Caldeiras, vasos de pressao,
tubulacoes e tanques metalicos de armazenamento.
"""

from __future__ import annotations

from engine.formats._base import Format
from engine.schema_inference import FieldSchema

_SCHEMAS: list[FieldSchema] = [
    FieldSchema("EMPRESA", "{{EMPRESA}}", "mustache", field_type="freetext", required=True),
    FieldSchema(
        "CNPJ_EMPRESA",
        "{{CNPJ_EMPRESA}}",
        "mustache",
        field_type="freetext",
        format_hint="00.000.000/0000-00",
        required=True,
    ),
    FieldSchema(
        "CATEGORIA",
        "{{CATEGORIA}}",
        "mustache",
        field_type="freetext",
        format_hint="A | B | C | D",
        required=True,
    ),
    FieldSchema("CALDEIRA_TAG", "{{CALDEIRA_TAG}}", "mustache", field_type="doc_code", required=True),
    FieldSchema("PRESSAO_OPERACAO", "{{PRESSAO_OPERACAO}}", "mustache", field_type="freetext", required=True),
    FieldSchema("PMTA", "{{PMTA}}", "mustache", field_type="freetext", required=True),
    FieldSchema("DATA_INSPECAO", "{{DATA_INSPECAO}}", "mustache", field_type="iso_date", required=True),
    FieldSchema("PROXIMA_INSPECAO", "{{PROXIMA_INSPECAO}}", "mustache", field_type="iso_date", required=True),
    FieldSchema("RESPONSAVEL", "{{RESPONSAVEL}}", "mustache", field_type="fullname", required=True),
    FieldSchema("CREA", "{{CREA}}", "mustache", field_type="doc_code", required=True),
    FieldSchema("CONCLUSAO", "{{CONCLUSAO}}", "mustache", field_type="freetext", required=True),
]

_FIELD_EXAMPLES: dict[str, list[str]] = {
    "EMPRESA": [
        "ACME Industria Ltda",
        "Globex Manufatura S/A",
        "Hooli Equipamentos ME",
    ],
    "CNPJ_EMPRESA": [
        "12.345.678/0001-99",
        "98.765.432/0001-11",
        "11.222.333/0001-44",
    ],
    "CATEGORIA": ["A", "B", "C"],
    "CALDEIRA_TAG": ["CALD-001", "VP-042", "TQ-099"],
    "PRESSAO_OPERACAO": ["10 kgf/cm2", "15 kgf/cm2", "8 kgf/cm2"],
    "PMTA": ["12 kgf/cm2", "18 kgf/cm2", "10 kgf/cm2"],
    "DATA_INSPECAO": ["2026-01-15", "2026-04-26", "2026-07-30"],
    "PROXIMA_INSPECAO": ["2027-01-15", "2027-04-26", "2027-07-30"],
    "RESPONSAVEL": [
        "Joao da Silva",
        "Maria Carolina Souza",
        "Pedro Henrique Lima",
    ],
    "CREA": ["CREA-PE 123456", "CREA-SP 987654", "CREA-RJ 445566"],
    "CONCLUSAO": [
        "Caldeira em conformidade com NR-13. Apta para operacao por 12 meses.",
        "Vaso de pressao apresenta nao-conformidades. Recomenda-se reparo em 30 dias.",
        "Tanque em conformidade. Proxima inspecao externa em 12 meses.",
    ],
}


def _gold(i: int) -> str:
    e = {k: v[i] for k, v in _FIELD_EXAMPLES.items()}
    return f"""LAUDO DE INSPECAO - NR-13

1 IDENTIFICACAO

Empresa: {e["EMPRESA"]}
CNPJ: {e["CNPJ_EMPRESA"]}

2 EQUIPAMENTO

Categoria: {e["CATEGORIA"]}
Tag: {e["CALDEIRA_TAG"]}
Pressao de operacao: {e["PRESSAO_OPERACAO"]}
PMTA: {e["PMTA"]}

3 INSPECAO

Data: {e["DATA_INSPECAO"]}
Proxima inspecao: {e["PROXIMA_INSPECAO"]}
Responsavel: {e["RESPONSAVEL"]}
CREA: {e["CREA"]}

Itens verificados conforme NR-13:
- Pressostatos e valvulas de seguranca
- Sistema de alimentacao de agua
- Dispositivos de controle e protecao
- Espessura de chapas (END)

4 CONCLUSAO

{e["CONCLUSAO"]}
"""


_GOLD_DOCS: list[str] = [_gold(0), _gold(1), _gold(2)]


FORMAT = Format(
    name="nr13",
    title="NR-13 - Laudo de inspecao em caldeiras e vasos de pressao",
    description=(
        "Laudo de inspecao de seguranca em caldeiras, vasos de pressao, "
        "tubulacoes e tanques de armazenamento segundo NR-13."
    ),
    spec="NR-13 (Portaria MTE)",
    schemas=_SCHEMAS,
    field_examples=_FIELD_EXAMPLES,
    gold_docs=_GOLD_DOCS,
    conformity_weights={
        "text": 0.20,
        "structural": 0.25,
        "visual": 0.05,
        "design": 0.05,
        "technical": 0.45,
    },
    required_headings=["IDENTIFICACAO", "EQUIPAMENTO", "INSPECAO", "CONCLUSAO"],
    recommended_threshold=0.90,
)
