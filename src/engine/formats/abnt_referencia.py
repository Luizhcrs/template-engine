"""ABNT NBR 6023 - Referencias bibliograficas (Wave H).

Spec: ABNT NBR 6023:2018 - Informacao e documentacao - Referencias - Elaboracao.

Formato basico de livro (modelo monografia):

```
SOBRENOME, Nome. Titulo: subtitulo. Edicao. Local: Editora, ano. paginas.
```

Exemplo:

```
CORMEN, T. H. et al. Introduction to Algorithms. 4. ed. Cambridge: MIT Press, 2026. 1320 p.
```

Este format e mais um **validador** de linha de referencia do que um doc
inteiro - util pra QA de listas de referencias em TCCs/artigos.
"""

from __future__ import annotations

from engine.formats._base import Format
from engine.schema_inference import FieldSchema

_SCHEMAS: list[FieldSchema] = [
    FieldSchema("AUTOR", "{{AUTOR}}", "mustache", field_type="freetext", required=True),
    FieldSchema("TITULO", "{{TITULO}}", "mustache", field_type="freetext", required=True),
    FieldSchema("EDICAO", "{{EDICAO}}", "mustache", field_type="freetext", required=False),
    FieldSchema("LOCAL", "{{LOCAL}}", "mustache", field_type="freetext", required=True),
    FieldSchema("EDITORA", "{{EDITORA}}", "mustache", field_type="freetext", required=True),
    FieldSchema("ANO", "{{ANO}}", "mustache", field_type="integer", required=True),
    FieldSchema("PAGINAS", "{{PAGINAS}}", "mustache", field_type="freetext", required=False),
]

_FIELD_EXAMPLES: dict[str, list[str]] = {
    "AUTOR": [
        "CORMEN, T. H. et al",
        "GOODFELLOW, Ian; BENGIO, Yoshua; COURVILLE, Aaron",
        "BARROSO, L. A.",
    ],
    "TITULO": [
        "Introduction to Algorithms",
        "Deep Learning",
        "The Datacenter as a Computer",
    ],
    "EDICAO": ["4. ed.", "1. ed.", "3. ed."],
    "LOCAL": ["Cambridge", "Cambridge", "San Rafael"],
    "EDITORA": ["MIT Press", "MIT Press", "Morgan Claypool"],
    "ANO": ["2026", "2026", "2026"],
    "PAGINAS": ["1320 p.", "775 p.", "248 p."],
}

_GOLD_DOCS: list[str] = [
    "REFERENCIAS\n\n"
    + "\n".join(
        f"{_FIELD_EXAMPLES['AUTOR'][i]}. {_FIELD_EXAMPLES['TITULO'][i]}. "
        f"{_FIELD_EXAMPLES['EDICAO'][i]} {_FIELD_EXAMPLES['LOCAL'][i]}: "
        f"{_FIELD_EXAMPLES['EDITORA'][i]}, {_FIELD_EXAMPLES['ANO'][i]}. "
        f"{_FIELD_EXAMPLES['PAGINAS'][i]}"
        for i in range(3)
    )
    for _ in range(3)
]


FORMAT = Format(
    name="abnt_referencia",
    title="ABNT NBR 6023 - Referencias bibliograficas",
    description=(
        "Formato de referencia bibliografica segundo NBR 6023 (modelo livro). "
        "Util como validador isolado de linhas de referencia em TCCs/artigos."
    ),
    spec="ABNT NBR 6023:2018",
    schemas=_SCHEMAS,
    field_examples=_FIELD_EXAMPLES,
    gold_docs=_GOLD_DOCS,
    conformity_weights={
        "text": 0.40,
        "structural": 0.10,
        "visual": 0.05,
        "design": 0.05,
        "technical": 0.40,
    },
    required_headings=["REFERENCIAS"],
    recommended_threshold=0.90,
)
