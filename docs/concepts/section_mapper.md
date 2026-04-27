---
title: Section mapper (Wave L)
---

# Section mapper

Companion to [`normalize_batch`][batch] for **structural** templates that ship with named-but-empty sections (`OBJETIVO`, `APLICAÇÃO`, ...) and rely on heading hierarchy plus tables instead of explicit `{{X}}` tokens. Built and validated against industrial procedure documents (Engeman, NR-12 / NR-13 style, ABNT-shaped academic templates).

[batch]: pipeline.md

## When to use it

Use `engine.section_mapper.map_sections` instead of `normalize_batch` when:

- The template has no `{{placeholder}}` markers — only headings + empty body slots + empty tables.
- The source carries the same heading taxonomy as the target (possibly under different wording: `DESCRIÇÃO` ↔ `SISTEMÁTICA`, `ESCOPO` ↔ `APLICAÇÃO`).
- You want sub-section markers (`6.1.`, `6.2.1.`), list markers (`a.`, `b.`, `•`), and the template's header (document code, author, approver, date, title) populated automatically from the source.

## End-to-end pipeline

```
template.docx ──┬─→ parse_docx ──→ list[DocxSection] (paragraph indices)
                │
                ├─→ detect_default_specs_with_source(template, source) ──→ list[TableSpec]
                │
                └─→ fill_template_header(output, metadata)

source.docx ────┬─→ parse_docx_source ──→ list[TextSection] (numbering resolved)
                │
                └─→ extract_source_metadata ──→ HeaderMetadata
                                                    │
                                                    ▼
similarity (string / embeddings / llm) ─→ list[HeadingMatch]
                                                    │
                                                    ▼
_build_content_map ─→ dict[target_name -> joined source content]
                                                    │
                                                    ▼
render_section_content (line-kind aware: subheading bold, nota italic)
                                                    │
                                                    ▼
fill_tables (header-set match, sub-header row writing)
                                                    │
                                                    ▼
prune empty body slots + collapse empty paragraph runs
                                                    │
                                                    ▼
fill_template_header (XXXX → IT.PRO.URE.387.0005, TITULO → ...)
                                                    │
                                                    ▼
                                         SectionMappingReport
```

`map_sections_async` is the same flow with the `llm` similarity tier wired as a final fallback when string + embeddings still under-cover the target.

## Modules

| Module | Responsibility |
|---|---|
| `engine.section_mapper.parser` | Heading detection from `.docx` + plain text. `parse_docx` (template), `parse_docx_source` (source with auto-numbering resolution). |
| `engine.section_mapper.numbering` | `NumberingResolver` reads `word/numbering.xml`, walks `<w:numPr>` paragraphs, returns the rendered marker. |
| `engine.section_mapper.similarity` | 3-tier matcher: string (zero deps) → embeddings (optional) → llm (when provider supplied). |
| `engine.section_mapper.renderer` | Multi-line content insertion preserving formatting. Sub-heading detection + bold + spacing. |
| `engine.section_mapper.table_filler` | Header-set table fill with optional `subheaders` for templates that have repeated primary headers. |
| `engine.section_mapper.auto_tables` | Walks template + source; synthesizes `TableSpec` for canonical empty tables (Histórico Rev/Data/Alteração, Atividades / Responsabilidade). |
| `engine.section_mapper.header_filler` | Extracts metadata from source header + revision-history table; substitutes `XXXX` / `Rev. 00` / `Elaborado:` / `Aprovado:` / `Data:` / `(TITULO)` placeholders in the template header. |
| `engine.section_mapper.orchestrator` | `map_sections` and `map_sections_async` glue + `SectionMappingReport`. |

## Parser — heading detection

A heading is detected when a paragraph either:

1. Has a Word `Heading <N>` style.
2. Matches the numbered-heading pattern (`1. OBJETIVO`, `3.2. Etapas...`).
3. Matches the all-caps unnumbered pattern (`OBJETIVO`, `NORMAS E DOCUMENTOS DE REFERÊNCIA`).

Hardening guards (each documented with a regression test):

- 2+ separators (`FAFEN-SE/PR/AM`) — rejected.
- Single-word ≤4 letters (`PE`, `NA`, `CFM`) — rejected.
- All-caps sentences > 60 chars — rejected.
- Lines containing `:` (label syntax `EMPRESA: ACME`) — rejected.
- Lines ending in digit (form-field `PROTOCOLO 12345`) — rejected.
- Parenthesized labels (`(TITULO)`) — rejected.
- Single-token version labels (`REV.02`, `VERSAO_1.0`) — rejected.

PDFs commonly emit each heading twice — once in the table of contents, once in the body. The orchestrator deduplicates by **richest content** per heading name, dropping TOC lines.

## Numbering resolver

When the source is a `.docx`, plain-text extraction loses Word's auto-numbering: `<w:numPr>` references `word/numbering.xml` and the marker is rendered at display time, never written into `<w:t>`. The resolver fixes that:

```python
from engine.section_mapper.numbering import load_resolver_from_docx, extract_num_pr

resolver = load_resolver_from_docx(Path("dados.docx"))
for p in doc.paragraphs:
    np = extract_num_pr(p._p.xml)
    if np:
        marker = resolver.marker_for(*np)  # "1.", "5.2.", "a.", "•", ...
```

State is per-`numId`; advancing one level resets every deeper level. Faithful to `numFmt` (`decimal`, `lowerLetter`, `upperLetter`, `lowerRoman`, `upperRoman`).

### Bullet-as-letters heuristic (default on)

`bullet_as_letters=True` (default) renders bullets at `ilvl=0` as Excel-style letters (`a.`, `b.`, ..., `z.`, `aa.`). Industrial documents use Wingdings/Symbol bullets internally but expect lettered output. Set `bullet_as_letters=False` for strictly faithful rendering (`"•"` for every bullet level).

`reset_bullet_counters()` is called by the parser whenever a structural decimal heading advances, so each sub-section restarts its lettering at `a.` instead of continuing across boundaries.

## Similarity matcher

Three tiers, ordered by cost:

| Tier | Deps | Speed | Use when |
|---|---|---|---|
| **string** | none | µs | Source and target use the same vocabulary; synonym table covers wording variants |
| **embeddings** | `pip install "template-engine-ia[embeddings]"` (sentence-transformers, ~80 MB) | ms | Wording diverges across templates (cross-vendor docs) |
| **llm** | provider supplied | s + $ | Long-tail mappings the heuristics still miss |

Default mode is `"auto"`: string first; falls back to embeddings (when installed) when target coverage is < 60%; the async path adds llm as final tier when a provider is supplied and embeddings still under-cover.

The synonym table covers the common Brazilian-Portuguese industrial taxonomy:

| Canonical | Variants |
|---|---|
| `OBJETIVO` | FINALIDADE, PROPOSITO, FINALIDADES |
| `APLICACAO` | ESCOPO, AMBITO, ABRANGENCIA, ALCANCE |
| `SISTEMATICA` | DESCRICAO, PROCEDIMENTO, METODOLOGIA, DETALHAMENTO, EXECUCAO, PROCESSO |
| `RESPONSABILIDADE` | RESPONSABILIDADES, ATRIBUICOES, REGISTROS, RESPONSABILIDADES E AUTORIDADES |
| `HISTORICO` | HISTORICO DE REVISOES, CONTROLE DE REVISOES, REVISOES, HISTORICO DE REVISAO |
| `DEFINICOES` | TERMOS E DEFINICOES, GLOSSARIO, DEFINICOES SIGLAS |

## Renderer

Inserts source content under the matched template heading:

1. Find the heading paragraph in the template.
2. Locate the first empty body paragraph below it (the **anchor**).
3. Drop `<w:jc>` from the anchor's `pPr` so a multi-line block does not render as justified columns.
4. Set the anchor's text to line 1 of the content.
5. For each remaining line, clone the anchor's `<w:p>`, clear inner `<w:t>`, set line N, insert via `addnext` so paragraph order is preserved.

### Line-kind decoration (Phase 2)

Each inserted line is classified by its prefix and decorated:

| Prefix | Kind | Decoration |
|---|---|---|
| `^\d+\.\d+\.?\s` (e.g. `6.1. Foo`) | sub-heading | bold + black + `before=240/after=120` twips |
| `^\d+\.\d+\.\d+\.?\s` (e.g. `6.2.1.`) | sub-sub-heading | bold + black + `before=180/after=80` |
| `^Nota\s*\d*[:.]\s` | nota | italic |
| anything else | body | unchanged |

Decoration is applied via direct formatting only — no `<w:pStyle>` reference — because Word's default `Ttulo2`/`Ttulo3` styles render blue, which is wrong for industrial-procedure documents that expect black bold sub-headings.

### Empty-paragraph cleanup

After insertion, two passes prevent the visual gaps the template's blank slots would otherwise leave:

- **Prune unused body slots**: walk siblings of every filled anchor; delete empty paragraphs up to the next heading.
- **Collapse empty runs**: walk the document body once; collapse any run of 2+ consecutive empty paragraphs to a single empty. Paragraphs inside table cells are left alone (cell layout depends on paragraph count).

### Section-aware post-transforms (Phase 2)

After parsing the source, two section-name-driven content transforms run:

- Sections named `NORMAS` / `REGISTROS` / `ANEXOS` / `DOCUMENTOS DE REFERÊNCIA`: every line without a marker gets a leading `"• "` (reference list auto-bullet).
- Sections named `DEFINIÇÕES`: leading `"term: "` (up to 3 short tokens) is converted to `"term – "` (en-dash).

## Tables

`fill_tables(template, output, specs)` matches each `TableSpec` to a template table by **header set** (order-insensitive). Each spec's `rows` populate empty rows; extra rows are appended.

`TableSpec` extras:

- `subheaders: list[str] | None` — when the template's primary header row repeats values (`["Atividades", "Responsabilidade", "Responsabilidade"]`), supplying `["", "Gerente Setorial", "Supervisores"]` writes those into row 1 and uses them for column mapping.

### Auto-tables

`detect_default_specs_with_source(template, source)` synthesizes specs without manual configuration:

- **Histórico de Revisões** (`Rev. | Data | Alteração`): extracts the source's revision-history table (matching any of `VERSÃO|DATA|AUTOR|ALTERAÇÕES` columns), renumbers from `00`, appends a `"Migração para o novo modelo padrão"` row dated today.
- **Atribuições e Responsabilidades** (`Atividades | Responsabilidade | Responsabilidade`): extracts source paragraphs under `Compete à gerência` / `Compete aos supervisores` (or wording variants); each child paragraph becomes a row tagged `X` in the correct column. Bucket boundaries are detected via `<w:numPr>` `ilvl` so the extractor doesn't spill into the next top-level section.

When an auto-table fills the data for a target section (Responsabilidade / Histórico), the orchestrator drops the prose body for that section so the same info doesn't appear twice.

## Header filler

`extract_source_metadata(source_path)` reads the source `.docx` and gathers:

| Field | Source |
|---|---|
| `document_code` | source `word/header*.xml`, dotted-decimal code reassembled across run fragmentation (`IT.PRO.` + `U` + `RE` + `.387.0005`) |
| `title` | source header, longest all-caps multi-word run that is not the company name or document code |
| `version` | source header, `Ver.: NN` / `Rev. NN` |
| `author` | source body's revision-history table, `AUTOR / REVISOR` column, first non-empty data row |
| `approver` | source header, `Aprovador (es): <name>` (cut at next page indicator / date) |
| `source_date` | source body's revision-history table, `DATA` column, first non-empty data row |

`fill_template_header(output_path, metadata)` walks every `word/header*.xml` inside the output docx zip and substitutes:

| Placeholder | Replacement |
|---|---|
| `XXXX` | `metadata.document_code` |
| `Rev. 00` | `Rev. <version>` |
| `Elaborado:` | `Elaborado: <author>` |
| `Aprovado:` | `Aprovado: <approver>` |
| `Data:` | `Data: <today_iso>` |
| `TITULO` | `metadata.title` |

When source metadata for a placeholder is missing, the placeholder is left in place so a downstream reviewer can spot the gap.

### Document-code reassembly

Source headers fragment a code across many `<w:t>` runs (`IT.PRO.` + `U` + `RE` + `.387.0005`) AND glue a company tag in without a word boundary (`...TRABALHOIT.PRO.URE.387.0005...`).

The extractor builds two flavors of the flat header text — **glued** (no spacing between runs, so dotted codes stay intact) and **spaced** (single space between runs, so titles like `PARTIDA DA ÁREA DE SÍNTESE` followed by `Ver.:` don't merge into `SÍNTESEVer`). The prefix `[A-Z]{2,3}\.[A-Z]{2,5}\.` is located in spaced flavor; a state-machine walk over glued flavor consumes the full code, stopping at the first invalid letter↔digit transition (`...0005PARTIDA` ends the code at `0005`).

## Quick example

```python
from pathlib import Path

from engine.section_mapper import map_sections

report = map_sections(
    template_path=Path("template.docx"),
    source_path=Path("source.docx"),
    output_path=Path("output.docx"),
    # similarity_mode="auto" + auto_tables=True are the defaults
)

print(f"mapped {report.mapped_count} sections")
print(f"tables filled: {report.tables_filled}")
print(f"unmapped source: {report.unmapped_source_headings}")
print(f"unfilled target: {report.unfilled_target_headings}")
print(f"orphan placeholders: {report.orphan_paragraphs}")
```

`SectionMappingReport.to_dict()` returns a JSON-serializable summary suitable for audit logs.

## Limits

See [REAL-WORLD-LIMITS.md][limits] for the full list. Notable items for `section_mapper`:

[limits]: https://github.com/Luizhcrs/template-engine/blob/main/REAL-WORLD-LIMITS.md

- Scanned PDFs are not OCR'd. Use `.docx` source whenever possible.
- Multi-column PDFs interleave columns at extraction time; convert to single-column first.
- Source tables (other than the canonical Histórico / Responsabilidade) come through as flattened text.
- Synonym table is Brazilian-Portuguese specific. Install the `[embeddings]` extra for cross-language matching, or supply an LLM provider for the long tail.
- Sub-section hierarchy (`3.2.1.`) is preserved as text prefix, not as nested heading anchors.
