"""NR-12 - Laudo de seguranca em maquinas e equipamentos (Wave H).

Spec: Norma Regulamentadora 12 (Portaria MTE) - Seguranca no trabalho em
maquinas e equipamentos.

Use case: Engeman e empresas industriais que recebem laudos de inspecao de
maquinas de vendors terceiros e precisam padronizar pro template corporativo.

Campos esperados:

- EMPRESA, CNPJ_EMPRESA, ENDERECO
- EQUIPAMENTO, TAG_EQUIPAMENTO, FABRICANTE, NS_EQUIPAMENTO
- DATA_INSPECAO, RESPONSAVEL, CREA
- CONCLUSAO

Pesos de conformidade: technical alto (CNPJ, CREA, datas validados), structural
medio (laudo tem secoes fixas: Identificacao, Equipamento, Inspecao, Conclusao).
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
    FieldSchema("ENDERECO", "{{ENDERECO}}", "mustache", field_type="freetext", required=True),
    FieldSchema("EQUIPAMENTO", "{{EQUIPAMENTO}}", "mustache", field_type="freetext", required=True),
    FieldSchema(
        "TAG_EQUIPAMENTO",
        "{{TAG_EQUIPAMENTO}}",
        "mustache",
        field_type="doc_code",
        required=True,
    ),
    FieldSchema("FABRICANTE", "{{FABRICANTE}}", "mustache", field_type="freetext", required=True),
    FieldSchema(
        "NS_EQUIPAMENTO",
        "{{NS_EQUIPAMENTO}}",
        "mustache",
        field_type="doc_code",
        required=True,
    ),
    FieldSchema(
        "DATA_INSPECAO",
        "{{DATA_INSPECAO}}",
        "mustache",
        field_type="iso_date",
        required=True,
    ),
    FieldSchema("RESPONSAVEL", "{{RESPONSAVEL}}", "mustache", field_type="fullname", required=True),
    FieldSchema(
        "CREA",
        "{{CREA}}",
        "mustache",
        field_type="doc_code",
        format_hint="CREA-UF NNNNNN",
        required=True,
    ),
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
    "ENDERECO": [
        "Av Industrial, 1000 - Recife - PE - 51000-000",
        "Rua das Maquinas, 250 - Sao Paulo - SP - 01000-000",
        "Av Boa Viagem, 500 - Recife - PE - 51011-000",
    ],
    "EQUIPAMENTO": [
        "Prensa hidraulica 200t",
        "Torno CNC modelo X-2000",
        "Compressor de parafuso 50hp",
    ],
    "TAG_EQUIPAMENTO": ["EQ-001-X", "EQ-042-Y", "EQ-099-Z"],
    "FABRICANTE": ["Schuler", "Mazak", "Atlas Copco"],
    "NS_EQUIPAMENTO": ["NS-2024-0001", "NS-2024-0042", "NS-2024-0099"],
    "DATA_INSPECAO": ["2026-01-15", "2026-04-26", "2026-07-30"],
    "RESPONSAVEL": [
        "Joao da Silva",
        "Maria Carolina Souza",
        "Pedro Henrique Lima",
    ],
    "CREA": ["CREA-PE 123456", "CREA-SP 987654", "CREA-RJ 445566"],
    "CONCLUSAO": [
        "Equipamento em conformidade com NR-12. Apto para operacao.",
        "Equipamento apresenta nao-conformidades menores. Recomenda-se manutencao corretiva em 30 dias.",
        "Equipamento em conformidade. Proxima inspecao em 12 meses.",
    ],
}


def _gold(i: int) -> str:
    e = {k: v[i] for k, v in _FIELD_EXAMPLES.items()}
    return f"""LAUDO TECNICO DE SEGURANCA - NR-12

1 IDENTIFICACAO

Empresa: {e["EMPRESA"]}
CNPJ: {e["CNPJ_EMPRESA"]}
Endereco: {e["ENDERECO"]}

2 EQUIPAMENTO

Equipamento: {e["EQUIPAMENTO"]}
Tag: {e["TAG_EQUIPAMENTO"]}
Fabricante: {e["FABRICANTE"]}
Numero de serie: {e["NS_EQUIPAMENTO"]}

3 INSPECAO

Data: {e["DATA_INSPECAO"]}
Responsavel: {e["RESPONSAVEL"]}
CREA: {e["CREA"]}

Itens verificados conforme NR-12:
- Protecoes fixas e moveis
- Dispositivos de parada de emergencia
- Sistemas de aterramento
- Sinalizacao e iluminacao

4 CONCLUSAO

{e["CONCLUSAO"]}

Recife, {e["DATA_INSPECAO"]}
"""


_GOLD_DOCS: list[str] = [_gold(0), _gold(1), _gold(2)]


FORMAT = Format(
    name="laudo_nr12",
    title="NR-12 - Laudo de seguranca em maquinas",
    description=(
        "Laudo tecnico de inspecao de seguranca em maquinas e equipamentos "
        "industriais segundo NR-12 (Portaria MTE). Inclui identificacao da "
        "empresa, equipamento, inspecao e conclusao."
    ),
    spec="NR-12 (Portaria MTE)",
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
