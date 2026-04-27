# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.10.0] - 2026-04-27 — Wave M (LLM-driven full-doc mapping)

The Wave L pipeline relied on hardcoded vendor heuristics: Engeman
placeholder names, Brazilian-PT synonym table, canonical Histórico /
Responsabilidade extractors, regex-based `Aprovador (es):` /
`IT.PRO.URE.387.0005` parsers, etc. That worked for one vendor's
templates; it did not generalise.

Wave M ships a vendor-agnostic LLM-driven mode that handles ANY template
+ source pair the LLM can read.

### Added — generic profilers

- **`engine.section_mapper.template_profiler`** —
  `profile_template(path)` returns a vendor-agnostic
  `TemplateStructure` carrying:
  - Headings (re-used from `parse_docx`).
  - Placeholders detected by SHAPE (not by name): `XXXX` repeated
    chars, `(TITULO)` parenthesised labels, `[FOO]` brackets, `{{X}}`
    curly tokens, `___` underscore runs, `Label:` empty-suffix labels,
    `Rev. 00` revision-like literals. Header / footer placeholders are
    detected even inside `<w:txbxContent>` text boxes that
    python-docx's iterators skip.
  - Empty tables: any table with at least one fully-blank data row
    after the header(s).
- **`engine.section_mapper.source_profiler`** — `profile_source(path)`
  bundles sections (with auto-numbering already resolved when the
  source is `.docx`), tables, and the source's header text in two
  flavors (glued for dotted document codes, spaced for multi-word
  titles).

Both structures are JSON-serialisable.

### Added — LLM mapper

- **`engine.section_mapper.auto_mapper.build_mapping_plan(template,
  source, *, llm)`** — issues ONE batched LLM call that returns a
  complete `MappingPlan`:
  - `header_substitutions: dict[placeholder_text, replacement]`
  - `section_content: dict[heading_canonical, body_text]`
  - `table_data: list[TableFillData]` (per-template-table rows)
- The schema is JSON-Schema strict; required keys come from the
  detected placeholders + headings so the LLM is forced to address
  every detected slot. Failure (provider error / schema mismatch)
  returns an empty plan so callers can fall back to rules-mode.

### Added — auto renderer

- **`engine.section_mapper.auto_renderer.apply_mapping_plan(template,
  output, *, plan, template_struct)`** — materialises the plan: section
  content via `render_section_content`, tables via `fill_tables` with
  synthesised `TableSpec`s anchored by `template_table_index`, header
  placeholders via run-preserving substitution in every
  `word/header*.xml`.

### Added — orchestrator `mode` flag

- `map_sections_async` gains a `mode: str = "rules"` parameter:
  - `"rules"` (default) — Wave L pipeline, free, deterministic, but
    Engeman / PT-BR specific.
  - `"llm"` — single LLM call builds the complete substitution plan
    from the profilers. Generalises across vendors and languages.
    Requires a provider.
  - `"hybrid"` — runs rules first, then asks the LLM to plug whatever
    gaps the rules left behind (untouched header placeholders, empty
    tables the auto-detector did not recognise, content for sections
    still empty). Requires a provider.
- `map_sections` (sync) stays rules-only. Use `map_sections_async` for
  LLM / hybrid modes.

### Tests

7 new unit tests covering profilers + mapper + renderer paths
(351 → **358 passing**).

### Cost ballpark (Gemini Flash 2.5)

| Mode | LLM calls | $/doc |
|---|---|---|
| `rules` | 0 | **$0.0000** |
| `hybrid` | 1 (only when rules left gaps) | ~$0.0010 |
| `llm` | 1 (always) | ~$0.0010 |

Use `rules` when the regulator demands bit-for-bit reproducibility,
`hybrid` for best of both worlds, `llm` when the template / source pair
is too far from the rules' Engeman heuristics.

## [0.9.7] - 2026-04-27

### Added — header filler

The template's header carries placeholders the previous releases never
touched: ``XXXX`` (document code), ``Rev. 00`` (revision), ``Elaborado:``
(author), ``Aprovado:`` (approver), ``Data:`` (date), ``(TITULO)``
(title). Industrial templates ship these blank so the orchestrator was
producing valid body text under a placeholder header.

#### New module — `engine.section_mapper.header_filler`

- ``extract_source_metadata(source_path)`` reads the source ``.docx``
  header (fragmented runs reassembled in two flavors: glued for dotted
  document codes, spaced for multi-word titles) plus the body's
  revision-history table; returns a ``HeaderMetadata`` record.
- ``fill_template_header(output_path, metadata)`` walks every
  ``word/header*.xml`` inside the docx zip and substitutes each
  placeholder inline (run-preserving), saving back to the same file.

Document-code extraction handles the common case where the source
fragments the code across many ``<w:t>`` elements (``IT.PRO.`` + ``U`` +
``RE`` + ``.387.0005``) AND the surrounding text glues a company tag in
without a word boundary (``...TRABALHOIT.PRO.URE.387.0005...``). The
prefix is located in the spaced flavor (where each run sits between
spaces), then a state-machine walk over the glued flavor consumes the
full code until a letter→digit boundary breaks the segment kind.

#### Orchestrator wiring

Both ``map_sections`` and ``map_sections_async`` call the header filler
after table fill. When source metadata is missing for a placeholder,
the placeholder is left in place so a downstream reviewer can spot the
gap.

### Tests

3 new unit tests (348 → **351 passing**):

- ``test_extract_document_code_handles_run_split_prefix`` — synthetic
  glued/spaced pair; expects ``IT.PRO.URE.387.0005`` not the truncated
  ``PRO.URE.387.0005``.
- ``test_extract_source_metadata_engeman_pair`` — end-to-end on a
  synthetic source carrying every recognised field.
- ``test_fill_template_header_substitutes_placeholders`` — substitution
  asserts, including replaced-not-duplicated placeholder.

### Result on Engeman dados.docx

Header before:

    XXXX           Rev. 00       Elaborado:        Aprovado:        Data:
    ENGEMAN ...                              (TITULO)

Header after:

    IT.PRO.URE.387.0005    Rev. 01    Elaborado: Marcos Britto
    Aprovado: Fabiano Roberto Gomes Arce    Data: 2026-04-27
    ENGEMAN ...                  (PARTIDA DA ÁREA DE SÍNTESE)

Matches DOcStream's reference output.

## [0.9.6] - 2026-04-27

### Fixed — sub-headings turning blue

v0.9.5 applied Word's ``Ttulo2`` / ``Ttulo3`` styles for sub-headings so
they would inherit Heading-2/3 spacing. Side-effect: those styles
default to blue, which is wrong for industrial-procedure documents that
expect black bold sub-headings throughout.

The renderer now applies decoration via direct formatting only — no
``<w:pStyle>`` reference:

- Bold run + explicit black color (``w:color w:val="000000"``).
- Paragraph spacing: ``before=240`` twips / ``after=120`` for
  ``X.Y.`` sub-headings, ``before=180`` / ``after=80`` for
  ``X.Y.Z.`` sub-sub-headings.

This keeps the visual hierarchy (bold + visible breaks before/after)
without inheriting any heading-style color theme.

### Tests

`test_renderer_applies_subheading_direct_formatting` asserts the output
XML carries direct ``<w:b/>`` + ``w:val="000000"`` + ``w:before=`` but
NOT the ``Ttulo2`` / ``Ttulo3`` style refs.

**348 passing**.

## [0.9.5] - 2026-04-27

### Fixed — paragraph styling for sub-headings + notes

In Word the v0.9.4 output looked dense and visually flat: every line in
a section inherited the anchor body slot's plain-Normal style, so
sub-section markers like ``6.1. Condições Gerais`` and
``6.2.1. Ações Preliminares`` rendered as ordinary body text without
bold or spacing — the document read as a wall of paragraphs instead of
a hierarchy.

The renderer now classifies each inserted line by its prefix and
applies the right style:

- ``6.1. Foo`` (one dotted level) → ``Ttulo2`` style + bold run.
- ``6.2.1. Bar`` (two or three dotted levels) → ``Ttulo3`` + bold run.
- ``Nota: ...`` / ``Nota 1: ...`` / ``Nota1: ...`` → italic run.
- Anything else (list items, body sentences) → unchanged.

Word's ``Ttulo2`` / ``Ttulo3`` (Brazilian-PT Heading 2/3) carry their
own spacing-before / -after, so sub-headings now sit in proper visual
breaks instead of glued to the surrounding paragraphs.

When a clone inherits style or emphasis from the previous line, the
renderer resets it before applying the next line's decoration, so a
heading isn't propagated into the body line that follows.

### Tests

6 new unit tests covering line-kind detection (sub-heading,
sub-sub-heading, nota, body, value-with-dot non-matching), plus an
end-to-end assertion that ``Ttulo2`` / ``Ttulo3`` show up in the output
XML when sub-headings are present.

**348 passing** (342 → 348).

## [0.9.4] - 2026-04-27

### Fixed — vertical-gap regression

The renderer was leaving every unused empty body slot in place, so
sections that filled less content than the template reserved (and the
HISTÓRICO tail beyond the last heading) showed as long blank runs in
Word. Output had 185 paragraphs vs DOcStream's 180; 24 were empty (vs
DOcStream's 10).

Two new post-render passes:

- **Prune unused body slots**: after inserting content, walk the
  siblings of the last filled anchor; delete every empty paragraph up
  to the next heading. Catches the per-section trailing blank slots.
- **Collapse empty-paragraph runs**: walk the document body once;
  whenever 2+ consecutive empty paragraphs appear at the same nesting
  level, drop all but the first. Catches the HISTÓRICO tail (no next
  heading to stop at) and any other long blank run. Paragraphs inside
  table cells are left alone — cell layout depends on paragraph count.

### Result on Engeman dados.docx

| Aspect | v0.9.3 | v0.9.4 | DOcStream |
| --- | --- | --- | --- |
| Total paragraphs | 185 | 172 | 180 |
| Empty paragraphs | 24 | 11 | 10 |
| Empty slots between filled section and next heading | yes | gone | gone |
| Empty paragraphs after last heading (HISTÓRICO tail) | 11 | 1 | 1 |

### Tests

1 new test (`test_renderer_collapses_consecutive_empty_paragraphs`),
**342 passing**.

## [0.9.3] - 2026-04-27

### Added — DOcStream-style heuristics for industrial templates

The faithful Phase 1 path (v0.9.2) preserved decimal sub-section markers
and bullets. This release closes the remaining visible gaps against
DOcStream's reference output on Engeman procedure documents:

#### Bullet → letter sequences (per-list reset)

`NumberingResolver.bullet_as_letters` (default `True`) renders bullet
items at ilvl=0 as Excel-style letters (`a.`, `b.`, ..., `z.`, `aa.`).
The parser calls `reset_bullet_counters()` whenever a structural
decimal heading advances (any non-bullet marker), so each sub-section
restarts its lettering at `a.` instead of continuing across boundaries.

#### Reference-list auto-bullet

Sections named `NORMAS`, `REGISTROS`, `ANEXOS`, `DOCUMENTOS DE
REFERÊNCIA`, etc. routinely list items as plain paragraphs without
`<w:numPr>`. Post-process prepends `"• "` to every line that doesn't
already carry a marker.

#### Definitions: `:` → en-dash

In `DEFINIÇÕES` / `DEFINIÇÕES SIGLAS` sections, leading `term: ` is
converted to `term – ` (en-dash). Term matcher accepts up to 3 short
tokens (so `Loop teste:` matches; sentence-style colons do not).

#### Source-driven Histórico table

`detect_default_specs_with_source(template, source)` extracts the
source's revision-history table (any of `VERSÃO|DATA|AUTOR|ALTERAÇÕES`
columns), renumbers from `00`, and appends a final `"Migração para o
novo modelo padrão"` row dated today.

#### Source-driven Responsabilidade table

When the source carries `Compete à gerência` / `Compete aos
supervisores` sub-sections, the orchestrator extracts each child
paragraph as an activity and emits a `TableSpec` whose rows tag `X` in
the correct column (`Gerente Setorial` / `Supervisores`). Bucket
boundaries are detected via `<w:numPr>` ilvl, so the extractor doesn't
spill into the next top-level section.

#### `TableSpec.subheaders`

New optional field. When set, `fill_tables` writes the sub-headers into
row 1 of the matched table and uses them for column mapping when the
primary header row has duplicates (e.g. `Atividades |
Responsabilidade | Responsabilidade`).

#### Tabular section content suppression

When an auto-table fills the data for a target section (Responsabilidade
/ Histórico), the orchestrator drops the prose body for that section so
the same info doesn't appear twice (once as text, once in the table).

### Tests

12 new unit tests (328 → **341 passing**) covering bullet-as-letters,
counter reset, post-transforms, history-column classification, and
sub-header writing in `fill_tables`.

### Result against the Engeman dados.docx pair

| Aspect | v0.9.2 | v0.9.3 |
| --- | --- | --- |
| `NORMAS` reference list bullets | dropped | `• <ref>` per line |
| `DEFINIÇÕES` separator | `term: prose` | `term – prose` |
| Bullet sub-items under sub-section | `•` | `a.`, `b.`, `c.`, ... |
| Letter reset between sub-sections | continuous (`a-z-aa`) | resets per sub-section |
| Histórico table | 1 default row | source revisions + migração row |
| Responsabilidade table | empty 5 rows | activity per row + X by role |
| RESPONSABILIDADE prose duplication | yes | suppressed (table-only) |

## [0.9.2] - 2026-04-27

### Added — section_mapper preserves source `.docx` auto-numbering

When the source is a Word document, headings, sub-sections and list items came out unnumbered because Word resolves `<w:numPr>` against `word/numbering.xml` at render time. Plain-text extraction loses everything: a paragraph whose XML says "this is the first item under numId=1, ilvl=0" carries the text `"OBJETIVO"` — the rendered marker `"1."` exists only in Word's view.

Output diff against the first real-world Engeman procedure pair:

| Aspect | Before (v0.9.1) | After (v0.9.2) |
| --- | --- | --- |
| Sub-section markers (`6.1.`, `6.2.1.`) | dropped | preserved as text prefix |
| List markers (`•`) | dropped | preserved (faithful to numFmt) |
| Source paragraph order | preserved | preserved |

Top-level section markers (`1. OBJETIVO`) still come from the template's own numbering — the template's `<w:numPr>` is preserved and Word renders them when the output is opened.

#### New module — `engine.section_mapper.numbering`

- `NumberingResolver` — reads `word/numbering.xml`, walks paragraphs and returns the rendered marker for each `<w:numPr>` paragraph. Stateful counters per `numId`; advancing one level resets every deeper level.
- Faithful to `numFmt`: `decimal`, `lowerLetter`, `upperLetter`, `lowerRoman`, `upperRoman` resolved against `lvlText` placeholders (`%1.`, `%1.%2.%3.`, `%4)`). `bullet` collapses to a portable `"•"` regardless of source glyph (Wingdings/Symbol).
- `load_resolver_from_docx(path)`, `extract_num_pr(p_xml)` helpers.
- Exported from `engine.section_mapper.__init__`.

#### New parser — `parse_docx_source(path)`

Routes `.docx` source through the resolver. Returns `list[TextSection]` whose `content` lines carry the rendered marker (`"5.1. Compete à gerência"`, `"• Todas as utilidades..."`) and whose `raw_heading` of each section is also numbered (`"1. OBJETIVO"`).

#### Orchestrator routing

`map_sections` and `map_sections_async` detect `source_path.suffix == ".docx"` and route through `parse_docx_source`; everything else (PDF, txt, etc) keeps the existing `extract → parse_text` path because Word has already rendered the numbering into the text.

### Tests

9 new unit tests in `tests/test_section_mapper.py` (319 → 328 passing) covering the resolver (decimal / nested decimal / lowerLetter / bullet collapse / Excel-style letter sequence / Roman / unknown numId / paragraph numPr extraction / end-to-end `parse_docx_source` against a synthetic source).

## [0.9.1] - 2026-04-27

### Changed — section_mapper goes zero-config

- `similarity_mode` default flipped from `"string"` to `"auto"`. Auto runs string first, falls back to embeddings (when the optional `[embeddings]` extra is installed) when target coverage is < 60%. The async path adds an LLM tier when a provider is supplied AND the heuristic chain still falls short.
- New `auto_tables=True` default (both sync and async). Walks the template, detects canonical empty tables (Histórico Rev/Data/Alteração) and synthesizes a sane `TableSpec` so callers don't need to configure them. User-supplied specs still win over auto-detected ones (matched by header set).
- New module `engine.section_mapper.auto_tables` exports `detect_default_specs(template_path)` and `merge_specs(auto, user)`.
- Synonym table expanded to cover wording variations seen on the first real-world Engeman pair: `ABRANGENCIA`, `DETALHAMENTO`, `REGISTROS`, `RESPONSABILIDADES AUTORIDADES`, `HISTORICO DE REVISAO`, `DEFINICOES SIGLAS`.

Result on Engeman dados.docx with zero config: mapped **7/8** (was 5/8 with manual synonym additions); empty Histórico table auto-filled with default first row.

### Added — Wave L (section_mapper for structural templates)

New subpackage `engine.section_mapper` covers the case the existing pipeline did not: templates that ship with named-but-empty sections (no `{{X}}` placeholders) and rely on heading hierarchy + tables. Validated against an industrial procedure template (Engeman / NR-style) that the Wave D `normalize_batch` could not handle.

- **`engine.section_mapper.parser`** — heading detection from `.docx` (paragraphs + heading styles + numbered + all-caps unnumbered) and from plain text (PDF-extracted). Returns `DocxSection` with paragraph indices and `TextSection` with captured content.
- **`engine.section_mapper.similarity`** — three-tier matcher:
  - **string** (default, zero deps): exact + curated synonym table + Jaccard token overlap with stop-word filtering. Maps `DESCRIÇÃO -> SISTEMÁTICA`, `REGISTROS -> RESPONSABILIDADE`, `ESCOPO -> APLICAÇÃO` out of the box.
  - **embeddings** (optional `[embeddings]` extra, `sentence-transformers`): cosine similarity for semantic equivalence when wording diverges.
  - **llm**: one batched call asking the provider to map every source heading to either a target heading or `null`.
- **`engine.section_mapper.renderer`** — multi-line content insertion that walks every `<w:t>` via XPath (covers hyperlinks, smart-tags), strips `<w:jc>` to prevent the justified-paragraph blowout, and clones the anchor `<w:p>` for additional lines so paragraph order is preserved.
- **`engine.section_mapper.table_filler`** — `TableSpec(headers, rows)` + header-set matching populates empty tables (Histórico Rev/Data/Alteração, Atividades/Responsabilidade, etc) without touching the rest of the doc.
- **`engine.section_mapper.orchestrator`** — `map_sections()` and `map_sections_async()` plus `SectionMappingReport` (mapped count, unmapped source headings, unfilled target headings, orphan paragraphs, JSON-serializable).
- **New extra `[embeddings]`**: `sentence-transformers>=3.0,<4`.
- 22 new unit tests (284 → **307 passing**) covering parser, similarity (all 3 modes mocked), renderer, table_filler, orchestrator end-to-end.

Real-world smoke against an Engeman industrial procedure template: 7 target sections detected, 21 source sections detected, 10 mapped (OBJETIVO -> OBJETIVO, APLICAÇÃO -> APLICAÇÃO, DESCRIÇÃO -> SISTEMÁTICA via synonym, REGISTROS -> RESPONSABILIDADE via synonym), 1 metadata table filled (Rev/Data/Alteração).

### Fixed — Wave K (closes 22 code-review findings)

**3 CRITICAL** + **7 HIGH** + 9 MEDIUM + 3 LOW from `CODE-REVIEW.md` resolved. Unblocks PyPI publish.

#### Pattern inference + formats (#1, #20)

- `pattern_inference.infer_field_patterns` now refuses the freetext / grex no-label fallback for permissive shapes. Only the distinctive shapes (`cpf`, `cnpj`, `iso_date`, `cep`, `uf`) accept value-only regex. Other shapes without a label anchor mark the field for LLM-only fallback.
- Example→doc 1-1 alignment in label collection: example index `i` searches gold doc `i` first. Eliminates cross-field label leakage when one field's example value also appears under another field's label.
- Gold docs of `ata_reuniao`, `contrato_simples`, `procuracao_simples` rewritten to put one field per labeled line (no comma chains). Disambiguates extraction.
- New test `test_format_hybrid_mapper_extracts_correct_values_from_gold_doc` asserts value-equality per field (not just `source=='regex'` coverage). All 10 formats round-trip cleanly.

#### Renderer (#4, #11, #22)

- `_apply_mapping_to_template` now walks document headers and footers (`section.header`, `section.footer`) plus their tables.
- Token replacement walks every `<w:t>` element via XPath, including those nested inside hyperlinks, smart-tags, and content controls.
- Single-pass alternation regex replaces all tokens at once, eliminating the order-dependent re-substitution bug where a field value containing `{{B}}` would trigger another replacement when the loop processed `B`.
- Pass-2 dead branch removed.

#### Security (#3, #5, #6, #14, #15)

- `injection.py::ignore_instructions` regex tightened to allow stacked qualifiers (`"the previous"`, `"all prior"`) — closes canonical-attack misses (`"Ignore the previous instructions"` was previously ignored).
- `injection.py::ignore_instructions_pt` regex restructured to remove ambiguous `\s+...\s*` partitioning. ReDoS gate (test) now asserts <1s on 100K-space adversarial input — was 7.5s on 20K previously.
- `pii.py::CPF` and `CNPJ` patterns no longer accept bare digit blocks. 11-digit phones used to silently mask as `<CPF_001>`; users now must format CPFs explicitly.
- `pii.py::PHONE` pattern extended: keyword-prefixed bare digits (`Tel: 8133334444`), DD-spaced 11-digit (`81 99999-9999`).
- `pii.py::CEP` pattern extended for keyword-prefixed dashless CEP.
- `audit.py::AuditLog` adds `__del__` defensive close + `compare=False, repr=False` on internal fields.

#### Pipeline integration (#2, #7, #8, #9, #10, #13, #16, #19)

- **`AuditLog` is now wired** into `normalize_batch` and `check_conformity` via an optional `audit:` kwarg. Emits `batch.item_start`, `hybrid_mapper.field`, `semantic_diff.done`, `batch.item_end`, `conformity.dimension`, `conformity.verdict` events. The "audit-grade" claim is now backed by code, not just docs.
- `check_conformity` returns `is_conformant=False` and surfaces an `all_dimensions_skipped` failure when no dimension actually evaluated (was: silent score=1.0 pass).
- `check_design` and `diff_texts` no longer swallow LLM errors as `score=1.0` / empty diff. Both now surface a synthetic `provider_error` failure / discrepancy with `severity='warning'`.
- `enrich_with_llm` batches all field enrichments into a single LLM call (was: N sequential calls per template).
- Output stems include the source extension (`doc1.docx.normalized.docx` instead of `doc1.normalized.docx`) so `doc1.docx` and `doc1.pdf` no longer overwrite each other silently.
- `_classify_tier` returns `"low"` when `schemas=[]` (was: `"high"` — a template with zero placeholders silently looked OK).
- `hybrid_mapper.map_hybrid` and `enrich_with_llm` narrow the LLM exception scope from `Exception` to `(LLMError, TimeoutError, ValueError, KeyError)` so configuration / authentication failures propagate.
- `conformity.technical` placeholder regex now matches lowercase + namespaced tokens (`{{user.name}}` no longer invisible).

### Changed

- `__version__` bumped to `0.8.0`.

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
