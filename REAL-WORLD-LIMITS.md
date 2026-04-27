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

### What still doesn't work

- **Scanned PDFs**: extractor falls back to whatever `pdfplumber` can
  produce. OCR is not yet integrated; use the source as a `.docx`
  whenever possible.
- **Multi-column PDFs**: `pdfplumber` interleaves columns; the parser
  reads them as a single column and section detection becomes
  unreliable. Convert to single-column PDF first.
- **Images, tables, charts in source**: section content is text-only.
  Tables in the source are extracted as flattened text rows, not
  reconstructed as docx tables in the output.
- **Heading hierarchy across levels**: dotted numbers (`3.2.1.`) yield
  the right `level` value but the renderer flattens everything under
  the matched parent heading. Sub-sections are not preserved as
  hierarchical anchors in the output.
- **Multilingual templates**: the synonym table and footer markers are
  Brazilian-Portuguese specific. English / Spanish / etc inputs map by
  string overlap only; install the `[embeddings]` extra for better
  cross-language matching.

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
