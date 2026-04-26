# Pipeline

Duas operações expõem a engine: **normalize** (template + N sources → N outputs) e **check_conformity** (template + 1 candidato → veredicto multi-dim). Ambas compartilham as mesmas primitivas.

## Pipeline de normalização

```
template.docx                     source_dir/*.docx,*.pdf
      │                                    │
      ▼                                    ▼
┌──────────────────┐             ┌──────────────────┐
│ schema_inference │             │ extractor        │
│ FieldSchema list │             │ texto + tabelas  │
└──────────────────┘             └──────────────────┘
      │                                    │
      ▼                                    ▼
┌────────────────────┐         ┌──────────────────────┐
│ pattern_inference  │  ─────► │ hybrid_mapper        │
│ regex por campo    │         │ tier 1: regex        │
│ (10 shapes + grex) │         │ tier 2: LLM batched  │
└────────────────────┘         │ MappingResult dict   │
                               └──────────────────────┘
                                         │
                                         ▼
                               ┌──────────────────────┐
                               │ token substitution   │
                               │ render em copy docx  │
                               └──────────────────────┘
                                         │
                                         ▼
                               ┌──────────────────────┐
                               │ semantic_diff (LLM)  │
                               │ flags missing/diff/  │
                               │ extra no output      │
                               └──────────────────────┘
                                         │
                                         ▼
                               BatchReport: tier por doc
                               + summary + discrepancies
```

## Estágios

### 1. `extract`

`engine.extractor.extract(path) -> ExtractedDoc`. Lê `.docx` (`python-docx`) ou `.pdf` (`pdfplumber`). Retorna texto + parágrafos + tabelas + header_fields. Stateless. Sem LLM.

### 2. `schema_inference`

`engine.schema_inference.detect_placeholders(text) -> list[FieldSchema]`. Cinco sintaxes reconhecidas:

| Sintaxe | Exemplo | Uso |
|---------|---------|-----|
| Mustache | `{{CODIGO}}` | Mais comum. Recomendada. |
| Bracket | `[NOME]` | Estilo formulário. |
| Chevron | `<<CLIENTE>>` | Templates legados. |
| Named blank | `__DOC_ID__` | Wrap em underscore. |
| Anonymous blank | `___` (3+) | Auto-nomeia `BLANK_<n>`. |

Opcional `enrich_with_llm(schemas, llm)` chama LLM 1x por campo pra inferir `field_type` (e.g. `iso_date`, `cpf`, `freetext`), `format_hint`, e `required` a partir do contexto.

### 3. `pattern_inference`

`engine.pattern_inference.infer_field_patterns(gold_docs, field_examples) -> dict[field, InferredPattern]`. Pra cada campo:

1. Localiza valores de exemplo nos gold docs, coleta labels antes de cada match.
2. Agrega labels por frequência.
3. Detecta value shape — três tiers, primeiro match vence:
   - **Tier 1**: shapes pré-definidas (`iso_date`, `br_date`, `doc_code`, `cpf`, `cep`, `uf`, `decimal_br`, `integer`, `version`, `fullname`, `month_year_pt`).
   - **Tier 2**: pattern aprendido por `grex` (opcional, só quando âncoras estruturais sobrevivem).
   - **Tier 3**: fallback freetext `[^\n]+`.
4. Compõe `(?:label_alt_1|label_alt_2|...):\s*(value_shape)`.

`apply_inferred(inferred, text) -> dict[field, str]` extrai valores de um doc novo.

### 4. `hybrid_mapper`

`engine.hybrid_mapper.map_hybrid(schemas, inferred_patterns, source_text, llm=None) -> dict[field, MappingResult]`. Dois tiers:

- **Tier 1 (regex/grex):** roda `apply_inferred`. Cada match vira `MappingResult(value, source="regex", confidence=1.0)`.
- **Tier 2 (LLM, opcional):** campos missing entram em uma única chamada batched ao LLM com prompt focado + JSON Schema dinâmico. Cada campo preenchido vira `MappingResult(value, source="llm", confidence=<0-1>)`. Campos que nem o LLM pega: `MappingResult(value=None, source="missing", confidence=0.0)`.

Custo LLM: 0 calls quando regex resolve tudo. 1 chamada batched quando fallback roda, independente de quantos campos caem.

### 5. Renderer

`engine.batch._apply_mapping_to_template`. Copia o template, anda em parágrafos + células de tabela, substitui cada placeholder pelo valor mapeado (string vazia se missing). `python-docx` puro, sem LibreOffice.

### 6. `semantic_diff`

`engine.semantic_diff.diff_documents(source, output, llm, schemas=...) -> list[Discrepancy]`. Pede ao LLM comparar source vs output só por texto. Tipos:

- `missing_in_output` — valor do source não apareceu no output (mais comum).
- `value_mismatch` — mesmo campo, valor diferente.
- `extra_in_output` — output tem conteúdo não justificado pelo source (hallucination).

Severity: `critical` / `warning` / `info`.

### 7. Tier classification

`batch._classify_tier(mapping, discrepancies, schemas)`:

- **`high`**: campos required todos vieram de regex E sem critical discrepancy.
- **`medium`**: algum campo via LLM OU warning-level discrepancy.
- **`low`**: algum required missing OU algum critical.
- **`error`**: extração ou render falhou.

## Pipeline de conformidade

`engine.conformity.check_conformity(template, candidate, llm=, schemas=, mapping=, dimensions=, threshold=0.85)`:

| Dimensão | LLM? | O que verifica |
|----------|------|----------------|
| `text` | sim | Wrap em `semantic_diff`. Score por contagem de severity. |
| `structural` | não | Parser `python-docx` — heading levels, tables, sections, lists. |
| `visual` | não | Render sintético via PIL + `ascii_layout` fingerprint compare. |
| `design` | sim (multimodal) | `ConformityVisualProvider.compare_documents` — fonte, cor, spacing. |
| `technical` | não | Required-field check + format validators (CPF, CEP, ISO date, etc) + zero-orphan-placeholder. |

`is_conformant = (score >= threshold) AND (zero critical failures)`. Um único critical (CPF inválido, placeholder órfão, campo perdido) reprova o doc independente do score médio.

## Por que esse formato

- **Regex primeiro, LLM como rede de segurança.** Maioria dos campos em templates reais (códigos, datas, IDs, nomes) são extraíveis mecanicamente. Pagar LLM por isso é desperdício.
- **LLM como juiz, não autor.** `semantic_diff` e dimensões de conformidade perguntam "alguma coisa sumiu?" — LLM não escreve conteúdo; ele audita.
- **Determinístico onde importa.** Detecção de schema, extração regex, render por substituição, dimensões structural / visual / technical — todas reproduzíveis bit-a-bit.
- **Local-only é garantia dura.** `local_only=True` raise antes de qualquer chamada remota. Não "confia em mim", uma exception real.

[Detalhes de arquitetura →](architecture.md)
