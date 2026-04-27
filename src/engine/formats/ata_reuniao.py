"""Ata de Reuniao - formato generico (Wave I)."""

from __future__ import annotations

from engine.formats._base import Format
from engine.schema_inference import FieldSchema

_SCHEMAS: list[FieldSchema] = [
    FieldSchema("ATA_NUMERO", "{{ATA_NUMERO}}", "mustache", field_type="doc_code", required=True),
    FieldSchema("DATA", "{{DATA}}", "mustache", field_type="iso_date", required=True),
    FieldSchema("HORA_INICIO", "{{HORA_INICIO}}", "mustache", field_type="freetext", required=True),
    FieldSchema("HORA_FIM", "{{HORA_FIM}}", "mustache", field_type="freetext", required=True),
    FieldSchema("LOCAL", "{{LOCAL}}", "mustache", field_type="freetext", required=True),
    FieldSchema("ASSUNTO", "{{ASSUNTO}}", "mustache", field_type="freetext", required=True),
    FieldSchema("PARTICIPANTES", "{{PARTICIPANTES}}", "mustache", field_type="freetext", required=True),
    FieldSchema("PAUTA", "{{PAUTA}}", "mustache", field_type="freetext", required=True),
    FieldSchema("DELIBERACOES", "{{DELIBERACOES}}", "mustache", field_type="freetext", required=True),
    FieldSchema("PROXIMA_REUNIAO", "{{PROXIMA_REUNIAO}}", "mustache", field_type="iso_date", required=False),
]

_FIELD_EXAMPLES: dict[str, list[str]] = {
    "ATA_NUMERO": ["ATA-2026-001", "ATA-2026-042", "ATA-2026-099"],
    "DATA": ["2026-01-15", "2026-04-26", "2026-07-30"],
    "HORA_INICIO": ["09:00", "14:30", "10:00"],
    "HORA_FIM": ["10:30", "16:00", "11:30"],
    "LOCAL": [
        "Sala de reunioes principal",
        "Sala virtual via Meet",
        "Auditorio do edificio sede",
    ],
    "ASSUNTO": [
        "Planejamento Q1 2026",
        "Revisao de metas trimestrais",
        "Aprovacao do orcamento anual",
    ],
    "PARTICIPANTES": [
        "Joao da Silva, Maria Souza, Pedro Lima",
        "Ana Carolina, Bruno Henrique, Carla Mendes",
        "Carlos Mendes, Beatriz Costa, Daniel Oliveira",
    ],
    "PAUTA": [
        "1. Revisao das metas anteriores 2. Definicao de OKRs 3. Cronograma",
        "1. Performance Q1 2. Ajustes Q2 3. Riscos identificados",
        "1. Apresentacao do orcamento 2. Discussao 3. Aprovacao",
    ],
    "DELIBERACOES": [
        "Aprovado o plano apresentado. Cronograma vigora a partir de 01/02.",
        "Aprovados os ajustes Q2 com 80% das metas mantidas.",
        "Orcamento aprovado por unanimidade com revisao em junho.",
    ],
    "PROXIMA_REUNIAO": ["2026-02-15", "2026-05-26", "2026-08-30"],
}


def _gold(i: int) -> str:
    e = {k: v[i] for k, v in _FIELD_EXAMPLES.items()}
    return f"""ATA DE REUNIAO N {e["ATA_NUMERO"]}

Data: {e["DATA"]}
Hora inicio: {e["HORA_INICIO"]}
Hora fim: {e["HORA_FIM"]}
Local: {e["LOCAL"]}
Assunto: {e["ASSUNTO"]}

Participantes: {e["PARTICIPANTES"]}

Pauta: {e["PAUTA"]}

Deliberacoes: {e["DELIBERACOES"]}

Proxima reuniao: {e["PROXIMA_REUNIAO"]}
"""


_GOLD_DOCS: list[str] = [_gold(0), _gold(1), _gold(2)]


FORMAT = Format(
    name="ata_reuniao",
    title="Ata de Reuniao - generico",
    description=(
        "Ata de reuniao corporativa generica. Inclui identificacao, "
        "participantes, pauta, deliberacoes e proxima reuniao."
    ),
    spec="generico",
    schemas=_SCHEMAS,
    field_examples=_FIELD_EXAMPLES,
    gold_docs=_GOLD_DOCS,
    conformity_weights={
        "text": 0.35,
        "structural": 0.20,
        "visual": 0.05,
        "design": 0.05,
        "technical": 0.35,
    },
    required_headings=["PARTICIPANTES", "PAUTA", "DELIBERACOES"],
    recommended_threshold=0.85,
)
