"""ABNT NBR 14724 - TCC / dissertacao / tese (Wave H).

Spec: ABNT NBR 14724:2024 - Informacao e documentacao - Trabalhos academicos -
Apresentacao.

Campos esperados:

- TITULO, AUTOR, ORIENTADOR
- INSTITUICAO, CURSO, ANO, LOCAL
- RESUMO, ABSTRACT, PALAVRAS_CHAVE, KEYWORDS

Estrutura tipica (elementos pre-textuais + textuais + pos-textuais):

```
Capa: INSTITUICAO / AUTOR / TITULO / LOCAL ANO
Folha de rosto: AUTOR / TITULO / "Trabalho apresentado..." / ORIENTADOR
Resumo + Palavras-chave
Abstract + Keywords
Sumario
1 INTRODUCAO
2 DESENVOLVIMENTO (capitulos)
3 CONCLUSAO
REFERENCIAS
```
"""

from __future__ import annotations

from engine.formats._base import Format
from engine.schema_inference import FieldSchema

_SCHEMAS: list[FieldSchema] = [
    FieldSchema("TITULO", "{{TITULO}}", "mustache", field_type="freetext", required=True),
    FieldSchema("AUTOR", "{{AUTOR}}", "mustache", field_type="fullname", required=True),
    FieldSchema("ORIENTADOR", "{{ORIENTADOR}}", "mustache", field_type="fullname", required=True),
    FieldSchema("INSTITUICAO", "{{INSTITUICAO}}", "mustache", field_type="freetext", required=True),
    FieldSchema("CURSO", "{{CURSO}}", "mustache", field_type="freetext", required=True),
    FieldSchema("ANO", "{{ANO}}", "mustache", field_type="integer", required=True),
    FieldSchema("LOCAL", "{{LOCAL}}", "mustache", field_type="freetext", required=True),
    FieldSchema("RESUMO", "{{RESUMO}}", "mustache", field_type="freetext", required=True),
    FieldSchema("ABSTRACT", "{{ABSTRACT}}", "mustache", field_type="freetext", required=True),
    FieldSchema(
        "PALAVRAS_CHAVE",
        "{{PALAVRAS_CHAVE}}",
        "mustache",
        field_type="freetext",
        required=True,
    ),
    FieldSchema("KEYWORDS", "{{KEYWORDS}}", "mustache", field_type="freetext", required=True),
]

_FIELD_EXAMPLES: dict[str, list[str]] = {
    "TITULO": [
        "Aplicacao de redes neurais profundas em diagnostico de defeitos industriais",
        "Modelagem de processos de manufatura aditiva",
        "Sistemas de recomendacao baseados em grafos heterogeneos",
    ],
    "AUTOR": [
        "Joao da Silva Santos",
        "Maria Carolina Souza Lima",
        "Pedro Henrique de Oliveira",
    ],
    "ORIENTADOR": [
        "Prof. Dr. Carlos Mendes",
        "Profa. Dra. Ana Beatriz Costa",
        "Prof. Dr. Bruno Henrique Almeida",
    ],
    "INSTITUICAO": [
        "Universidade Federal de Pernambuco",
        "Universidade de Sao Paulo",
        "Universidade Federal do Rio de Janeiro",
    ],
    "CURSO": [
        "Engenharia de Computacao",
        "Engenharia Mecanica",
        "Ciencia da Computacao",
    ],
    "ANO": ["2026", "2025", "2026"],
    "LOCAL": ["Recife - PE", "Sao Paulo - SP", "Rio de Janeiro - RJ"],
    "RESUMO": [
        "Este trabalho apresenta um sistema de diagnostico de defeitos industriais utilizando redes neurais convolucionais.",
        "A pesquisa propoe um modelo de simulacao para processos de manufatura aditiva metalica.",
        "Esta dissertacao apresenta um sistema de recomendacao baseado em grafos heterogeneos.",
    ],
    "ABSTRACT": [
        "This work presents an industrial defect diagnosis system using convolutional neural networks.",
        "This research proposes a simulation model for metallic additive manufacturing processes.",
        "This dissertation presents a recommender system based on heterogeneous graphs.",
    ],
    "PALAVRAS_CHAVE": [
        "redes neurais; diagnostico industrial; visao computacional",
        "manufatura aditiva; simulacao; metalurgia",
        "sistemas de recomendacao; grafos; aprendizado profundo",
    ],
    "KEYWORDS": [
        "neural networks; industrial diagnosis; computer vision",
        "additive manufacturing; simulation; metallurgy",
        "recommender systems; graphs; deep learning",
    ],
}


def _gold(i: int) -> str:
    e = {k: v[i] for k, v in _FIELD_EXAMPLES.items()}
    return f"""{e["INSTITUICAO"]}
{e["CURSO"]}

{e["AUTOR"]}

{e["TITULO"]}

{e["LOCAL"]}
{e["ANO"]}

---

{e["AUTOR"]}

{e["TITULO"]}

Trabalho de conclusao de curso apresentado ao {e["CURSO"]} da {e["INSTITUICAO"]} como requisito parcial para obtencao do titulo.

Orientador: {e["ORIENTADOR"]}

{e["LOCAL"]}
{e["ANO"]}

---

RESUMO

{e["RESUMO"]}

Palavras-chave: {e["PALAVRAS_CHAVE"]}

ABSTRACT

{e["ABSTRACT"]}

Keywords: {e["KEYWORDS"]}

SUMARIO

1 INTRODUCAO
2 REVISAO DE LITERATURA
3 METODOLOGIA
4 RESULTADOS
5 CONCLUSAO
REFERENCIAS

1 INTRODUCAO

Conteudo da introducao do trabalho.

2 REVISAO DE LITERATURA

Revisao do estado da arte.

3 METODOLOGIA

Detalhes da metodologia adotada.

4 RESULTADOS

Apresentacao dos resultados obtidos.

5 CONCLUSAO

Conclusoes finais e trabalhos futuros.

REFERENCIAS

CORMEN, T. H. et al. Introduction to Algorithms. 4. ed. MIT Press, 2026.
"""


_GOLD_DOCS: list[str] = [_gold(0), _gold(1), _gold(2)]


FORMAT = Format(
    name="abnt_tcc",
    title="ABNT NBR 14724 - TCC / dissertacao / tese",
    description=(
        "Formato de trabalho academico segundo NBR 14724. Capa, folha de rosto, "
        "resumo+abstract, sumario, capitulos numerados, referencias."
    ),
    spec="ABNT NBR 14724:2024",
    schemas=_SCHEMAS,
    field_examples=_FIELD_EXAMPLES,
    gold_docs=_GOLD_DOCS,
    conformity_weights={
        "text": 0.25,
        "structural": 0.30,
        "visual": 0.10,
        "design": 0.10,
        "technical": 0.25,
    },
    required_headings=[
        "RESUMO",
        "ABSTRACT",
        "SUMARIO",
        "INTRODUCAO",
        "CONCLUSAO",
        "REFERENCIAS",
    ],
    recommended_threshold=0.85,
)
