# Pipeline

Two top-level operations expose the engine: **normalize** (template + N sources → N outputs) and **check_conformity** (template + 1 candidate → multi-dimensional verdict). Both share the same primitives.

## Normalization pipeline

```
template.docx                     source_dir/*.docx,*.pdf
      │                                    │
      ▼                                    ▼
┌──────────────────┐             ┌──────────────────┐
│ schema_inference │             │ extractor        │
│ FieldSchema list │             │ text + tables    │
└──────────────────┘             └──────────────────┘
      │                                    │
      ▼                                    ▼
┌────────────────────┐         ┌──────────────────────┐
│ pattern_inference  │  ─────► │ hybrid_mapper        │
│ regex per field    │         │ tier 1: regex        │
│ (10 shapes + grex) │         │ tier 2: LLM batched  │
└────────────────────┘         │ MappingResult dict   │
                               └──────────────────────┘
                                         │
                                         ▼
                               ┌──────────────────────┐
                               │ token substitution   │
                               │ render in docx copy  │
                               └──────────────────────┘
                                         │
                                         ▼
                               ┌──────────────────────┐
                               │ semantic_diff (LLM)  │
                               │ flags missing/diff/  │
                               │ extra in output      │
                               └──────────────────────┘
                                         │
                                         ▼
                               BatchReport: tier per doc
                               + per-doc summary + diffs
```

## Stages

### 1. `extract`

`engine.extractor.extract(path) -> ExtractedDoc`. Reads `.docx` (`python-docx`) or `.pdf` (`pdfplumber`). Returns text + paragraphs + tables + header_fields. Stateless. No LLM.

### 2. `schema_inference`

`engine.schema_inference.detect_placeholders(text) -> list[FieldSchema]`. Five placeholder syntaxes recognized:

| Syntax | Example | Use |
|--------|---------|-----|
| Mustache | `{{CODIGO}}` | Most common. Recommended. |
| Bracket | `[NOME]` | Form-style. |
| Chevron | `<<CLIENTE>>` | Legacy templates. |
| Named blank | `__DOC_ID__` | Underscore-wrapped. |
| Anonymous blank | `___` (3+) | Auto-named `BLANK_<n>`. |

Optional `enrich_with_llm(schemas, llm)` calls the LLM once per field to infer `field_type` (e.g. `iso_date`, `cpf`, `freetext`), `format_hint`, and `required` from surrounding context.

### 3. `pattern_inference`

`engine.pattern_inference.infer_field_patterns(gold_docs, field_examples) -> dict[field, InferredPattern]`. For each field:

1. Find example values in the gold docs, collect labels appearing before each match.
2. Aggregate labels by frequency.
3. Detect a value shape — three tiers, first match wins:
   - **Tier 1**: predefined shapes (`iso_date`, `br_date`, `doc_code`, `cpf`, `cep`, `uf`, `decimal_br`, `integer`, `version`, `fullname`, `month_year_pt`).
   - **Tier 2**: optional `grex`-learned pattern (only when structural anchors survive).
   - **Tier 3**: free-text fallback `[^\n]+`.
4. Compose `(?:label_alt_1|label_alt_2|...):\s*(value_shape)`.

`apply_inferred(inferred, text) -> dict[field, str]` extracts values from a new document.

### 4. `hybrid_mapper`

`engine.hybrid_mapper.map_hybrid(schemas, inferred_patterns, source_text, llm=None) -> dict[field, MappingResult]`. Two tiers:

- **Tier 1 (regex/grex):** runs `apply_inferred`. Each match becomes `MappingResult(value, source="regex", confidence=1.0)`.
- **Tier 2 (LLM, optional):** missing fields are batched into a single LLM call with a focused prompt + dynamic JSON Schema. Each filled field becomes `MappingResult(value, source="llm", confidence=<0-1>)`. Fields the LLM also can't fill: `MappingResult(value=None, source="missing", confidence=0.0)`.

LLM cost: 0 calls when regex resolves everything. 1 batched call when fallback runs, regardless of how many fields fall back.

### 5. Renderer

`engine.batch._apply_mapping_to_template`. Copies the template, walks paragraphs and table cells, replaces every placeholder token with the mapped value (empty string when missing). Pure `python-docx`, no LibreOffice.

### 6. `semantic_diff`

`engine.semantic_diff.diff_documents(source, output, llm, schemas=...) -> list[Discrepancy]`. Asks the LLM to compare source vs output text-only. Discrepancy types:

- `missing_in_output` — source value didn't appear in output (most common).
- `value_mismatch` — same field, different value.
- `extra_in_output` — output has content not justified by source (hallucination).

Severity: `critical` / `warning` / `info`.

### 7. Tier classification

`batch._classify_tier(mapping, discrepancies, schemas)`:

- **`high`**: required fields all came from regex AND no critical discrepancy.
- **`medium`**: any LLM-sourced field OR warning-level discrepancy.
- **`low`**: any missing required field OR any critical discrepancy.
- **`error`**: extraction or render failed.

## Conformity pipeline

`engine.conformity.check_conformity(template, candidate, llm=, schemas=, mapping=, dimensions=, threshold=0.85)`:

| Dimension | LLM? | What it checks |
|-----------|------|----------------|
| `text` | yes | Wraps `semantic_diff`. Score from severity counts. |
| `structural` | no | `python-docx` parsing — heading levels, tables, sections, lists. |
| `visual` | no | Synthetic-render via PIL + `ascii_layout` fingerprint compare. |
| `design` | yes (multimodal) | `ConformityVisualProvider.compare_documents` — fonts, colors, spacing. |
| `technical` | no | Required-field check + format validators (CPF, CEP, ISO date, etc) + zero-orphan-placeholder. |

`is_conformant = (score >= threshold) AND (zero critical failures)`. A single critical (invalid CPF, orphan placeholder, lost field) invalidates the doc regardless of weighted score.

## Why this shape

- **Regex first, LLM as a safety net.** Most fields in real templates (codes, dates, IDs, names) are mechanically extractable. Paying the LLM for those is waste.
- **LLM as judge, not author.** `semantic_diff` and conformity dimensions ask "did anything go missing?" — the LLM does not write content; it audits.
- **Deterministic where it matters.** Schema detection, regex extraction, token-substitution rendering, structural / visual / technical conformity dimensions — all reproducible bit-for-bit.
- **Local-only is a hard guarantee.** `local_only=True` raises before any remote call. Not "trust me", an actual exception.

[Architecture details →](architecture.md)
