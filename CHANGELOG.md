# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed — Wave I

- **Renderer: tokens fragmented across runs.** `batch._apply_mapping_to_template` now uses a two-pass strategy: per-run replacement (preserves intra-paragraph formatting) followed by paragraph-level fallback when a token spans multiple `<w:r>` elements (the common case in Word-edited templates). 6 new tests cover token-in-single-run, fragmented `{{X}}` across 3+ runs, multiple fragmented tokens, table cells, no-op, and direct unit on `_replace_tokens_in_paragraph`.

### Added — Wave I

- **5 new bundled formats** (10 total now): `abnt_relatorio_tecnico` (NBR 10719), `nr13` (caldeiras / vasos de pressão), `nr35` (permissão de trabalho em altura), `ata_reuniao` (genérico), `procuracao_simples` (instrumento particular).
- **`.github/workflows/publish.yml`** — automated PyPI release on `v*.*.*` tag push using PyPA trusted publishing (no `PYPI_API_TOKEN` secret needed once the project is configured at <https://pypi.org/manage/account/publishing/>).

### Removed — Wave I

- **`examples/`** moved out of the main repo to keep the lib focused. POCs continue to exist as reference but are no longer shipped with the package. Prior examples (`08`-`14`) are preserved in git history.

### Changed — Wave I

- **README/README.pt + docs/index.pt.md**: dropped any mention of specific customer numbers, paying customers, or unverified case-study figures. The cost-by-tier table remains as the only quantitative claim.
- ``__version__`` bumped to ``0.7.0``.

### Added — Wave H (bundled formats library)

- **`engine.formats`** subpackage with 5 ready-to-use document formats. Each format ships :class:`FieldSchema` list, ``field_examples`` for ``pattern_inference``, 3 gold docs, conformity weight overrides, required headings, and a recommended threshold.
  - **`abnt_artigo`** — ABNT NBR 6022:2018 (artigo cientifico). 8 fields: titulo, autores, resumo, palavras-chave, abstract, keywords, introducao, referencias.
  - **`abnt_tcc`** — ABNT NBR 14724:2024 (TCC, dissertacao, tese). 11 fields: titulo, autor, orientador, instituicao, curso, ano, local, resumo, abstract, palavras-chave, keywords. Required headings: RESUMO, ABSTRACT, SUMARIO, INTRODUCAO, CONCLUSAO, REFERENCIAS.
  - **`abnt_referencia`** — ABNT NBR 6023:2018 (referencia bibliografica). 7 fields, near-perfect threshold 0.90 — useful as a standalone validator for reference lines.
  - **`laudo_nr12`** — NR-12 (Portaria MTE), laudo de seguranca em maquinas. 11 fields: empresa, cnpj, endereco, equipamento, tag, fabricante, NS, data, responsavel, CREA, conclusao. Conformity weights emphasize ``technical`` (0.45) since CNPJ + CREA + dates must validate.
  - **`contrato_simples`** — contrato bilateral generico. 10 fields: titulo, contratante, cnpj_contratante, contratada, cnpj_contratada, objeto, valor, vigencia, foro, data_assinatura.
- **`load_format(name) -> Format`**, **`list_formats() -> list[str]`**, **`describe_formats() -> list[dict]`**. Raises ``FormatNotFound`` on unknown name.
- **CLI `template-engine list-formats`** — rich table with name / spec / field count / title.
- **CLI `--format <name>`** flag added to `normalize` and `conformity`. When supplied, the bundled format provides gold docs + field examples (normalize) or conformity weights + recommended threshold (conformity).
- 44 new unit tests (189 → **233 passing**) covering registry, shape sanity, gold-coverage, pattern_inference integration, and per-format quirks.

### Changed

- ``__version__`` bumped to ``0.6.0``.
- README/quickstart docs add a bundled-formats example.

### Added — Wave G (security primitives for regulated deployments)

- **`engine.security.mask_pii(text)`** — reversible PII masking. Replaces CPF / CNPJ / email / phone (BR) / RG / CEP with stable tokens (``<CPF_001>`` etc). Returns ``(masked_text, PIIMask)``. Repeated occurrences of the same value reuse the same token. ``mask.unmask(text)`` restores originals.
- **`engine.security.detect_prompt_injection(text, mode='warn'|'reject')`** — pattern-based detector for adversarial inputs. 7 rules covering EN + PT-BR ("ignore previous", "respond only with", role hijack, system override, delimiter injection). ``mode='reject'`` raises ``PromptInjectionDetected``.
- **`engine.security.AuditLog(path)`** — append-only JSON Lines audit trail. Fixed schema: ``ts``, ``event``, ``doc_hash``, ``dimension``, ``source``, ``llm_provider``, ``llm_model``, ``fields_touched``, ``llm_input_hash``, ``llm_output_hash``, ``extra``. Records sha256 hashes — never raw content. Thread-safe per instance.
- **`engine.security.sha256_hex(text)`** — convenience helper for audit hashes.
- **``local_only=True``** flag on ``normalize_batch`` and ``check_conformity``. Raises ``RefusedRemoteCallError`` if any LLM provider is supplied. Hard guarantee for LGPD/HIPAA deployments.
- **``SECURITY-MODEL.md``** — threat model, operating-mode matrix, provider data residency table, reproducibility guarantees, framework guidance (LGPD/HIPAA/SOC2/ISO).
- 26 new unit tests for security (163 → **189 passing**).

Public API exports added: ``AuditLog``, ``InjectionMatch``, ``PIIMask``, ``PromptInjectionDetected``, ``RefusedRemoteCallError``, ``detect_prompt_injection``, ``mask_pii``, ``sha256_hex``, ``unmask``.

### Changed

- ``__version__`` bumped to ``0.5.0`` (Wave G ships security primitives).
- README rewritten — leads with the differential ("audit-grade, regex-first, LLM-as-judge, zero LibreOffice"), adds an ASCII pipeline diagram, an operating-cost table by tier, and a "Design decisions" section. PT-BR mirror updated.

### Added — Wave F (conformity validator multi-dim)

LLM-as-judge multi-dimensional conformity check. Subpackage ``engine.conformity`` with five dimensions:

- **text** — wraps ``engine.semantic_diff``. Score derived from severity counts. LLM call.
- **structural** — ``python-docx`` parsing. Counts headings by level, tables, sections, list paragraphs. Pure deterministic, zero LLM.
- **visual** — synthetic-render via PIL + ``ascii_layout`` fingerprint compare. Skipped gracefully when Pillow is absent. Zero LLM, no LibreOffice.
- **design** — multimodal LLM compare via new ``ConformityVisualProvider`` Protocol. Receives both ``.docx`` paths directly (no PNG render, no LO). Skipped when no provider supplied.
- **technical** — required-field check + format validators (``cpf``, ``cep``, ``iso_date``, ``br_date``, ``email``, ``phone_br``, ``uf``) + zero-orphan-placeholder check. Pure deterministic.

Top-level entry: ``engine.conformity.check_conformity(template_path, candidate_path, *, llm, visual_llm, schemas, mapping, candidate_text, dimensions, weights, threshold)`` returns a :class:`ConformityReport`.

**``is_conformant`` rule:** ``score >= threshold`` AND zero critical failures. A single critical (invalid CPF, orphan placeholder, lost field) invalidates the doc regardless of average.

CLI: ``template-engine conformity --template T --candidate C --provider gemini --dimensions text,structural,visual,design,technical --threshold 0.85 --json report.json``. Rich tables show per-dimension score + verdict + failure list.

32 new tests (131 → **163 passing**).

Public exports added to ``engine``: ``ConformityReport``, ``ConformityVisualProvider``, ``DimensionResult``, ``Failure``, ``StructuralFingerprint``, ``check_conformity``, ``check_text``, ``check_structural``, ``check_visual``, ``check_design``, ``check_technical``, ``find_orphan_placeholders``, ``validate_cpf``, ``validate_cep``, ``validate_iso_date``, ``validate_br_date``, ``validate_email``, ``validate_phone_br``, ``validate_uf``.

### Removed — Wave E (consolidation, BREAKING)

Drops the legacy preset-bundle pipeline in favor of the Wave D schema-driven path. **Breaking change.** Users on the old pipeline must migrate to ``template-engine normalize``.

- **Source modules dropped:** ``engine.preset_creator``, ``engine.preset_loader``, ``engine.preset_schemas``, ``engine.renderer``, ``engine.render_ops/`` (entire package), ``engine.validator``, ``engine.visual_validator``, ``engine.llm_mapper``.
- **LLM module dropped:** ``engine.llm.gemini_vision`` and ``engine.llm.base.VisualLLMProvider`` Protocol. (Will return in Wave F under a different name for the conformity validator design dimension.)
- **CLI commands dropped:** ``template-engine convert`` and ``template-engine visual-validate``. Replacement: ``template-engine normalize``.
- **Optional extras dropped:** ``[visual]`` (was ``pdf2image`` + ``pillow``). New ``[poc]`` extra exposes ``pillow`` for the example POC scripts.
- **Examples dropped:** ``examples/01_quickstart.py``, ``examples/02_custom_provider.py``, ``examples/03_validation.py``, ``examples/04_ascii_layout_poc.py``. POCs 08-14 (Wave A demos) preserved.
- **Tests dropped:** ``test_preset_creator``, ``test_preset_loader``, ``test_renderer``, ``test_validator``, ``test_visual_validator``, ``test_llm_mapper``. Total tests: 172 → **131 passing**.
- **Docs pages dropped:** ``concepts/preset.{md,pt.md}``, ``concepts/render-ops.{md,pt.md}``, ``concepts/visual-validation.{md,pt.md}``.

### Migration guide

Old pipeline → Wave D:

```python
# Before (legacy)
from engine import create_preset, load_preset, map_content, render
preset = await create_preset(template_path, gold_paths, llm)
data = await map_content(preset, source_text, llm)
render(preset, data, output_path)

# After (Wave D)
from engine import normalize_batch
report = await normalize_batch(
    template_path=template_path,
    source_dir=source_dir,
    output_dir=output_dir,
    llm=llm,
    gold_docs=[extract(p).text for p in gold_paths],
    field_examples=examples_dict,
)
```

Old CLI → new CLI:

```bash
# Before
template-engine convert source.docx --preset preset_dir --output out.docx
template-engine visual-validate gold.docx output.docx

# After
template-engine normalize --template template.docx --source-dir docs/ --output-dir out/
# (visual validation returns in Wave F as part of conformity check)
```

### Changed

- **`engine.confidence`** decoupled from `engine.validator`. ``calculate_confidence`` now accepts any object exposing ``critical_tokens_found/total`` and ``sections_present/required`` via a structural Protocol (no more hard import).
- **`__version__`** bumped to ``0.3.0`` (Wave E completes the v0.3 milestone).
- **LOC stats:** src 4594 → 3045 (-34%), tests 2655 → 1884 (-29%), total py 9897 → 7329 (-26%).


### Added — Wave A (regex inference)

- **`engine.pattern_inference`** — `infer_field_patterns(gold_docs, field_examples) -> dict[str, InferredPattern]` synthesizes a regex per field from gold docs + example values. Three-tier value-shape detection:
  1. **Predefined shapes** (Tier 1): `iso_date`, `br_date`, `doc_code`, `cpf`, `cep`, `uf`, `decimal_br`, `integer`, `version`, `fullname`, `month_year_pt`.
  2. **grex-learned shapes** (Tier 2, optional dep `[inference]`): `RegExpBuilder.from_test_cases(...).with_conversion_of_digits().with_conversion_of_words()` — generalizes `\d` and `\w` while preserving structural anchors (literal hyphens / digit classes). Hybrid policy rejects pure literal alternations (`(?:cat|dog|fox)`) and over-permissive `\w+` whose only anchor is whitespace.
  3. **Free-text fallback** (Tier 3): `[^\n]+` when neither tier produces a meaningful regex.
- **`apply_inferred(inferred, text) -> dict[str, str]`** — applies the synthesized regexes to a new document.
- **POCs 08-13 refactored** — `_FIELD_PATTERNS` hardcoded substituído por `infer_field_patterns(_GOLD_DOCS, _FIELD_EXAMPLES)`. 49/49 fields extracted across 6 designs (laudo / contrato / branded / creative / minimalist / form). Zero LLM in extraction path.
- **`[inference]` extra** — `grex>=1.0,<2`. Install via `pip install 'template-engine[inference]'`.
- 24 new unit tests for pattern_inference (110 → 116 total).

### Added — Wave D (batch orchestrator)

- **`engine.schema_inference`** — `detect_placeholders(template_text) -> list[FieldSchema]` recognizes 5 placeholder syntaxes: mustache `{{X}}`, single brace `{X}`, bracket `[X]`, chevron `<<X>>`, named-blank `__X__`, anonymous-blank `___`. Optional `enrich_with_llm(schemas, llm)` calls LLM per field to infer `field_type`, `format_hint`, `required` from surrounding context. `infer_template_schema(template_path, llm=...)` is the top-level entry point.
- **`engine.hybrid_mapper`** — `map_hybrid(schemas, inferred_patterns, source_text, llm=None)` runs regex first via `apply_inferred`; the missing fields are batched into a single LLM call (when `llm` is supplied) with a focused prompt + dynamic JSON Schema. Output: `dict[str, MappingResult]` with `value`, `source ∈ {regex, llm, missing}`, `confidence ∈ [0,1]`, optional `notes`. Helper `summarize(results)` returns aggregate stats.
- **`engine.semantic_diff`** — `diff_documents(source_path, output_path, llm=...)` and `diff_texts(source_text, output_text, llm=...)` ask the LLM to surface `missing_in_output` / `value_mismatch` / `extra_in_output` discrepancies with `critical` / `warning` / `info` severity. Text-only — no LibreOffice required. `filter_by_severity(...)` for downstream filtering.
- **`engine.batch`** — `normalize_batch(template_path, source_dir, output_dir, llm=..., gold_docs=..., field_examples=..., enable_semantic_diff=..., max_concurrent=...)` end-to-end orchestrator. Async parallel processing with `asyncio.Semaphore`. Direct token-substitution renderer (`_apply_mapping_to_template`) avoids the legacy preset bundle. Returns `BatchReport` with per-doc `BatchItemResult` (mapping, discrepancies, tier, error). Tier classification: `high` (regex resolved everything, no critical diff) / `medium` (LLM filled or warning-level diff) / `low` (missing required field or critical diff) / `error`. `BatchReport.to_dict()` is JSON-serializable for `report.json`.
- **CLI `template-engine normalize`** — wires the full pipeline. Flags: `--template`, `--source-dir`, `--output-dir`, `--provider` (omit for regex-only), `--gold-doc` (repeatable), `--field-examples` (JSON file), `--report`, `--skip-diff`, `--max-concurrent`. Prints rich summary table by tier, writes `report.json`.
- 55 new unit tests across schema_inference (19) + hybrid_mapper (12) + semantic_diff (12) + batch (12). Total: 116 → **172 passing**.

### Added — Visual validation (legacy, to be deprecated in Wave E)

- **Visual validation** — `engine.visual_validator.validate_visual()` compares a rendered `.docx` against a gold reference using a multi-modal LLM. Pipeline: LibreOffice headless (`.docx` → PDF) + `pdf2image` (PDF → PNG) + LLM call with structured schema. Returns `VisualValidationResult` with 0-1 score, categorized issues (alignment / spacing / typography / section_order / other), severity (low/medium/high), and rendered images for inspection.
- **`GeminiVisionProvider`** — multi-modal provider in `engine.llm.gemini_vision`. Implements `VisualLLMProvider` Protocol. Reuses existing `[gemini]` extra (no new dep).
- **`VisualLLMProvider`** Protocol added to `engine.llm.base` (text providers untouched).
- **`engine.docx_to_png(path, out_dir, dpi)`** — public helper for raster previews.
- **CLI command** `template-engine visual-validate <gold> <output> --api-key X`.
- **`[visual]` extra** — `pdf2image` + `pillow`.

### Changed

- `__version__` bumped to `0.3.0a1` (alpha — Wave D + visual validator APIs may evolve before v0.3 stable).
- Pipeline core continues to require **zero LibreOffice**. Only `visual_validator` legacy uses it; replacement (Wave F design dimension via direct multimodal upload) is in roadmap.

## [0.2.1] - 2026-04-26

### Fixed

- **CRITICAL** — `OpenAIProvider` no longer crashes with `BadRequestError: Invalid schema` when `strict=True` was incorrectly enabled by default. Strict is now opt-in (`strict=False` default); when enabled, the provider auto-normalizes the schema via `engine.llm._schema.normalize_for_strict` (recursive `additionalProperties: false` + populate `required`).

### Changed

- **Breaking (soft):** `PresetManifest.owner_sub` renamed to `PresetManifest.owner`. Manifests still containing `owner_sub` are auto-promoted via Pydantic `model_validator` for backwards compatibility through v0.3. The `owner_sub` field will be removed in v0.4.
- **Deprecated:** `engine.preset_loader.list_user_presets(data_dir, user_sub)` — use `list_presets_for_owner(base_dir, owner)` instead. Old function still works but emits `DeprecationWarning`. Removal in v0.4.
- Internal helper `_retry_after_from_error` moved from `openai_provider.py` to `engine.llm._utils.retry_after_from_error` (sibling providers no longer cross-import private symbols).
- Removed empty `docs/overrides/` directory and orphan `version.provider: mike` from `mkdocs.yml`.

### Added

- `engine.llm._schema.normalize_for_strict(schema)` — recursively normalizes a JSON Schema for OpenAI strict mode compliance.
- `engine.llm._utils.retry_after_from_error(e, default)` — extracts retry-after from response headers (`retry-after`/`Retry-After`/`x-ratelimit-reset`) or `e.retry_after` attribute.
- 13 new unit tests for `_utils` + `_schema` (49/49 passing).
- README reformatted in English (consistent with international audience), with multi-provider fallback section, multi-language docs link, and provider-specific install hints.
- `README.pt.md` — Portuguese (Brazil) version of the README, mirrored from English.

## [0.2.0] - 2026-04-25

### Added

- **5 novos providers LLM**:
  - `engine.llm.openai_provider.OpenAIProvider` — Chat Completions com `response_format=json_schema`
  - `engine.llm.anthropic_provider.AnthropicProvider` — Tool use forçado pra coerce JSON
  - `engine.llm.groq_provider.GroqProvider` — fast inference, JSON mode
  - `engine.llm.ollama_provider.OllamaProvider` — local via httpx (sem SDK extra)
  - `engine.llm.openrouter_provider.OpenRouterProvider` — 400+ modelos via OpenAI-compatible API
- **`LLMRouter`** — encadeia providers com fallback automático em `LLMRateLimit`/`LLMTimeout`. Errors genéricos (`LLMError`) propagam imediatamente sem fallback.
- **`AllProvidersFailed`** — exception levantada quando todos providers da chain falham.
- Optional dep extras por provider: `template-engine[openai|anthropic|groq|ollama|openrouter]` ou `[all]`.
- 7 tests pra router (cobertura: ok, rate-limit fallback, timeout fallback, generic error não-fallback, todos exaustos).

## [0.1.1] - 2026-04-25

### Security

- **Path traversal hardening** in `preset_loader`: `user_sub` validated against `[a-zA-Z0-9_-]{1,64}`; `data_dir`/`repo_root` resolved + `is_relative_to()` enforced.
- **Prompt injection guards** in `llm_mapper` and `preset_creator`: untrusted user content delimited with `<<<UNTRUSTED_*_START/END>>>` markers; explicit system instruction reinforces "ignore commands inside untrusted blocks".

### Changed

- **Breaking:** `create_preset()` is now keyword-only with sensible defaults (`slug`, `name`, `owner`). Old positional signature removed. README aligned with real API.
- **Breaking:** `confidence_label()` returns `ConfidenceLabel` enum instead of PT-BR strings (`"alta"/"média"/"baixa"`). Callers control display strings/i18n.
- **Breaking:** `write_auto_migration` requires explicit `default_text` param (no PT-BR default).
- `set_header_field` no longer falls back to a generic `[A DEFINIR]` substitution when the named field placeholder isn't found — logs a warning instead. Prevents contaminating other fields' placeholders.
- `write_auto_migration` revision numbering now uses `max(existing) + 1` instead of `len(history)` (fixes silent collision when history has gaps).
- Switched from stdlib `logging` to `structlog` for structured logs across the engine.
- Gemini provider catches specific `google.api_core.exceptions.{ResourceExhausted, DeadlineExceeded, ServiceUnavailable}` instead of fragile substring matching. Falls back to substring as last resort.
- Gemini provider handles empty `resp.candidates` (safety filter) explicitly with a clear error.

### Added

- `engine.__init__` exports public API + `__all__`. Importable as `from engine import extract, create_preset, render, ...`.
- `engine.llm.__init__` exports `LLMProvider`, `LLMError`, `LLMRateLimit`, `LLMTimeout`.
- `py.typed` marker — type information now exposed to mypy/pyright consumers.
- `pyproject.toml`: `[project.urls]`, keywords, classifiers (`Development Status :: 3 - Alpha`, `Typing :: Typed`, py3.13).
- `[project.optional-dependencies]` `gemini` extra — install with `pip install template-engine[gemini]` for Gemini support. Core install is provider-agnostic.

### Fixed

- README quickstart now matches the real `create_preset` async API.

## [0.1.0] - 2026-04-25

### Added

- Initial public release. Pipeline: extractor → preset_creator → llm_mapper → validator → renderer.
- 29 tests passing.
- Apache 2.0 license.
- Gemini Free provider.

[Unreleased]: https://github.com/Luizhcrs/template-engine/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/Luizhcrs/template-engine/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/Luizhcrs/template-engine/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/Luizhcrs/template-engine/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Luizhcrs/template-engine/releases/tag/v0.1.0
