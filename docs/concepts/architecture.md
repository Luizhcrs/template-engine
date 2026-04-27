# Architecture

## Module map

```
engine/
├── extractor.py             docx/pdf -> ExtractedDoc (text, paragraphs, tables, header_fields)
├── schema_inference.py      detect_placeholders + enrich_with_llm + FieldSchema
├── pattern_inference.py     infer_field_patterns + grex Tier 2 + apply_inferred
├── hybrid_mapper.py         map_hybrid (regex first, LLM batched fallback)
├── batch.py                 normalize_batch orchestrator + token-substitution renderer
├── semantic_diff.py         diff_documents / diff_texts (LLM as judge)
├── confidence.py            ConfidenceLabel + calculate_confidence (structural Protocol)
├── ascii_layout.py          luminance-based layout features (no LLM)
├── cli.py                   typer CLI: info, version, extract, normalize, conformity
├── llm/
│   ├── base.py              LLMProvider Protocol + LLMError, LLMRateLimit, LLMTimeout
│   ├── router.py            LLMRouter + AllProvidersFailed
│   ├── gemini_free.py       GeminiFreeProvider
│   ├── openai_provider.py   OpenAIProvider (strict mode opt-in)
│   ├── anthropic_provider.py AnthropicProvider (tool-use coercion)
│   ├── groq_provider.py     GroqProvider (JSON mode)
│   ├── ollama_provider.py   OllamaProvider (local httpx)
│   ├── openrouter_provider.py OpenRouterProvider (subclass of OpenAI w/ base_url)
│   ├── _schema.py           normalize_for_strict (OpenAI strict mode)
│   └── _utils.py            retry_after_from_error
├── conformity/
│   ├── report.py            ConformityReport, DimensionResult, Failure
│   ├── text.py              wraps semantic_diff
│   ├── structural.py        python-docx parser + StructuralFingerprint
│   ├── visual.py            PIL render + ascii_layout fingerprint compare
│   ├── design.py            ConformityVisualProvider Protocol + check_design
│   ├── technical.py         format validators (cpf/cep/iso/...) + orphan check
│   └── aggregator.py        check_conformity top-level + weighted score
├── security/
│   ├── pii.py               mask_pii / unmask + PIIMask
│   ├── injection.py         detect_prompt_injection + 7 regex rules
│   ├── audit.py             AuditLog (append-only JSONL) + sha256_hex
│   └── local_only.py        RefusedRemoteCallError
└── section_mapper/
    ├── parser.py            parse_docx (template) / parse_docx_source (numbering-aware)
    ├── numbering.py         NumberingResolver (reads word/numbering.xml, renders markers)
    ├── similarity.py        match_string / match_embeddings / match_llm + synonym table
    ├── renderer.py          render_section_content (line-kind decoration + empty-prune)
    ├── table_filler.py      fill_tables (header-set match + subheaders)
    ├── auto_tables.py       detect_default_specs_with_source (Histórico + Resp from source)
    ├── header_filler.py     extract_source_metadata + fill_template_header
    └── orchestrator.py      map_sections / map_sections_async + SectionMappingReport
```

## Dependency graph

```
extractor ─────┐
               ├─→ schema_inference ─┐
               ├─→ semantic_diff ────┤
pattern_inference ─→ hybrid_mapper ─┤
                                    ├─→ batch (orchestrator)
                                    │
schema_inference ───────────────────┘

conformity.{text, structural, visual, design, technical} ─→ conformity.aggregator
                                                                  ↓
                                                          ConformityReport

security.{pii, injection, audit, local_only} ─→ used wherever LLM calls happen

section_mapper.{parser, numbering, similarity, renderer, table_filler,
                auto_tables, header_filler}
                                ↓
                  section_mapper.orchestrator (map_sections / map_sections_async)
                                ↓
                      SectionMappingReport
```

DAG, no cycles. Each module owns one responsibility.

## Public API surface

`engine.__init__` exports ~71 symbols. Categorized:

- **Core data:** `ExtractedDoc`, `FieldSchema`, `InferredPattern`, `MappingResult`, `BatchReport`, `ConformityReport`, `Failure`, `Discrepancy`.
- **Operations:** `extract`, `infer_field_patterns`, `apply_inferred`, `map_hybrid`, `normalize_batch`, `check_conformity`, `diff_documents`.
- **Validators:** `validate_cpf`, `validate_cep`, `validate_iso_date`, `validate_br_date`, `validate_email`, `validate_phone_br`, `validate_uf`.
- **Security:** `mask_pii`, `unmask`, `detect_prompt_injection`, `AuditLog`, `RefusedRemoteCallError`, `sha256_hex`.
- **Layout:** `image_to_ascii`, `detect_layout_features`, `summarize_layout`.
- **Section mapper:** `map_sections`, `map_sections_async`, `SectionMappingReport`, `TableSpec`, `HeadingMatch`, `NumberingResolver`, `parse_docx_source`, `extract_source_metadata`, `fill_template_header`. See the dedicated [Section mapper](section_mapper.md) page.

All public types are frozen dataclasses or Protocols — no inheritance, no mutation.

## Design decisions

### Stateless

Path / bytes in, paths / bytes / dataclasses out. The lib does not own a database, a cache, a config file, or a process. The calling app owns those. This makes it embeddable in FastAPI, CLI tools, batch jobs, Lambda handlers — same code, different shells.

### Frozen dataclasses on the public API

`MappingResult`, `Failure`, `ConformityReport`, `BatchItemResult`, `FieldSchema`, `InferredPattern`. Equality + hashing for free, no accidental mutation across pipeline boundaries, easy to serialize (`to_dict` returns plain dicts).

### Protocol-based LLM provider

`LLMProvider` is a `typing.Protocol`, not an ABC. Adding a new provider means implementing one method (`generate_structured`); no subclassing, no registry magic. Existing providers don't share a base class — they share a shape. This decouples the lib's surface from any single SDK.

### Regex tier rejects over-generalization

`pattern_inference._has_structural_anchors` requires literal punctuation or digit-class tokens before accepting a `\w`-converted pattern from grex. Without this, grex collapses `["Joao Silva", "Maria Souza"]` into `\w+ \w+`, which would match arbitrary two-word phrases. The lib falls back to free-text instead.

### `is_conformant` requires zero critical failures

A high weighted score doesn't override a single critical. Matches the regulator's mental model: "any deal-breaker = fail". Implemented at the aggregator level: `is_conformant = (score >= threshold) AND not has_critical`.

### Audit hashes, not raw content

`AuditLog` records sha256 of inputs/outputs. The audit file proves a document was processed without becoming a secondary data store. Aligns with LGPD's data-minimization principle.

### Direct token-substitution renderer

`batch._apply_mapping_to_template` does not depend on a preset bundle. It walks `python-docx` paragraphs and table cells, replacing tokens directly. No YAML render-ops layer, no LibreOffice. The output preserves the template's formatting intact.

## Operating modes

Three deployment modes, ordered by strictness:

1. **Local-only** — `llm=None, local_only=True`. Engine never contacts a network. Only regex tier runs; missing fields stay missing. Required for HIPAA, recommended for highly sensitive LGPD data.
2. **PII-masked** — wrap `mask_pii` / `unmask` around any LLM call. Personal identifiers never reach the provider.
3. **Audit-trace** — `AuditLog(path=...)` for every LLM-touching operation. Hashes of inputs/outputs preserved.

See [`SECURITY-MODEL.md`](https://github.com/Luizhcrs/template-engine/blob/main/SECURITY-MODEL.md) for the full framework guidance.

## What it explicitly does not do

- **No embedded database / cache.** Caller owns persistence.
- **No PII detection beyond patterns.** No name/address heuristics; for broader detection integrate Presidio in front of `mask_pii`.
- **No encryption at rest.** Caller owns disk encryption / KMS.
- **No multi-tenant isolation.** The lib is stateless; caller owns tenant separation.
- **No telemetry / phone-home.** The lib makes no network call besides the LLM provider explicitly supplied.

## Test coverage

189 tests across:

- providers (Gemini / OpenAI / Anthropic / Groq / Ollama / OpenRouter / Router)
- pattern_inference (Tier 1 + Tier 2 grex + label aggregation)
- schema_inference (5 placeholder syntaxes + LLM enrichment)
- hybrid_mapper (regex tier + LLM fallback batched)
- batch orchestrator (tier classification + report serialization)
- conformity (5 dimensions + aggregator + threshold)
- security (PII mask, prompt injection, audit log, local_only)

Validation suite: `ruff check . && ruff format --check . && mypy src/engine && pytest`. Passes on Python 3.11 / 3.12 / 3.13 in CI.
