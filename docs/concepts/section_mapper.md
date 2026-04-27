---
title: Section mapper (Wave L + M)
---

# Section mapper

Companion to [`normalize_batch`][batch] for **structural** templates that ship with named-but-empty sections (`OBJETIVO`, `APLICAÇÃO`, ...) and rely on heading hierarchy + tables + cell layout instead of explicit `{{X}}` tokens.

Two modes ship side-by-side:

- **Wave L (`mode="rules"`)** — deterministic, free, zero LLM calls. Hardcoded heuristics tuned to Brazilian-PT industrial procedures (Engeman, NR-12 / NR-13). DOcStream parity on the first real-world Engeman pair.
- **Wave M (`mode="llm"` / `"hybrid"`)** — vendor-agnostic. ONE multimodal LLM call (template rendered as PNG + structural JSON + source content) returns a complete `MappingPlan` covering header substitutions, section content, paragraph rewrites, table data, and cell-level fills. Validated against:
  - The original Engeman pair (PT-BR industrial).
  - Five synthetic adversarial pairs (English corporate, ABNT academic, bilingual gov form, legal contract, mega-table layout).
  - Two real-world templates downloaded from public Brazilian institution sites (UNIFAP POP — universidade federal; Corentocantins POP — regional nursing council).

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

## Operating modes

| Mode | When | Cost (Gemini Flash 2.5) |
| --- | --- | --- |
| `rules` (default in `map_sections`) | PT-BR / Engeman style; bit-for-bit reproducibility | $0.0000 |
| `llm` (`map_sections_async(mode="llm", llm=...)`) | any vendor / language; needs provider | ~$0.001 |
| `hybrid` (`mode="hybrid", llm=...`) | rules first, LLM tops up gaps | ~$0.001 when gaps |

### LLM mode end-to-end

```python
import asyncio
from pathlib import Path

from engine.llm.openai_provider import OpenAIProvider
from engine.section_mapper import map_sections_async

async def main() -> None:
    provider = OpenAIProvider(api_key="sk-...", model="gpt-4o", timeout=300.0)
    report = await map_sections_async(
        template_path=Path("template.docx"),
        source_path=Path("source.docx"),
        output_path=Path("output.docx"),
        mode="llm",
        llm=provider,
    )
    print(f"sections in plan: {len(report.matches)}")
    print(f"tables filled: {report.tables_filled}")

asyncio.run(main())
```

The LLM call returns a `MappingPlan` covering every detected
placeholder (header + body), every template heading, and every empty
table. Failure paths fall back to an empty plan so callers can chain a
rules-mode retry.

### Cross-vendor validation (Wave M)

Five fixture pairs and two real-world public templates exercise the
LLM mapper:

| Pair | Domain | Language | Notable shape |
| --- | --- | --- | --- |
| **A — Engeman** (`dados.docx`) | industrial procedure | PT-BR | `XXXX` / `(TITULO)` / `Elaborado:` / `Atividades \| Responsabilidade \| Responsabilidade` |
| **B — English corporate** | corporate procedure | EN | `{{DOC_CODE}}` / `[Title]` / `Author:` / `Activity \| Owner` |
| **C — ABNT academic** | thesis | PT-BR Title-case | `<<TITULO_DO_TRABALHO>>` / `§§§§§` / nested `1.2.1` / `__/__/____` |
| **D — Bilingual gov form** | government form | PT-BR / EN | `[______]` / `< nome >` / `___.___.___-__` masks |
| **E — Legal contract** | contract | PT-BR | parties block (multi-placeholder), numbered clauses 1-6 |
| **UNIFAP POP** (real-world) | university procedure | PT-BR Title-case | `Descrição` / `Objetivos` / `XXXXXXXX` / contact table |
| **Corentocantins POP** (real-world) | nursing-council POP | PT-BR | mega-table 20×8 with merged cells |

Result against gpt-4o (mode=`llm`):

| Pair | Sections | Header subs | Tables | Cell fills | Orphans |
| --- | --- | --- | --- | --- | --- |
| A | 7/7 | 6 | 2 | n/a | 0 |
| B | 7/7 | 5 | 2 | n/a | 0 |
| C | 6/9 | 4 | 2 | n/a | 0 |
| D | 5/5 | 8 | 1 | n/a | 1 |
| E | 7/7 | 7 | 1 | n/a | 0 |
| UNIFAP | 14 plan keys | 12 | 1 | covered | 0 |
| Corentocantins | 4 sections | 5 | 0 | partial (title + procedure rows) | 0 |

Regenerate via:

```bash
python scripts/build_vendor_b_fixtures.py
python scripts/build_adversarial_fixtures.py
python scripts/build_real_world_source.py
python scripts/run_adversarial_llm.py
python scripts/run_real_world_llm.py
```

### Multimodal vision (Wave M)

The LLM call attaches PNG renders of the template (up to 3 pages) so
the model can SEE merged cells, table geometry, embedded logos.
Pipeline:

```
template.docx ──→ docx2pdf (Word COM / Pages) ──→ template.pdf
                                                       │
                                                       ▼
                                           PyMuPDF (fitz) per-page
                                                       │
                                                       ▼
                                              base64 PNG data URLs
                                                       │
                                                       ▼
                                       OpenAI vision (gpt-4o)
                                       multipart user message
```

`engine.section_mapper.template_renderer.render_pages(docx_path,
max_pages=3)` returns `list[PageImage]`. Both `docx2pdf` and `pymupdf`
are optional — when missing, the orchestrator falls back to text-only
mode (logged at info level). Install via:

```bash
pip install docx2pdf pymupdf
```

### Cell-level fills (Wave M)

Mega-table layouts (Corentocantins-style POPs) carry the entire
document as one big table. Heading cells and body slot cells live in
the same table grid. The Wave L renderer doesn't see inside cells.

Wave M adds:

- `TemplateCell(table_index, row, col, text, is_fillable)` — every
  cell of every body table is profiled with a fillability heuristic
  (empty / imperative-instruction text / `XX` mask / parenthesised
  hint / label-no-value / known template defaults like `Fulano de
  Tal`).
- `MappingPlan.cell_fills: list[CellFill]` — LLM addresses each
  fillable cell by `(table_index, row, col)`.
- `auto_renderer._apply_cell_fills` — writes via `cell.text` while
  preserving the first paragraph's run formatting. Mirrors the fill
  across every sibling cell in the same row that shared the original
  text (merged-column groups).
- A deduplicated `FILLABLE CELLS YOU MUST ADDRESS` checklist is
  appended to the prompt, grouping merged columns into one logical
  entry per row, so the LLM no longer thinks it filled them.

### Plan validation + retry

After the initial LLM call, `_detect_plan_gaps` reports:

- placeholders the LLM left empty
- template headings empty in the plan when the source mentions a
  matching keyword
- empty template tables not addressed in `table_data`

When gaps exist, a focused retry prompt lists exactly what's missing
and asks the LLM to fill ONLY those slots. `_merge_plans` overlays the
retry without erasing existing values. `max_retries=1` by default.

### Plan cache

`engine.section_mapper.plan_cache` persists every successful
`MappingPlan` to `${XDG_CACHE_HOME:-~/.cache}/template-engine/plans/`
keyed by `sha256(template_bytes) + sha256(source_bytes) +
PROMPT_VERSION`. Same template + source pair → 0 LLM calls. Override
the cache directory via `TEMPLATE_ENGINE_CACHE_DIR=/path`.

Real-run benchmark (Vendor E, gpt-4o):

| Run | Wall time | LLM calls |
| --- | --- | --- |
| First | ~20 s | 1 (call) + 0-1 (retry) |
| Second (cache hit) | 4.6 s | 0 |

CLI `--no-cache` skips the cache for one-off runs.

### Polymorphic source input

`profile_source` accepts:

- `Path` / `str` — file path on disk
- `bytes` / `bytearray` — raw docx bytes (written to a temp file)
- `BytesIO` / any `io.IOBase` — read & buffered
- URL strings (`http://` / `https://`) — downloaded via `urllib`
- existing `SourceStructure` — passed through (idempotent)

The same applies to source paths inside `map_sections_async`.

### CLI command

```bash
template-engine map-sections \
    --template ./template.docx \
    --source ./source.docx \
    --output ./output.docx \
    --provider openai --api-key "$OPENAI_API_KEY" --model gpt-4o
```

Auto-picks `mode="llm"` when a provider is supplied, `"rules"`
otherwise. `--no-cache` disables the plan cache. `--json <path>` emits
the `SectionMappingReport`.

### Smart-default mode

`map_sections_async(... mode=None)` (default) auto-picks:

- `llm` provider supplied → `mode="llm"`
- no provider → `mode="rules"`

Callers don't need to remember mode flags.

## Limits

See [REAL-WORLD-LIMITS.md][limits] for the full list. Honest call-outs:

[limits]: https://github.com/Luizhcrs/template-engine/blob/main/REAL-WORLD-LIMITS.md

### Wave L (rules mode)

- Scanned PDFs are not OCR'd. Use `.docx` source whenever possible.
- Multi-column PDFs interleave columns at extraction time; convert to single-column first.
- Source tables (other than the canonical Histórico / Responsabilidade) come through as flattened text.
- Synonym table is Brazilian-Portuguese specific. Install the `[embeddings]` extra for cross-language matching, or supply an LLM provider for the long tail.
- Sub-section hierarchy (`3.2.1.`) is preserved as text prefix, not as nested heading anchors.

### Wave M (LLM mode)

- **Determinism lost** — gpt-4o varies slightly across runs. The plan cache mitigates this for repeated pairs but not for first runs.
- **Cost** — ~$0.05/doc with gpt-4o, ~$0.001/doc with Gemini Flash 2.5. Cache makes follow-up runs free.
- **Multimodal optional** — when `docx2pdf` (Word COM) or `pymupdf` is missing, the orchestrator silently falls back to text-only mode. Install both for best mega-table coverage.
- **Token-window cap** — template JSON capped at 30 000 chars, source JSON at 60 000 chars. Very large templates may be truncated.
- **Mega-table body slots with imperative hints** still partially resist replacement (Corentocantins rows 2-7). The model preserves cells whose current text combines a numbered heading with a parenthesised hint. Closing this is a prompt-tightening target.

### Universal

- **Real-world template variance is endless.** Five vendors covered now (synthetic + real). Every new vendor is a new failure-mode discovery exercise; bugs reproduce per-template, not in the abstract.
- **No CI integration test** for `mode="llm"` — the pipeline calls a paid API. Production use requires a smoke run against your own corpus.
