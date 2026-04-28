"""ABNT NBR 6022 — formato de artigo cientifico.

Spec: ABNT NBR 6022:2018 — Informacao e documentacao — Artigo em publicacao
periodica tecnica e/ou cientifica — Apresentacao.

Campos esperados:

- TITULO, AUTORES, RESUMO, PALAVRAS_CHAVE
- ABSTRACT, KEYWORDS (versao em ingles)
- INTRODUCAO, REFERENCIAS

Estrutura tipica:

```
TITULO
Autor(es) - filiacao - email

Resumo: ... (100-250 palavras)
Palavras-chave: termo1; termo2; termo3

Abstract: ...
Keywords: ...

1 INTRODUCAO
2 DESENVOLVIMENTO
3 CONCLUSAO

REFERENCIAS
```
"""

from __future__ import annotations

from engine.formats._base import Format
from engine.schema_inference import FieldSchema

_SCHEMAS: list[FieldSchema] = [
    FieldSchema(
        name="TITULO",
        placeholder_token="{{TITULO}}",
        kind="mustache",
        field_type="freetext",
        required=True,
    ),
    FieldSchema(
        name="AUTORES",
        placeholder_token="{{AUTORES}}",
        kind="mustache",
        field_type="freetext",
        required=True,
    ),
    FieldSchema(
        name="RESUMO",
        placeholder_token="{{RESUMO}}",
        kind="mustache",
        field_type="freetext",
        required=True,
    ),
    FieldSchema(
        name="PALAVRAS_CHAVE",
        placeholder_token="{{PALAVRAS_CHAVE}}",
        kind="mustache",
        field_type="freetext",
        required=True,
    ),
    FieldSchema(
        name="ABSTRACT",
        placeholder_token="{{ABSTRACT}}",
        kind="mustache",
        field_type="freetext",
        required=True,
    ),
    FieldSchema(
        name="KEYWORDS",
        placeholder_token="{{KEYWORDS}}",
        kind="mustache",
        field_type="freetext",
        required=True,
    ),
    FieldSchema(
        name="INTRODUCAO",
        placeholder_token="{{INTRODUCAO}}",
        kind="mustache",
        field_type="freetext",
        required=True,
    ),
    FieldSchema(
        name="REFERENCIAS",
        placeholder_token="{{REFERENCIAS}}",
        kind="mustache",
        field_type="freetext",
        required=True,
    ),
]

_FIELD_EXAMPLES: dict[str, list[str]] = {
    "TITULO": [
        "Analise de algoritmos de ordenacao em ambientes embarcados",
        "Estudo comparativo de metodos de aprendizado de maquina",
        "Otimizacao de consumo energetico em data centers",
    ],
    "AUTORES": [
        "Joao da Silva, Maria Souza",
        "Pedro Henrique Lima",
        "Ana Carolina Costa, Bruno Lima, Carla Mendes",
    ],
    "RESUMO": [
        "Este artigo apresenta uma analise comparativa de tres algoritmos de ordenacao em sistemas embarcados.",
        "O estudo avaliou cinco modelos de aprendizado supervisionado em datasets publicos.",
        "Esta pesquisa propoe um metodo para reducao de consumo energetico em data centers.",
    ],
    "PALAVRAS_CHAVE": [
        "algoritmos; ordenacao; sistemas embarcados",
        "aprendizado de maquina; classificacao; benchmark",
        "consumo energetico; data center; otimizacao",
    ],
    "ABSTRACT": [
        "This article presents a comparative analysis of three sorting algorithms in embedded systems.",
        "The study evaluated five supervised learning models on public datasets.",
        "This research proposes a method for reducing energy consumption in data centers.",
    ],
    "KEYWORDS": [
        "algorithms; sorting; embedded systems",
        "machine learning; classification; benchmark",
        "energy consumption; data center; optimization",
    ],
    "INTRODUCAO": [
        "Sistemas embarcados possuem restricoes de memoria e CPU que impactam a escolha de algoritmos.",
        "Aprendizado de maquina e amplamente aplicado em problemas de classificacao supervisionada.",
        "Data centers consomem cerca de 1 porcento da eletricidade mundial.",
    ],
    "REFERENCIAS": [
        "CORMEN, T. H. et al. Introduction to Algorithms. 4. ed. MIT Press, 2026.",
        "GOODFELLOW, I.; BENGIO, Y.; COURVILLE, A. Deep Learning. MIT Press, 2026.",
        "BARROSO, L. The Datacenter as a Computer. 3. ed. Morgan Claypool, 2026.",
    ],
}


def _gold(idx: int) -> str:
    return f"""{_FIELD_EXAMPLES["TITULO"][idx]}

{_FIELD_EXAMPLES["AUTORES"][idx]}

Resumo: {_FIELD_EXAMPLES["RESUMO"][idx]}
Palavras-chave: {_FIELD_EXAMPLES["PALAVRAS_CHAVE"][idx]}

Abstract: {_FIELD_EXAMPLES["ABSTRACT"][idx]}
Keywords: {_FIELD_EXAMPLES["KEYWORDS"][idx]}

1 INTRODUCAO

{_FIELD_EXAMPLES["INTRODUCAO"][idx]}

2 DESENVOLVIMENTO

Desenvolvimento detalhado da pesquisa.

3 CONCLUSAO

Conclusao final do artigo.

REFERENCIAS

{_FIELD_EXAMPLES["REFERENCIAS"][idx]}
"""


_GOLD_DOCS: list[str] = [_gold(0), _gold(1), _gold(2)]


FORMAT = Format(
    name="abnt_artigo",
    title="ABNT NBR 6022 - Artigo cientifico",
    description=(
        "Formato de artigo cientifico segundo NBR 6022. Capa-titulo, autores, "
        "resumo+palavras-chave (PT), abstract+keywords (EN), introducao, "
        "desenvolvimento, conclusao, referencias."
    ),
    spec="ABNT NBR 6022:2018",
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
    required_headings=["Resumo", "Abstract", "Introducao", "Conclusao", "Referencias"],
    recommended_threshold=0.85,
)
