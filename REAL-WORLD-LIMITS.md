# Real-world limits — known caveats per pipeline

This document captures behavior that synthetic tests do not exercise but
real-world inputs trigger. Each item ships with at least one regression
test in `tests/`.

## section_mapper (Wave L)

### Heading detector

**Rejected as false-positive headings:**

- Acronyms / codes with 2+ separators: `FAFEN-SE/PR/AM`, `PE-3FSE-00220`
- Short acronyms (≤4 letters, single word): `PE`, `NA`, `CFM`
- Long all-caps sentences (>60 chars): warning banners
- Lines with colon: `EMPRESA: ACME` (label syntax, not heading)
- Lines ending in digit: `PROTOCOLO 12345` (form field)
- Parenthesized: `(TITULO)`, `(NOTAS)` (placeholder labels)
- Revision/version labels with dot or dash on single token: `REV.02`, `VERSAO_1.0`

**Accepted as headings:**

- All-caps multi-word: `OBJETIVO`, `APLICAÇÃO`, `NORMAS E DOCUMENTOS DE REFERÊNCIA`
- Numbered sections: `1. OBJETIVO`, `3.2. Etapas`
- Word `Heading 1/2/3` style (any case)

### TOC vs body

PDFs commonly emit each heading twice — once in the table of contents
(empty body) and once in the actual section. The orchestrator deduplicates
by **richest content** per heading name, dropping TOC lines.

### Footer / annex trim

Section content stops at any of these markers:

- `FORM.<...>` (form code)
- `REPRODUCAO PROIBIDA` / `REPRODUÇÃO PROIBIDA`
- `Fl. N/M` (page indicator)
- `INTERNA Página N de M`
- `Referências e Anexos`
- `Dados da Referência`

If your source uses different footer conventions, extend
`_FOOTER_MARKERS` in `engine/section_mapper/orchestrator.py`.

### Source `.docx` auto-numbering preserved (v0.9.2+)

When the source is a Word document, sub-section markers (`6.1.`,
`6.2.1.`) and list markers come through because
`engine.section_mapper.numbering.NumberingResolver` reads
`word/numbering.xml` and renders the marker per `<w:numPr>` paragraph.
Counter state is per `numId`; advancing one level resets every deeper
level.

### DOcStream-style heuristics (v0.9.3+)

Default-on transformations applied to source content for industrial
Brazilian templates:

- Bullet items at `ilvl=0` render as Excel-style letters (`a.`, `b.`,
  ..., `z.`, `aa.`). Set `bullet_as_letters=False` on the resolver for
  faithful `"•"` rendering.
- Letter sequences reset whenever a structural decimal heading
  advances, so each sub-section gets its own `a.`-`z.` run.
- Sections named `NORMAS` / `REGISTROS` / `ANEXOS` / `DOCUMENTOS DE
  REFERÊNCIA` get `"• "` prepended to every line that lacks a marker.
- Sections named `DEFINIÇÕES`: leading `"term: "` is converted to
  `"term – "` (en-dash).

### Sub-heading visual hierarchy (v0.9.5+, fixed colour in v0.9.6)

Inserted lines are classified by prefix and decorated:

- `^\d+\.\d+\.?\s` → bold + black + paragraph spacing.
- `^\d+\.\d+\.\d+\.?\s` → bold + black + paragraph spacing (smaller).
- `^Nota\s*\d*[:.]\s` → italic.

Decoration uses direct formatting, not `<w:pStyle>` references — Word's
default `Ttulo2`/`Ttulo3` styles render blue, which is wrong for
industrial-procedure documents.

### Empty-paragraph cleanup (v0.9.4+)

Two passes prevent vertical-gap regression:

- Walk siblings of every filled anchor; delete empty paragraphs up to
  the next heading.
- Collapse any run of 2+ consecutive empty paragraphs to a single empty.
  Paragraphs inside table cells are left alone (cell layout depends on
  paragraph count).

### Header filler (v0.9.7+)

The orchestrator extracts metadata from the source `.docx` (header runs
in two flavors — glued for dotted document codes, spaced for
multi-word titles — plus the body's revision-history table) and
substitutes the template header placeholders (`XXXX`, `Rev. 00`,
`Elaborado:`, `Aprovado:`, `Data:`, `(TITULO)`) inline. Missing
metadata leaves the placeholder in place so a reviewer can spot the
gap.

### What still doesn't work

- **Scanned PDFs**: extractor falls back to whatever `pdfplumber` can
  produce. OCR is not yet integrated; use the source as a `.docx`
  whenever possible.
- **Multi-column PDFs**: `pdfplumber` interleaves columns; the parser
  reads them as a single column and section detection becomes
  unreliable. Convert to single-column PDF first.
- **Images, tables, charts in source**: section content is text-only.
  Tables in the source are extracted as flattened text rows, not
  reconstructed as docx tables in the output (except the canonical
  Histórico + Responsabilidade tables, which are populated via
  `auto_tables`).
- **Heading hierarchy across levels**: dotted numbers (`3.2.1.`) are
  preserved as text prefixes, not as hierarchical anchors / heading
  styles in the output.
- **Multilingual templates**: the synonym table and footer markers are
  Brazilian-Portuguese specific. English / Spanish / etc inputs map by
  string overlap only; install the `[embeddings]` extra for better
  cross-language matching.
- **Templates without canonical placeholders / tables**: the auto-table
  detector only covers `Histórico` (`Rev. | Data | Alteração`) and
  `Atribuições / Responsabilidade` (`Atividades | Responsabilidade |
  Responsabilidade`). Other empty-table shapes need a caller-supplied
  `TableSpec`. The header filler only knows the Engeman placeholder
  layout (`XXXX` / `(TITULO)` / `Elaborado:` / `Aprovado:` / `Data:` /
  `Rev. 00`); other vendor templates need their own substitution map.

## batch_orchestrator (Wave D)

- **Templates without explicit `{{X}}` placeholders**: use
  `engine.section_mapper.map_sections` instead. `normalize_batch` only
  handles placeholder templates.
- **Templates with placeholders fragmented across multiple `<w:r>`
  runs**: handled by the Wave I two-pass renderer (verified by 6
  regression tests).
- **Source extension collisions**: `doc1.docx` and `doc1.pdf` produce
  separate outputs (`doc1.docx.normalized.docx` and
  `doc1.pdf.normalized.docx`). No silent overwrites since Wave K.

## conformity (Wave F)

- **Visual dimension** uses synthetic-render via PIL + ascii_layout.
  This is a layout-density fingerprint, not pixel-perfect comparison.
  Pixel-perfect belongs to the `design` dimension.
- **Design dimension** ships only the `ConformityVisualProvider`
  Protocol; concrete provider (Gemini File API, etc) is user-supplied.
- **All-skipped runs are non-conformant** since Wave K. A report whose
  every dimension was skipped (typical of `local_only=True` with no
  LLM) can no longer return `is_conformant=True` by accident.

## security (Wave G)

- **PII patterns** are deliberate: only formatted CPF / CNPJ are
  matched. Bare 11-digit blocks (which would also match phone numbers)
  are rejected to avoid misclassification. Keyword-prefixed bare digits
  (`Tel: 81999999999`) are caught.
- **Audit log** is per-process thread-safe but not multi-process safe.
  Use one log file per worker, or wrap with OS-level file locking.
- **`local_only=True`** is enforced at every entry point but does not
  audit user-supplied callbacks. If you pass a custom provider that
  itself reaches the network, that bypass is on you.

## When in doubt

The honest answer to "will the lib work on document X?" is: extract
text first via `engine.extract(path)` and inspect what `pdfplumber` /
`python-docx` give you. Most surprises trace back to the extractor
losing structure that the human eye assumes is preserved.
