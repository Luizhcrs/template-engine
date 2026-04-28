"""NR-35 - Permissao de Trabalho em Altura.

Spec: Norma Regulamentadora 35 (Portaria MTE) - Trabalho em altura.

Documento de PT (Permissao de Trabalho) emitido antes de qualquer atividade
acima de 2 metros do nivel inferior.
"""

from __future__ import annotations

from engine.formats._base import Format
from engine.schema_inference import FieldSchema

_SCHEMAS: list[FieldSchema] = [
    FieldSchema("EMPRESA", "{{EMPRESA}}", "mustache", field_type="freetext", required=True),
    FieldSchema("PT_NUMERO", "{{PT_NUMERO}}", "mustache", field_type="doc_code", required=True),
    FieldSchema("DATA_EMISSAO", "{{DATA_EMISSAO}}", "mustache", field_type="iso_date", required=True),
    FieldSchema(
        "VALIDADE",
        "{{VALIDADE}}",
        "mustache",
        field_type="freetext",
        required=True,
        format_hint="ate fim do turno",
    ),
    FieldSchema("LOCAL_TRABALHO", "{{LOCAL_TRABALHO}}", "mustache", field_type="freetext", required=True),
    FieldSchema("ALTURA", "{{ALTURA}}", "mustache", field_type="freetext", required=True),
    FieldSchema("DESCRICAO_TAREFA", "{{DESCRICAO_TAREFA}}", "mustache", field_type="freetext", required=True),
    FieldSchema("EXECUTANTE", "{{EXECUTANTE}}", "mustache", field_type="fullname", required=True),
    FieldSchema(
        "MATRICULA",
        "{{MATRICULA}}",
        "mustache",
        field_type="doc_code",
        required=True,
    ),
    FieldSchema("SUPERVISOR", "{{SUPERVISOR}}", "mustache", field_type="fullname", required=True),
    FieldSchema(
        "TREINAMENTO_VALIDO_ATE",
        "{{TREINAMENTO_VALIDO_ATE}}",
        "mustache",
        field_type="iso_date",
        required=True,
    ),
]

_FIELD_EXAMPLES: dict[str, list[str]] = {
    "EMPRESA": [
        "ACME Construtora Ltda",
        "Globex Engenharia S/A",
        "Hooli Manutencao ME",
    ],
    "PT_NUMERO": ["PT-2026-0001", "PT-2026-0042", "PT-2026-0099"],
    "DATA_EMISSAO": ["2026-01-15", "2026-04-26", "2026-07-30"],
    "VALIDADE": [
        "ate fim do turno (8h)",
        "ate 18:00 do mesmo dia",
        "ate fim das 12h de jornada",
    ],
    "LOCAL_TRABALHO": [
        "Telhado predio A - lado norte",
        "Andaime fachada bloco B",
        "Torre de transmissao TX-12",
    ],
    "ALTURA": ["8 metros", "15 metros", "32 metros"],
    "DESCRICAO_TAREFA": [
        "Substituicao de telhas e impermeabilizacao",
        "Pintura externa da fachada",
        "Substituicao de isoladores e cabos",
    ],
    "EXECUTANTE": [
        "Joao da Silva",
        "Maria Carolina Souza",
        "Pedro Henrique Lima",
    ],
    "MATRICULA": ["MAT-12345", "MAT-67890", "MAT-44556"],
    "SUPERVISOR": [
        "Carlos Mendes",
        "Ana Beatriz Costa",
        "Bruno Almeida",
    ],
    "TREINAMENTO_VALIDO_ATE": ["2027-01-15", "2027-04-26", "2027-07-30"],
}


def _gold(i: int) -> str:
    e = {k: v[i] for k, v in _FIELD_EXAMPLES.items()}
    return f"""PERMISSAO DE TRABALHO EM ALTURA - NR-35

1 IDENTIFICACAO

Empresa: {e["EMPRESA"]}
PT N: {e["PT_NUMERO"]}
Data de emissao: {e["DATA_EMISSAO"]}
Validade: {e["VALIDADE"]}

2 LOCAL E TAREFA

Local: {e["LOCAL_TRABALHO"]}
Altura: {e["ALTURA"]}
Descricao: {e["DESCRICAO_TAREFA"]}

3 EQUIPE

Executante: {e["EXECUTANTE"]}
Matricula: {e["MATRICULA"]}
Supervisor: {e["SUPERVISOR"]}
Treinamento valido ate: {e["TREINAMENTO_VALIDO_ATE"]}

4 ANALISE PRELIMINAR DE RISCO

Riscos identificados:
- Queda de altura
- Queda de objetos
- Condicoes meteorologicas

Medidas de controle:
- Cinto paraquedista tipo Y
- Linha de vida instalada
- Conferencia de equipamentos antes da subida

5 ASSINATURAS

Executante: ____________________
Supervisor: ____________________
"""


_GOLD_DOCS: list[str] = [_gold(0), _gold(1), _gold(2)]


FORMAT = Format(
    name="nr35",
    title="NR-35 - Permissao de Trabalho em Altura",
    description=(
        "Permissao de Trabalho (PT) para atividades acima de 2 metros segundo "
        "NR-35. Inclui APR (Analise Preliminar de Risco), executante + "
        "supervisor + validade do treinamento."
    ),
    spec="NR-35 (Portaria MTE)",
    schemas=_SCHEMAS,
    field_examples=_FIELD_EXAMPLES,
    gold_docs=_GOLD_DOCS,
    conformity_weights={
        "text": 0.20,
        "structural": 0.20,
        "visual": 0.05,
        "design": 0.05,
        "technical": 0.50,
    },
    required_headings=["IDENTIFICACAO", "LOCAL", "EQUIPE", "RISCO", "ASSINATURAS"],
    recommended_threshold=0.90,
)
