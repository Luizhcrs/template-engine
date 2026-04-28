"""ABNT NBR 10719 - Relatorio tecnico-cientifico.

Spec: ABNT NBR 10719:2015 - Informacao e documentacao - Relatorio tecnico
e/ou cientifico - Apresentacao.
"""

from __future__ import annotations

from engine.formats._base import Format
from engine.schema_inference import FieldSchema

_SCHEMAS: list[FieldSchema] = [
    FieldSchema("TITULO", "{{TITULO}}", "mustache", field_type="freetext", required=True),
    FieldSchema("AUTORES", "{{AUTORES}}", "mustache", field_type="freetext", required=True),
    FieldSchema("INSTITUICAO", "{{INSTITUICAO}}", "mustache", field_type="freetext", required=True),
    FieldSchema("RELATORIO_N", "{{RELATORIO_N}}", "mustache", field_type="doc_code", required=True),
    FieldSchema("DATA", "{{DATA}}", "mustache", field_type="iso_date", required=True),
    FieldSchema("LOCAL", "{{LOCAL}}", "mustache", field_type="freetext", required=True),
    FieldSchema("RESUMO", "{{RESUMO}}", "mustache", field_type="freetext", required=True),
    FieldSchema(
        "PALAVRAS_CHAVE",
        "{{PALAVRAS_CHAVE}}",
        "mustache",
        field_type="freetext",
        required=True,
    ),
    FieldSchema("OBJETIVO", "{{OBJETIVO}}", "mustache", field_type="freetext", required=True),
    FieldSchema("CONCLUSAO", "{{CONCLUSAO}}", "mustache", field_type="freetext", required=True),
]

_FIELD_EXAMPLES: dict[str, list[str]] = {
    "TITULO": [
        "Avaliacao de desempenho de motores eletricos industriais",
        "Estudo de viabilidade tecnica de geradores fotovoltaicos",
        "Analise de falhas em redutores de velocidade",
    ],
    "AUTORES": [
        "Joao da Silva, Maria Souza",
        "Pedro Henrique Lima",
        "Ana Carolina Costa, Bruno Lima",
    ],
    "INSTITUICAO": [
        "Instituto de Pesquisas Tecnologicas",
        "Centro de Inovacao Industrial",
        "Laboratorio de Engenharia Mecanica",
    ],
    "RELATORIO_N": ["RT-2026-001", "RT-2026-042", "RT-2026-099"],
    "DATA": ["2026-01-15", "2026-04-26", "2026-07-30"],
    "LOCAL": ["Recife - PE", "Sao Paulo - SP", "Rio de Janeiro - RJ"],
    "RESUMO": [
        "Este relatorio apresenta a avaliacao de tres modelos de motores eletricos industriais.",
        "Estudo da viabilidade tecnica de geradores fotovoltaicos em ambiente urbano.",
        "Analise das principais falhas em redutores de velocidade de uso industrial.",
    ],
    "PALAVRAS_CHAVE": [
        "motores eletricos; eficiencia; industria",
        "fotovoltaico; energia solar; viabilidade",
        "redutores; falhas; manutencao",
    ],
    "OBJETIVO": [
        "Avaliar comparativamente o desempenho de motores eletricos sob carga variavel.",
        "Determinar a viabilidade tecnica de geradores fotovoltaicos em telhados urbanos.",
        "Identificar os principais modos de falha de redutores em servico continuo.",
    ],
    "CONCLUSAO": [
        "Os tres modelos apresentaram desempenho dentro da norma com vantagem para o modelo X.",
        "Geradores fotovoltaicos urbanos sao viaveis em 78% dos cenarios analisados.",
        "Falhas decorrem majoritariamente de lubrificacao inadequada e sobrecarga.",
    ],
}


def _gold(i: int) -> str:
    e = {k: v[i] for k, v in _FIELD_EXAMPLES.items()}
    return f"""{e["INSTITUICAO"]}

RELATORIO TECNICO N {e["RELATORIO_N"]}

{e["TITULO"]}

{e["AUTORES"]}

{e["LOCAL"]}, {e["DATA"]}

RESUMO

{e["RESUMO"]}

Palavras-chave: {e["PALAVRAS_CHAVE"]}

1 OBJETIVO

{e["OBJETIVO"]}

2 METODOLOGIA

Detalhes da metodologia adotada.

3 RESULTADOS

Resultados obtidos durante o estudo.

4 CONCLUSAO

{e["CONCLUSAO"]}

REFERENCIAS

Referencias bibliograficas conforme NBR 6023.
"""


_GOLD_DOCS: list[str] = [_gold(0), _gold(1), _gold(2)]


FORMAT = Format(
    name="abnt_relatorio_tecnico",
    title="ABNT NBR 10719 - Relatorio tecnico-cientifico",
    description=(
        "Relatorio tecnico-cientifico segundo NBR 10719. Estrutura: capa, "
        "identificacao, resumo, objetivo, metodologia, resultados, conclusao, "
        "referencias."
    ),
    spec="ABNT NBR 10719:2015",
    schemas=_SCHEMAS,
    field_examples=_FIELD_EXAMPLES,
    gold_docs=_GOLD_DOCS,
    conformity_weights={
        "text": 0.30,
        "structural": 0.25,
        "visual": 0.10,
        "design": 0.10,
        "technical": 0.25,
    },
    required_headings=["RESUMO", "OBJETIVO", "METODOLOGIA", "RESULTADOS", "CONCLUSAO", "REFERENCIAS"],
    recommended_threshold=0.85,
)
