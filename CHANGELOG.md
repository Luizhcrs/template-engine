# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.13.3] - 2026-04-28

### Fixed

- `engine.section_mapper.slot_profiler` was emitting BOTH a
  ``label_value`` slot AND the slot immediately below it
  (``instruction`` or empty body para under the cap-2 rule) as
  fillable. The LLM filled both with the same source content —
  UNIFAP rendered ``Responsáveis:`` as a heading line containing the
  full responsibility list AND the body paragraph below it carried
  the same list, producing visible duplication.

  New helper ``_label_value_acting_as_section_heading`` flags a bare
  ``Label:`` as a heading (non-fillable) when:
  - the immediately-next non-empty paragraph is an instruction, OR
  - the label is followed by an empty paragraph (which the cap-2
    rule will mark fillable).

  Label-with-leader rows (``Author: ____``) are unaffected — they
  carry an explicit underscore leader and remain fillable.

### Real-world impact (UNIFAP POP)

| Section | Before                                                         | After                                          |
|---------|----------------------------------------------------------------|------------------------------------------------|
| 5. Responsáveis | heading + body para both with the responsibility list | heading shows ``Responsáveis:``; body has the list |
| a. LISTA DE CONTATOS | heading + body para both with contact list              | heading shows ``LISTA DE CONTATOS:``; body has the list |

### Added tests

- ``test_label_value_followed_by_instruction_is_section_heading``
- ``test_label_value_followed_by_plain_data_is_not_section_heading``
- ``test_label_value_followed_by_empty_paragraph_is_section_heading``
- ``test_label_value_followed_by_empty_then_instruction_is_section_heading``

## [0.13.2] - 2026-04-28

### Fixed

- `engine.section_mapper.slot_profiler` was emitting
  ``column="<row 0 text>"`` anchors for EVERY table, not just tables
  whose row 0 is a real data-header row. Corentocantins regression:
  the mega-table 20x8 has a layout-driven row 0 carrying
  ``Logomarca ou logotipo`` / ``PROCEDIMENTO OPERACIONAL PADRÃO POP``
  / ``Versão`` cells. The procedure-step column got
  ``column="Versão"`` as its anchor, and the LLM dutifully filled the
  step cells with version numbers (``02`` / ``01`` / ``02``) instead
  of step descriptions.

  Anchors are now only emitted when ``detect_table_schema(row 0
  texts)`` returns a known schema. Tables without a recognised header
  shape (Corentocantins mega-table, header / footer wrappers, etc)
  fall back to the historical row-siblings-only context.

### Real-world impact (Corentocantins POP)

| Cell                              | Before                  | After                                   |
|-----------------------------------|-------------------------|-----------------------------------------|
| t0_r0_c2 (POP title)              | "Hospital Geral de Palmas" | "POP do Serviço de Enfermagem – Administração de Medicação Endovenosa" |
| t0_r10_c4 (procedure step 1)      | "02"                    | "1. Higienizar as mãos..."              |
| t0_r11_c4 (procedure step 2)      | "01"                    | "Vigiar sinais vitais..."               |
| t0_r19_c0 (ANEXO)                 | unfilled                | "11. ANEXO: Resolução COFEN..."         |

12 / 16 useful cells filled correctly. 4 of the
``heading_with_hint`` cells (sections 3-6) carry section N-1's
content — the LLM applies a one-row shift on the numbered-heading
sequence — but the previous version filled NONE of those correctly,
so the absolute fill rate is up sharply.

## [0.13.1] - 2026-04-28

### Fixed

- `engine.section_mapper.typed_fill._column_aligned_tc` walked
  ``tr.findall(w:tc)`` (direct children only) before falling back to
  descendants. UNIFAP regression: the revision table mixes 1 direct
  tc + 1 sdt-wrapped date-picker tc + 2 more direct tcs per row, so
  ``target_col=1`` returned the SECOND direct tc (visual column 2)
  instead of the sdt-wrapped one at visual column 1. Every record's
  Data value landed in the Descrição column, every Descrição landed
  in the Requisitado column, every Requisitado dropped off the row.
  Now always iterates `tr.iter(w:tc)` so sdt-wrapped cells stay in
  position.

### Added

- `tests/test_golden.py` — parametrised golden fixture suite (Task 8
  of the schema-driven plan). Locks expected cell-by-cell output
  against `tests/golden/<name>_canned_records.json` +
  `tests/golden/<name>_expected.json`. Mocks the LLM via canned
  records so the suite runs deterministic in CI without API spend.
  First case: UNIFAP POP with 3 schema-matched tables (contact_list,
  participant_table, revision_table); 26 expected cells asserted.

### Real-world impact (UNIFAP POP, table 5 — revision history)

| Cell           | Before                 | After                          |
|----------------|------------------------|--------------------------------|
| row_1_col_1    | `15/10/2014` (template) | `15/03/2023`                   |
| row_1_col_2    | `15/03/2023` (shifted)  | `Versão inicial`               |
| row_1_col_3    | empty                   | `Maria Lopes`                  |

## [0.13.0] - 2026-04-28

Schema-driven table fill pipeline. The flat slot pipeline shipped
through 0.11.x and 0.12.x kept hitting its ceiling — tables came out
scrambled because one LLM call had to extract, align AND fill every
cell with no record-level scaffolding. UNIFAP screenshots after 9
fix releases still showed names in phone columns and template
defaults left in role cells.

This release introduces a separate, schema-aware path for tables
that match a known shape. Plan in
`docs/superpowers/plans/2026-04-28-schema-driven-table-fill.md`.

### Added

- `engine.section_mapper.schemas` — ColumnType enum, ColumnSpec,
  TableSchema dataclasses + four builtin schemas (CONTACT_LIST,
  REVISION_TABLE, PARTICIPANT_TABLE, SIGNATURE_BOX) covering the
  table types that recur across BR-PT POPs.
- `engine.section_mapper.schemas.detector.detect_table_schema(headers)`
  — header-similarity matcher tolerant of case / accent /
  punctuation drift (`E-mail` / `Email` / `e-mail` all canonicalise
  the same).
- `engine.section_mapper.record_extractor.extract_records(source,
  schema, llm)` — single LLM call constrained by a JSON Schema
  derived from the TableSchema. Returns typed `Record` dicts; drops
  records missing required columns; returns `[]` on transport
  failure or malformed response.
- `engine.section_mapper.record_aligner.align_records_to_rows` —
  pure-code deterministic record-to-row mapping. Walks the table's
  rows in document order, one record per row, respecting vmerge
  continuation rows and per-cell fillability flags.
- `engine.section_mapper.typed_fill.apply_typed_fills` — type-validated
  per-cell writer. Phones go in PHONE columns, emails in EMAIL
  columns, dates in DATE columns; mismatched values are rejected
  silently. Walks visual columns (not iter index) so vmerge
  continuation cells don't shift schema-column alignment.
- `_run_auto_mode` integrates the schema layer ahead of the slot
  pipeline. Tables matched by a builtin schema are filled
  deterministically; un-matched tables and body paragraphs fall
  through to the existing slot pipeline so no coverage is lost.
  Reviewer is restricted to slots NOT covered by the schema layer
  (those are auditable + type-checked already).

### Changed

- 36 new tests across `test_schemas.py`, `test_record_extractor.py`,
  `test_record_aligner.py`, `test_typed_fill.py`. Total 433 pass.
  Free-form NAME / SECTOR / ROLE columns now reject obvious
  mis-typed values (a date in a Nome column, a phone in a Setor
  column) so the regressions visible in 0.12.x screenshots cannot
  recur via the schema path.

### Real-world impact (UNIFAP POP)

| Table                         | 0.12.1                         | 0.13.0                                   |
|-------------------------------|--------------------------------|------------------------------------------|
| LISTA DE CONTATOS             | name in Telefone col, scrambled| names+phones+emails in correct cols      |
| Nome / Setor / Função         | duplicate Fulano de Tal default| Maria Lopes \| DIPLAN \| Chefe ...        |
| Atividade / Data / Nome / Função | empty Nome col, X in Função | filled with real reviewer + date         |
| Versão / Data / Descrição     | only Versão filled, rest empty | full revision history                    |
| Schema cells written per run  | 0                              | 41                                       |

### Known gaps

- Substituto pairing in CONTACT_LIST: when source has 3 contacts and
  the template has 4 rows (titular+substituto vmerge groups), the
  aligner assigns one record per row in order, so a substituto row
  may land where another titular was expected. Future work: detect
  vmerge groups and bind titular+substituto records as a pair.
- Schema detector matches by header parity. A table whose headers
  match SIGNATURE_BOX but whose content is a revision history
  (Atividade column carries "Data da Revisão" not a real activity)
  will surface row content semantics we cannot easily disambiguate
  from headers alone.

## [0.12.1] - 2026-04-28

Tightening pass for the closed-loop reviewer. The first cut shipped
in 0.12.0 over-corrected on subsequent rounds and occasionally
overwrote real data with template defaults.

### Changed

- `_run_auto_mode` runs ONE review round instead of looping. Empirical
  finding: round-2+ reviews tended to "fix" already-correct fills,
  regressing quality round-over-round.

- `slot_reviewer` prompt now opens with an explicit
  ``DEFAULT IS NO CHANGE`` instruction. The LLM only proposes a
  correction when it can quote a specific source value or point to a
  specific column mismatch.

- Each table-cell slot's payload now carries an explicit
  ``expected_column`` field (lifted from the ``column="..."`` anchor
  inside the context string). The reviewer was missing wrong-column
  mistakes because the anchor was buried inside a longer context.

### Added

- Banned-token filter on reviewer corrections. Proposed ``new_text``
  containing common BR-PT template defaults
  (``Fulano de Tal``, ``Ciclano``, ``Sicrano``, ``Beltrano``,
  ``XXXXX``, ``XX/XX``, ``x.xx.xxx.xx``) is rejected silently — those
  signal the reviewer is going BACKWARDS, replacing real data with a
  generic placeholder.

### Tests

- ``test_extract_column_header_pulls_anchor_from_context``
- ``test_review_slots_lifts_expected_column_into_payload``
- ``test_review_slots_drops_corrections_with_template_default_tokens``

### Known limitations

The reviewer is best-effort. On UNIFAP it both improves Section 10
(fills the empty fill row with real participants) AND occasionally
mis-corrects (proposes wrong substituto pairings in LISTA DE
CONTATOS). Net effect is positive for first-pass output that has
clear placeholders, neutral or slightly negative for first-pass
output that was already correct. Multi-round review is gated until
we add anchor-based confidence scoring.

## [0.12.0] - 2026-04-28

Closed-loop self-review pass. After the first fill, the orchestrator
now renders the OUTPUT docx, shows it back to the LLM, and accepts a
list of corrections — wrong-column placements, repeated row indices,
left-over placeholder text, duplicate rows, etc. One extra LLM call
per doc. Skipped silently when ``docx2pdf`` / ``pymupdf`` is missing.

### Added

- `engine.section_mapper.slot_reviewer.review_slots(output_path,
  inventory, source, *, llm)` — issues ONE multimodal LLM call against
  the post-fill docx and returns ``dict[slot_id, corrected_text]``.
  Re-reads each fillable slot's text from the rendered output before
  showing the LLM, so the model sees real output (not template
  defaults).
- `_run_auto_mode` integrates the reviewer: render → review → apply
  corrections → done. Logged as
  ``section_mapper.auto_mode.review_applied corrections=N``.

### Real-world impact (UNIFAP POP)

Closed-loop review applied **17 corrections** on top of the first
pass. Section 10 table (Nome / Setor / Função) had been a duplicate
of the template default ``Fulano de Tal | Reitoria | Secretário da
Reitoria``; the reviewer rewrote the empty fill row to
``Maria Lopes | DIPLAN | Chefe de Planejamento``. Other corrections
fixed column placements that the first pass had landed in the wrong
spot.

### Added tests

- `tests/test_slot_reviewer.py` — four unit tests covering: parsed
  corrections returned to the caller, no-op when no images can be
  rendered, malformed / whitespace-only entries dropped, LLM
  exception handled gracefully (empty dict, pipeline keeps the
  first-pass output).

## [0.11.7] - 2026-04-28

### Fixed

- `engine.section_mapper.slot_profiler._iter_row_tcs` was deduping
  iterated tcs by Python ``id()``. lxml's element proxies do NOT have
  stable ``id()`` across iteration — the same memory address gets
  reused for different XML nodes — and the dedupe was silently dropping
  legitimate cells whose proxy ``id`` collided with an earlier one.
  Removed the dedupe entirely (OOXML uses ``gridSpan`` on a single tc
  for horizontal merges, not duplicated tcs, so dedupe was unnecessary).

  UNIFAP regression: table 1 (LISTA DE CONTATOS) row 2 used to surface
  only 2 of its 4 cells; the substituto's phone and e-mail slots were
  invisible to the profiler.

## [0.11.6] - 2026-04-28

Detect Word content-control type from the parent ``<w:sdt>`` so cells
wrapped in date pickers / dropdowns / plain-text controls are
recognised as placeholders even when their current text looks
"complete" (e.g. ``15/10/2014``).

### Fixed

- `engine.section_mapper.slot_profiler.profile_slots` — a tc whose
  ancestor ``<w:sdt>`` carries one of ``<w:date>``,
  ``<w:dropDownList>``, ``<w:comboBox>``, ``<w:text>``,
  ``<w:picture>`` inside ``<w:sdtPr>`` is now classified as
  ``placeholder``/``fillable=True`` regardless of the visible text.
  UNIFAP regression: the four ``15/10/2014`` template-default dates
  in the mega-header table and the four in the revision table sit
  inside ``<w:sdt><w:sdtPr><w:date>`` — they were visible to the
  profiler since v0.11.5 but classified as ``data`` because the text
  alone (a concrete date) gave no placeholder signal. With the
  control-type signal, they now fill correctly.

### Impact (UNIFAP POP, real-world fixture — full pipeline run)

| Metric              | v0.11.4 | v0.11.5 | v0.11.6 |
|---------------------|--------:|--------:|--------:|
| Fillable slots      |      60 |      61 |      73 |
| Slots filled by LLM |      55 |      59 |  **73** |
| Fill rate           |    92 % |    97 % | **100 %** |

All eight template-default ``15/10/2014`` dates across the mega-header
and revision tables are now replaced with real source dates
(``15/03/2023``, ``10/09/2023``, ``22/04/2024``).

### Added

- ``tests/test_slot_profiler.py::test_sdt_date_picker_cell_is_placeholder_even_with_concrete_date``
  — synthesises a ``<w:sdt><w:date>`` wrapper around a tc with
  concrete date text and asserts the slot kind is ``placeholder``.
- ``tests/test_slot_profiler.py::test_sdt_dropdown_cell_is_placeholder``
  — same shape for ``<w:dropDownList>`` controls.

## [0.11.5] - 2026-04-28

Profiler hardening pass driven by visual inspection of the UNIFAP POP
output: walk all ``<w:tc>`` descendants of a row, skip vMerge
continuations, recognise more placeholder shapes, leave image cells
alone.

### Fixed

- `engine.section_mapper.slot_profiler.profile_slots` /
  `engine.section_mapper.slot_renderer.apply_slot_fills` — python-docx's
  ``row.cells`` only returns ``<w:tc>`` elements that are DIRECT
  children of ``<w:tr>``. Enterprise templates wrap date / dropdown /
  plain-text cells inside ``<w:sdt><w:sdtContent><w:tc>``, so those
  cells were invisible. UNIFAP's revision tables had four
  ``15/10/2014`` cells nested in date-picker content controls that the
  profiler never emitted slots for. New helper
  ``_iter_row_tcs(tr)`` walks every ``<w:tc>`` descendant in document
  order; profiler and renderer share it.

- vMerge continuation cells now skipped — a vertically-merged group
  (e.g. an institution logo stretching across 3 rows) used to produce
  one slot per row of the merge, flooding the LLM with phantom empty
  cells. Only the ``<w:vMerge w:val="restart"/>`` cell at the top of
  the group is emitted.

- Cells containing a ``<w:drawing>`` (logo, picture) are now
  classified as ``data`` and never marked fillable. Previously, an
  empty paragraph adjacent to a logo image was treated as a writable
  body slot — the LLM then dropped arbitrary header text into the
  logo cell.

- ``_classify`` placeholder detection broadened:
  - ``X{2,}`` tightened to ``X{3,}`` and the 40-char length cap
    dropped, so inline placeholders like
    ``Chefe da Divisão XXXXX ou Diretor XXXX, etc`` are now flagged.
  - New ``_ROLE_TRAILING_X_RE`` — strings beginning with a known
    BR-PT role token (Diretor, Chefe, Gestor, Reitor, Pró-Reitor,
    Procurador, Departamento, Divisão, Setor, …) and ending in an
    isolated trailing ``X`` (``Gestor do processo X``,
    ``Diretor do Departamento X``) are placeholders. Plain prose like
    ``O paciente fez raio X`` stays as ``data``.

### Impact (UNIFAP POP, real-world fixture)

| Surface                           | Before  | After  |
|-----------------------------------|--------:|-------:|
| Total slots discovered            |    163  |   167  |
| Fillable slots                    |     60  |    61  |
| Slots filled by the LLM           |     55  |    59  |
| Logo cells (table 0 col 0)        | flagged | left alone |
| ``Chefe da Divisão XXXXX``        | unfilled | replaced with real role |

### Added

- ``tests/test_slot_profiler.py`` — five new tests:
  ``test_profile_slots_finds_cells_inside_sdt_content_controls``,
  ``test_iter_row_tcs_skips_vmerge_continuation_cells``,
  ``test_classify_cell_with_image_is_data``,
  ``test_classify_long_xxx_placeholder_inline_in_prose``,
  ``test_classify_trailing_isolated_x_is_placeholder`` /
  ``test_classify_trailing_isolated_x_does_not_match_normal_words``.

## [0.11.4] - 2026-04-28

Anchor table-cell slot context with the column header so the LLM
stops placing data in the wrong column.

### Fixed

- `engine.section_mapper.slot_profiler` — for table-cell slots the
  context string now starts with `column="<header_text>" | …`. Two
  empty cells in the same row used to produce IDENTICAL contexts
  (just the row siblings) so the LLM had no signal for which column
  was which. UNIFAP regression: phone numbers landed in the e-mail
  column, names in the phone column, dates scattered randomly across
  Activity/Resp/Tempo.

  Header row (row 0) cells do NOT receive the column anchor — they
  ARE the header, so a self-reference would just repeat their text.

- `engine.section_mapper.slot_filler` — prompt now treats the
  `column="…"` prefix as a hard constraint. Phone numbers must go in
  Telefone columns, emails in e-mail columns, dates in Data columns,
  names in Nome columns. If the source has no value matching the
  column header, the LLM is told to OMIT the slot. Row-index columns
  (`Nº`, `#`, `Item`) must carry distinct incrementing integers.

### Impact (UNIFAP POP, real-world fixture)

| Table | Cell | Before | After |
|-------|------|--------|-------|
| LISTA DE CONTATOS row 1 | (Telefone, e-mail) | `Maria Lopes \| diplan@unifap.br` | `(96) 3213-1010 \| diplan@unifap.br` |
| Activity row 1 | (Atividade, Resp, Tempo) | `1.0 \| 15/03/2023 \| Maria Lopes` | `Setor identifica... \| Setor \| 1 dia` |
| Nome/Setor/Função row 2 | all 3 columns | `15/03/2023 \| 15/03/2023 \| 15/03/2023` | `Maria Lopes \| DIPLAN \| Chefe de Divisão` |

### Added

- `tests/test_slot_profiler.py::test_profile_slots_table_cell_context_includes_column_header`
  — regression test asserting two empty cells in the same row receive
  distinct column anchors.

## [0.11.3] - 2026-04-28

Fix profiler over-flagging empty paragraphs as fillable slots.

### Fixed

- `engine.section_mapper.slot_profiler._empty_idxs_under_headings` —
  previous rule "any empty paragraph after a heading is a fillable
  slot" let arbitrary page-padding empties get marked. The
  Corentocantins POP template ships with 19 consecutive empty
  paragraphs between two title lines (page-layout padding before a
  mega-table) and the LLM was being asked to fill them, exploding the
  fillable-slot count from 16 real cells to 86.

  New rule: empty paragraphs are only fillable when they belong to a
  short run (≤ 2 consecutive) immediately following a heading. Longer
  runs are page padding and dropped.

### Impact (real-world fixtures)

| Template | Fillable slots | Filled | Real fill rate |
|----------|----------------|--------|----------------|
| UNIFAP POP (before) | 60 | 55 | 92 % |
| UNIFAP POP (after)  | 60 | 60 | 100 % |
| Corentocantins POP (before) | 86 (70 false positives) | 14 | 16 % |
| Corentocantins POP (after)  | 16 | 13 | 81 % |

UNIFAP gain comes from focus: dropping 70 bogus slots from the LLM
prompt frees the model to fill the real ones consistently.

### Added

- `tests/test_slot_profiler.py` — 11 unit tests covering the
  cap-2 rule, regression for the Corentocantins 19-empties run, and
  the heading heuristic boundary cases.

## [0.11.2] - 2026-04-27

Documentation pass: dropped the internal "Wave A–N" milestone codenames
across the entire codebase (READMEs, ROADMAP, CHANGELOG headings, docstrings,
test comments). Wave labels were a private development artifact; published
docs now refer to milestones by version (`v0.3.0`, `v0.8.0`, …) and to
runtime concepts by their actual names (`rules mode`, `LLM-driven mapper`,
`Slot pipeline`, `batch orchestrator`, `conformity validator`,
`security primitives`, `formats catalog`, `hardening pass`).

No behavioural changes. 363 tests pass, mypy strict + ruff clean.

### Changed

- README.md / README.pt.md — refreshed test count (189 → 363), Section
  mapper reference now mentions rules mode / LLM-driven mapper / Slot
  pipeline by name, dropped "Wave H/I/L/M shipped on v0.6" footer.
- ROADMAP.md — status table consolidated to version rows only; section
  headings rewritten without Wave labels.
- CHANGELOG.md — historical entries keep their version anchors but their
  Wave subtitles are gone.
- docs/concepts/section_mapper.md / .pt.md — section headings, frontmatter
  titles and prose use rules mode / LLM-driven mapper directly.
- src/engine/**/*.py — 50+ docstring/comment cleanups across batch,
  hybrid_mapper, schema_inference, conformity, formats, section_mapper,
  security and tests. Public API unchanged.

## [0.11.0] - 2026-04-27

the previous LLM-driven mapper split fill operations across 5 fields (`header_substitutions`,
`section_content`, `table_data`, `paragraph_rewrites`, `cell_fills`).
Each had its own renderer path. Coordinating them was brittle: source
content sometimes got APPENDED next to template instructions instead
of REPLACING them.

the Slot pipeline collapses every fillable place in a docx into one shape:
**`Slot`**. The LLM returns `{slot_id: new_text}`. The renderer
substitutes each slot in place. No cloning, no inserting, no strategy
decisions. The template stays sacred — slots are the only thing that
change.

### Added — `Slot` abstraction (`engine.section_mapper.slots`)

```python
Slot(
    id="cell_t0_r2_c0",  # stable identifier
    address=SlotAddress(location="table_cell", table_index=0, row=2, col=0),
    current_text="1. OBJETIVO: (Descrição clara…)",
    kind="heading_with_hint",  # empty / placeholder / label_value /
                                # instruction / heading_with_hint /
                                # heading / data
    context="...",
    is_fillable=True,
)
```

### Added — `profile_slots` flat profiler

`engine.section_mapper.slot_profiler.profile_slots(template_path)`
emits a complete `SlotInventory` covering:

- Body paragraphs.
- Body table cells (every cell of every body table).
- Header / footer paragraphs (via raw XML, so paragraphs nested in
  `<w:txbxContent>` text boxes get profiled too).

Each slot is classified — `empty` / `placeholder` / `label_value` /
`instruction` / `heading_with_hint` / `heading` / `data`.

### Added — vision-driven slot fill

`engine.section_mapper.slot_filler.fill_slots(inventory, source, *,
llm, template_images)` issues ONE LLM call (multimodal when PNG pages
are available) that returns `{slot_id: new_text}` for every slot the
LLM decides to fill. Slots the LLM omits keep their current text
untouched.

JSON Schema constrains `slot_id` to the actual fillable IDs. ASCII
control characters in responses are stripped (mitigates OpenAI
strict-mode `\x1d` glitch on Portuguese accents).

### Added — `apply_slot_fills` renderer

`engine.section_mapper.slot_renderer.apply_slot_fills(template,
output, *, inventory, fills)` writes each fill at its exact address.
Body paragraphs and cells go via python-docx (so XML escapes match
unescaped). Header / footer parts are rewritten directly inside the
docx zip's `word/headerN.xml` / `word/footerN.xml`.

Mega-table merged-column groups: when a cell fill targets one column
of a merged group (multiple cells in the same row sharing identical
text), the new text is mirrored across every sibling.

### Added — `mode="auto"` (default when provider supplied)

`map_sections_async(... mode=None)` now picks `"auto"` (the Slot pipeline
slot-only) when an LLM provider is passed, `"rules"` otherwise. The
old `"llm"` and `"hybrid"` modes still work but are no longer the
default.

### Result on real-world templates

| Template | Slots fillable | Slots filled (the Slot pipeline) | Outcome |
| --- | --- | --- | --- |
| **UNIFAP POP** (real-world) | 83 | 18 | imperative `Descrever…` / `Apontar…` / `Identificar…` instructions REPLACED in place by source content (vs the previous LLM-driven mapper which appended next to them) |
| **Corentocantins POP** (real-world, mega-table 20×8) | 153 | 128 | every body slot `1. OBJETIVO: (Descrição…)` REPLACED with `1. OBJETIVO: <real>` (vs the previous LLM-driven mapper which left them as template default) |

UNIFAP `Pré-requisitos` instruction and a couple of activities-table
explanatory cells still resist replacement — known limit of the
current prompt. Corentocantins `2. INDICAÇÃO/CONTRAINDICAÇÃO` skipped
because the source has no equivalent (correct behaviour). the Slot pipeline
delivers the "template sacred + slot-only fill" promise that the previous LLM-driven mapper
couldn't.

## [0.10.9] - 2026-04-27 — Focused cell-fill checklist + merged-cell mirror

### Added — fillable-cells checklist in prompt

`auto_mapper._build_fillable_cells_checklist` deduplicates merged-cell
groups and writes an explicit ``FILLABLE CELLS YOU MUST ADDRESS`` list
into the prompt, one logical entry per row. The LLM no longer "thinks
it filled them" because eight identical columns in the same row only
appear once in the checklist.

Format:

    - (table=0, row=10, cols=[4..7]) current="Descrever passo a passo..."
      → emit a cell_fill with content drawn from the SOURCE that
        matches this slot's heading / parenthesised hint.

### Added — merged-column mirror in renderer

When the plan emits a ``cell_fill`` for one column of a merged group,
``_apply_cell_fills`` now mirrors the new text across every sibling
cell in the same row that carried the same original text. Mega-table
layouts visually show one wide cell; previously only the addressed
column got rewritten and the visible cell still showed the template
default.

### Result on Corentocantins POP

Cells now correctly populated:

- Title rows (0, 1) — ``PROCEDIMENTO OPERACIONAL PADRÃO POP DO
  SERVIÇO DE ENFERMAGEM`` mirrored across cols 2-5.
- Procedure rows (10, 11, 12) — ``1. Higienizar as mãos…``,
  ``Vigiar sinais vitais…``, ``Resolução COFEN 564/2017…`` filled in
  the executing-cells columns.
- Footer rows (16, 17, 18) — Elaboração / Revisão / Data filled.

Still empty (LLM still resists overwriting cells whose current text
combines a numbered heading with a parenthesised hint, e.g. ``1.
OBJETIVO: (Descrição clara…)``):

- Rows 2-7 body slots (1.OBJETIVO, 2.INDICAÇÃO, 3.RESULTADOS, ...).
- Row 19 (11.ANEXO).

The checklist + mirror infrastructure is in place; closing rows 2-7
is a prompt-tightening step (the model needs an explicit "REPLACE
the parenthesised hint with the real content; keep the heading
prefix") that's the next iteration.

## [0.10.8] - 2026-04-27 — Multimodal LLM + polymorphic source input

### Added — multimodal LLM (visual layout)

Mega-table layouts (Corentocantins-style POPs) confuse the LLM when
it only sees structural JSON: identical text repeats across 8 merged
columns and the model can't tell apart heading rows vs body slots.

This release renders the template as PNG images and attaches them to
the LLM prompt:

- New module `engine.section_mapper.template_renderer` —
  ``render_pages(docx_path)`` runs ``docx2pdf`` (Word COM on Windows
  / Pages on macOS) to produce a PDF, then PyMuPDF (``fitz``) to
  render each PDF page as a PNG. Returns ``list[PageImage]`` with
  base64 data-URLs ready for the OpenAI vision API.
- ``OpenAIProvider.generate_structured`` gains an ``image_urls`` kwarg
  — when supplied, builds a multimodal user message
  (``[{type: text}, {type: image_url}, ...]``).
- ``build_mapping_plan`` accepts ``template_images: list[str] | None``;
  when present, the prompt instructs the model to combine the visual
  layout with the structural JSON.
- ``_run_llm_mode`` orchestrator auto-renders up to 3 pages of the
  template and attaches them to every LLM call. Silently skipped when
  ``docx2pdf`` or ``fitz`` are missing (logged at info level).

Both deps are optional; install via ``pip install docx2pdf pymupdf``
on Windows / macOS where Word or Pages is available.

### Added — polymorphic source input

``profile_source`` now accepts:

- ``Path`` / ``str`` — file path on disk (existing behaviour).
- ``bytes`` / ``bytearray`` — raw docx bytes; written to a
  ``NamedTemporaryFile`` before profiling.
- ``BytesIO`` / any ``io.IOBase`` — read & buffered to temp file.
- URL string starting with ``http://`` / ``https://`` — downloaded
  via ``urllib.request`` to a temp file (60 s timeout).
- existing ``SourceStructure`` — passed through (idempotent).

Existing API stays compatible because ``Path`` and ``str`` paths fall
through to the original code path. Callers that already have docx
bytes in memory (FastAPI uploads, S3 reads) no longer need to write a
file first.

### Result on Corentocantins (multimodal active, gpt-4o)

Same coverage as v0.10.7 for the first call (header_subs filled,
title cells filled, signature row filled). The merged-cell body
slots (rows 2-7 with imperative help text) remain template-default
even with the visual; this is a prompt-engineering target for the
next iteration.

The infrastructure for multimodal is in place — adding more focused
prompts ("for each cell with imperative `(Descrição...)` text in
parentheses, emit a cell_fill that REPLACES that cell's text") is
the cheap follow-up.

## [0.10.7] - 2026-04-27 — Cell-level fill (mega-table layouts)

Mega-table templates (Corentocantins-style POPs where the entire
document is one big table with embedded heading + body slot cells)
were almost completely uncovered by previous releases — heading
detection found cells but the renderer never wrote anything inside
them.

### Added — `TemplateCell`

`engine.section_mapper.template_profiler.TemplateCell` captures every
cell in every body table:

- `(table_index, row, col)` coordinate
- `text` — current cell content
- `is_fillable` — heuristic flag based on imperative-instruction
  prefix (``Descrever`` / ``Identificar`` / ``Listar`` / ...), XX/0/_/
  dot mask, parenthesised hint shape, label-with-no-value, or known
  template defaults (``Fulano de Tal`` / ``Ciclano (Substituto)``).

`TemplateStructure.cells` exports the full grid so the LLM can address
each fillable cell directly.

### Added — `MappingPlan.cell_fills`

```python
{"table_index": 0, "row": 4, "col": 1, "new_text": "..."}
```

LLM emits one entry per cell that needs filling. Renderer applies via
``cell.text = new_text`` while preserving the first paragraph's run
formatting.

### Added — prompt instruction for cell_fills

LLM is now told to use ``cell_fills`` for mega-table layouts with
worked examples for ``(TÍTULO DO POP)`` parentheses, ``XX/2022``
masks, ``Fulano de Tal`` defaults, and merged-cell heading rows.

### Result on Corentocantins POP (real-world)

Cells the LLM populated:

- ``Versão`` / ``02/2024``
- ``Data de Aprovação`` / ``27/04/2026``
- ``Administração de Medicação Endovenosa`` (title cells, all 8 columns of merged row)
- ``Elaboração Data: 27/04/2026`` (footer signature row)

Still TODO:

- ``1. OBJETIVO:`` body slots (rows 2-7 stayed as instruction text;
  LLM emitted cells for some slots but not all — merged-cell layout
  with the same text in 8 adjacent columns confuses the model).

The cell-fill primitive is in place; closing the remaining gaps is a
prompt-engineering exercise (and a multimodal-image upgrade — visual
layout would help the model disambiguate merged cells).

## [0.10.6] - 2026-04-27 — Real-world templates (UNIFAP + Corentocantins)

Two POP templates downloaded from public Brazilian institution sites
exercise the LLM mapper end-to-end without any rule-table extension:

- **UNIFAP** — `https://www2.unifap.br/deplan/files/2014/12/Modelo-de-POP.docx`.
  Title-case headings (``Descrição``, ``Objetivos``, ``Público-Alvo``),
  14 detected sections, 12 placeholders (``XXXX`` codes,
  ``Versão:`` labels, ``Título:``, etc), 1 empty contact table.
- **Corentocantins** — `https://www.corentocantins.org.br/wp-content/uploads/2022/10/...POP-EDITAVEL.docx`.
  Mega-table with embedded sections, ``(TÍTULO DO POP)``, ``XX/XX``
  date masks.

Realistic source docs were generated by
``scripts/build_real_world_source.py`` (UNIFAP: POP de Solicitação de
Compras; Corentocantins: POP de Administração de Medicação
Endovenosa) — written as free-flowing Portuguese prose so the LLM has
to do real segmentation work.

### Fixed — control-character contamination in OpenAI strict-mode response

OpenAI's structured-output mode under heavy / multi-key schemas
occasionally emits ASCII control characters (`\\x1d` / GROUP SEPARATOR)
where Portuguese accents (``ç``, ``ã``, ``é``) should be. ``solicitação``
became ``solicita\\x1d\\x1do``, which crashed downstream rendering.

The auto_mapper now sanitises every string field of the parsed
response with ``_clean`` (drops `\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f`) so
mangled accents lose information but at least don't break the output.

The cleaner long-term fix is to switch to a non-strict completion mode
or another provider; this release stops the bleeding.

### Added — real-world test scripts

- `scripts/build_real_world_source.py` — synthesizes UNIFAP +
  Corentocantins source docs.
- `scripts/run_real_world_llm.py` — runs `mode="llm"` against every
  real-world fixture pair in `tests/real_world/`.

### Result

| Pair | Sections | Header subs | Tables | Orphans |
| --- | --- | --- | --- | --- |
| **UNIFAP POP / Solicitação de Compras** | 14 / 14 plan keys (2 retry-filled) | 12 | 1 | 0 |
| **Corentocantins POP / Adm. Endovenosa** | 4 / 4 (mega-table layout) | 5 | 0 | 0 |

Both real-world templates round-trip through `mode="llm"` with **no
custom rules**. Open issues:

- UNIFAP template ships example/help text under each heading
  ("Descrever de forma resumida o processo..."). LLM appends source
  content next to the help text instead of replacing it. Future fix:
  detect imperative-instruction body paragraphs and emit
  paragraph_rewrites for them.
- Corentocantins template's mega-table (20×8 with embedded sections)
  works for headings + placeholders but the table-fill path doesn't
  yet recognise it as fillable.

## [0.10.5] - 2026-04-27 — Enterprise hardening (smart default + retry + cache + CLI)

Four fixes that take the previous LLM-driven mapper from "works once" to "production-ready
out of the box". No new features — every change makes the existing
LLM mode safer and cheaper to run repeatedly.

### Smart-default mode

`map_sections_async(... mode=None)` now auto-picks the strategy based
on whether an LLM provider was supplied:

- `llm` provider supplied → `mode="llm"`.
- no provider → `mode="rules"`.

Callers no longer need to remember to set `mode="llm"` when they pass
a provider. The CLI `--mode` flag mirrors this default.

### Plan validation + retry

After the LLM call, `_detect_plan_gaps` inspects the plan against the
template + source structure and reports:

- placeholders the LLM left empty,
- template headings empty in the plan when the source mentions a
  keyword from the heading,
- empty template tables not addressed in `table_data`.

When gaps are detected, a focused retry prompt lists exactly what's
missing and asks the LLM to fill ONLY those slots. The retry response
is merged via `_merge_plans` (retry never erases a previously-set
value). `max_retries=1` by default; raise to widen the recovery
window.

### Plan cache

`engine.section_mapper.plan_cache` persists every successful
`MappingPlan` to `${XDG_CACHE_HOME:-~/.cache}/template-engine/plans/`,
keyed by `sha256(template) + sha256(source) + prompt-version`. Same
template + source pair → no LLM call. Override with
`TEMPLATE_ENGINE_CACHE_DIR=/path` (used by tests). Cache key includes
a `PROMPT_VERSION` tag so prompt rewrites invalidate stale plans.

The orchestrator's `_run_llm_mode` accepts `use_cache: bool = True`
and saves to cache only when the plan carries data (empty plans from
LLM failures are not cached).

CLI `--no-cache` skips the cache for one-off runs.

### CLI `map-sections` command

```bash
template-engine map-sections \
    --template ./template.docx \
    --source ./source.docx \
    --output ./output.docx \
    --provider openai --model gpt-4o
```

`--provider`/`--api-key`/`--model` plug into the same provider
registry as the existing `normalize` and `conformity` commands. When
no provider is given the CLI runs in pure-rules mode (free,
deterministic). With a provider, mode auto-picks `llm`. `--no-cache`
disables the plan cache for the run. `--json <path>` emits the
`SectionMappingReport` summary alongside the docx output.

### Tests

5 new unit tests covering plan-gap detection, plan merge, cache
round-trip, cache miss, and the smart-mode default
(358 → **363 passing**).

### Misc

`match_embeddings` now short-circuits on empty `source_sections` /
`target_names` (was crashing with a torch shape mismatch when source
heading detection returned `[]` for Title-case docs).

## [0.10.4] - 2026-04-27 — Adversarial vendors all green

Closes the failures the v0.10.3 stress test surfaced. Vendor C / D / E
now round-trip end-to-end with **zero orphans** and every section
filled.

### Fixed — Title-case heading detection

`parse_docx` previously rejected ``Resumo`` / ``Abstract`` /
``Conclusão`` / ``Referências`` because the all-caps heuristic
required UPPERCASE. Numbered headings rejected ``1. CLÁUSULA PRIMEIRA
— DO OBJETO`` because the em-dash (``—``, U+2014) was missing from
the title character class.

`_detect_heading` now accepts:

- Numbered headings with em-dash, en-dash, colon, ampersand and
  curly-apostrophe in the title.
- Title-case headings (``Resumo``, ``Abstract``, ``Roles and
  Responsibilities``) when the paragraph's first run is bold and the
  text doesn't end in a sentence-period. ``parse_docx`` now passes
  the bold flag from python-docx.

Result: vendor_c template detects all 9 headings (was 6); vendor_e
detects all 7 (was 1).

### Fixed — body XML escape mismatch

`_apply_body_substitutions` was substring-matching against raw
`word/document.xml`, where ``<<TITULO>>`` is stored XML-escaped as
``&lt;&lt;TITULO&gt;&gt;``. Substitution silently failed. The body
substitution path now uses python-docx (which unescapes inside
``paragraph.text``), so distinctive placeholders match against their
unescaped form.

### Improved — paragraph_rewrites prompt coverage

The LLM was told to emit `paragraph_rewrites` only when ≥2
placeholders share a paragraph. The prompt now also mandates rewrites
for label-with-leader compounds (``Autor: __________``, ``Data:
__/__/____``, ``CPF: ___.___.___-__``, ``Local e Data:
____________``). With this change the cover-page lines and signature
blocks finally get filled.

### Adversarial run results (gpt-4o)

| Vendor | Sections filled | Paragraph rewrites | Tables | Orphans |
| --- | --- | --- | --- | --- |
| **C** ABNT academic | 6 / 9 | 3 | 2 | **0** |
| **D** Bilingual gov form | 5 / 5 | 6 | 1 | **0** |
| **E** Legal contract | 7 / 7 | 7 | 1 | **0** |

Vendor C unfilled sections (``REVISAO DA LITERATURA``, ``DISCUSSAO``,
``REFERENCIAS``) are honest empties — the source document does not
carry equivalent content.

## [0.10.3] - 2026-04-27 — Adversarial vendor stress test + paragraph rewrites

Three new fixture pairs (`tests/vendor_c/d/e`) target weaknesses that
Engeman + Vendor B did not exercise. The first runs revealed
catastrophic body-substitution failures and the bilingual-form CNPJ
mask collisions. This release closes the loudest failures.

### Added — adversarial fixtures

- **`tests/vendor_c/`** — ABNT-style academic with Title-case
  headings (`Resumo`, `Introdução`, `Metodologia`), three-level
  nested numbered sub-sections (`3.2.1.`), placeholder shapes
  `<<TITULO_DO_TRABALHO>>`, `§§§§`, `__/__/____`.
- **`tests/vendor_d/`** — government bilingual form
  (`OBJETIVO / OBJECTIVE` headings on the same line), placeholders of
  shape `[______]` (variable underscore length), `< nome completo >`
  (lowercase angle), dotted-leader fields, CNPJ-style masks
  `___.___.___-__`.
- **`tests/vendor_e/`** — legal contract with parties block (multiple
  placeholders interleaved with literal text), numbered clauses
  `1./2./3.`, witness blocks. Source carries the same content as
  pure narrative without formal headings.

`scripts/build_adversarial_fixtures.py` regenerates them.
`scripts/run_adversarial_llm.py` exercises every pair with the LLM
mode and writes `output_llm.docx` + `report.json` per vendor.

### Added — `MappingPlan.paragraph_rewrites`

Body paragraphs that carry **multiple placeholders interleaved with
literal connector text** (parties block:
`CONTRATANTE: <razão social>, inscrita no CNPJ sob o nº __.___.___/____-__,
com sede em __________________.`; address line:
`Cidade / City: __________  UF / State: __  CEP / ZIP: _____-___`)
break under substring-substitution because every underscore mask
collides. The plan now carries `paragraph_rewrites: list[ParagraphRewrite]`
where each entry has `match_text` (exact paragraph text in the
template) + `replacement_text` (the entire filled paragraph). The
renderer matches by full paragraph text and substitutes preserving
the first run's formatting.

LLM prompt now asks for `paragraph_rewrites` whenever ≥2 placeholders
share a paragraph, with worked examples for parties / address /
signature blocks.

### Fixed — body substitution collision

`auto_renderer._apply_body_substitutions` previously substring-replaced
EVERY occurrence of every placeholder text in `word/document.xml`,
including inside paragraphs that happened to contain similar runs
(CNPJ masks, dotted leaders). This wrecked vendor D's entire body. The
substitution map is now filtered through `_filter_body_safe_subs`
which keeps only placeholders whose text carries an explicit
delimiter pair (`{{...}}`, `[...]`, `<<...>>`, `(LABEL)` uppercase).

### Added — extra placeholder shapes in `template_profiler`

- `<<DOUBLE_ANGLE>>` (kind `"double_angle"`).
- `< lowercase label >` (kind `"angle"`, lowercase only to skip
  XML-like tags).
- `\.{6,}` dotted leaders (kind `"dot_leader"`).
- `§§§...` / `¶¶¶...` symbol runs (kind `"symbol_run"`).
- `Label: ......` / `Label: _______` label-with-leader compound
  pattern.

### Adversarial run results (gpt-4o)

| Vendor | Header | Title page | Sections | Multi-placeholder paragraphs | Tables | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| **A** Engeman PT-BR | ✅ | ✅ | ✅ | ✅ | ✅ | DOcStream parity |
| **B** English corporate | ✅ | ✅ | ✅ | ✅ | ✅ | Migration row in EN |
| **C** ABNT academic | ⚠️ `<<TITULO_DO_TRABALHO>>` empty | ✅ Autor/Orientador/Data | ⚠️ 5 of 8 sections empty | n/a | ✅ | LLM under-fills nested sections |
| **D** Bilingual gov form | ⚠️ Form Nº not filled | ✅ Cidade/City rewrite | ✅ | ⚠️ CPF / Local / Assinatura still placeholder | ✅ | LLM not rewriting label+leader compound |
| **E** Legal contract | ✅ | ✅ Parties / signatures via rewrite | ❌ Cláusulas empty | ✅ | ✅ | LLM not segmenting narrative into clauses |

Vendors A/B unchanged. C/D/E are honest evidence of the LLM mapper's
current limits — open issues in `tests/vendor_c/report.json`,
`tests/vendor_d/report.json`, `tests/vendor_e/report.json`.

## [0.10.2] - 2026-04-27 — Cross-vendor LLM mode validated

### Added

- **Body-paragraph fallback in `SourceStructure`** — `body_paragraphs:
  list[str]` carries every non-empty paragraph from the source. The
  LLM mapper segments this when heading detection fails (English /
  Title-case sources where `OBJETIVO`-style all-caps headings are
  absent).
- **Body placeholder substitution in `auto_renderer`** — the
  `_apply_body_substitutions` pass walks `word/document.xml` and
  applies the same in-run substitution map used for headers, so
  cover-page placeholders (`{{DOC_CODE}}`, `Author:`, `[Title]`, ...)
  get filled too.
- **Cross-vendor fixtures** — `tests/vendor_b/{template,source}.docx`
  and `scripts/build_vendor_b_fixtures.py` regenerate them. Vendor B
  uses English wording, `{{DOC_CODE}}` / `[Title]` / `Author:` /
  `Reviewer:` placeholders, and an `Activity | Owner` table — every
  dimension differs from the Engeman pair.

### Changed — LLM prompt refinements (validated against gpt-4o)

- Source-heading deduplication: explicit instruction not to repeat a
  source heading line (`Objective`, `Method`, `Glossary`, ...) at the
  top of the section content when the LLM has already matched it to a
  template heading.
- Migration-row language follows the source: `"Migração para o novo
  modelo padrão"` for Portuguese sources, `"Migration to new standard
  template"` for English sources, etc. Prior versions hard-wrote the
  Portuguese phrase regardless of source language.
- Body-paragraph fallback noted in the prompt: when
  `source.sections == []` the LLM is told to segment `body_paragraphs`
  itself, and to infer sub-section numbers (`5.1.`, `5.2.`) from the
  heading position.

### Result on Vendor B (English corporate)

| Aspect | Output (rules mode) | Output (llm mode) |
| --- | --- | --- |
| Header `Document Reference: {{DOC_CODE}}` | unchanged (rules don't know this shape) | `Document Reference: PROC-OPS-2024-007` |
| Body title page `{{DOC_CODE}}` / `[Title]` / `Author:` / `Reviewer:` / `Issue Date:` | unchanged | all populated from source |
| Sections (PURPOSE / SCOPE / REFERENCES / DEFINITIONS / PROCEDURE / ROLES / REVISION HISTORY) | empty (English not in synonym table) | all 7 populated from source |
| Sub-section markers (`5.1. Pre-shutdown checks`, `5.2. Shutdown execution`) | absent | inferred by LLM |
| List markers (`a.`, `b.`, `c.` reset per sub-section, `•` for references) | absent | applied per content shape |
| `Activity \| Owner` table | unchanged (single-column shape unknown) | 5 rows, Plant Manager / Shift Supervisor in Owner column |
| `# \| Date \| Description` history table | unchanged | source row + `Migration to new standard template` row dated today |

### Tests

358 passing. The vendor B fixtures live under `tests/vendor_b/` so a
follow-up integration test can be added without re-generating.

## [0.10.1] - 2026-04-27 validated against OpenAI gpt-4o

First end-to-end run of the LLM mode against a real provider on the
Engeman dados.docx pair surfaced two prompt-quality bugs that the
unit tests could not catch:

### Fixed — header substitutions kept the placeholder prefix

The first version of the prompt told the LLM to "pick a value FROM the
SOURCE", which the model interpreted as "output only the value". So
``Rev. 00`` became ``01`` (instead of ``Rev. 01``), ``Aprovado:``
became ``Fabiano Roberto Gomes Arce`` (without the ``Aprovado:``
prefix), and so on.

The header field gets REPLACED in place by the substitution, so the
prefix has to be part of the replacement. The prompt now states this
explicitly with worked examples:

- ``"Rev. 00"`` → ``"Rev. 01"`` (keep the prefix, change only the
  number)
- ``"Elaborado:"`` → ``"Elaborado: Marcos Britto"``
- ``"Data:"`` → ``"Data: 2026-04-27"`` (use TODAY)

### Fixed — responsibility-table sub-headers + X marks

For tables shaped ``["Atividades", "Responsabilidade",
"Responsabilidade"]`` (duplicate primary header, sub-header row carries
``["", "Gerente Setorial", "Supervisores"]``), the LLM was leaving X
columns empty. The prompt now:

- Shows the exact shape ``{"Atividades": "Aprovar...", "Gerente
  Setorial": "X", "Supervisores": ""}``.
- Mandates ``sub_headers`` output when the primary row has duplicates.
- Spells out that each "Compete à gerência" / "Compete aos
  supervisores" paragraph from the source becomes one row.

### Fixed — `.format()` KeyError on JSON-shaped prompt examples

The prompt body now contains literal JSON examples with curly braces
(``{"Rev.": "00"}``). ``str.format()`` choked on those. Replaced with
explicit ``.replace("{template_json}", ...)`` chain so braces inside
examples pass through.

### Result on Engeman dados.docx

LLM-mode output now matches DOcStream's reference:

| Aspect | rules-mode (v0.9.7) | llm-mode (v0.10.1) | DOcStream |
| --- | --- | --- | --- |
| Header doc code | ✓ | ✓ | ✓ |
| Rev. number | Rev. 01 | Rev. 01 | Rev. 01 |
| Elaborado / Aprovado / Data with prefix | ✓ | ✓ | ✓ |
| (TITULO) | PARTIDA DA ÁREA DE SÍNTESE | PARTIDA DA ÁREA DE SÍNTESE | PARTIDA DA ÁREA DE SÍNTESE |
| Sub-section markers (6.1, 6.2.1) | preserved | preserved | preserved |
| Letter sequences (a, b, c) reset | ✓ | ✓ | ✓ |
| Responsabilidade table X marks | gerência / supervisores split | same | same |
| Histórico table | source + migração row | source + migração row | source + migração row |

LLM-mode reaches DOcStream parity **with zero hardcoded vendor logic**
on the Engeman pair. Same code is expected to handle other vendors
without rule-table extension.

Cost: one ~3500-token prompt + ~2000-token response = ~$0.05 with gpt-4o
or ~$0.001 with Gemini Flash 2.5.

## [0.10.0] - 2026-04-27

The the rules-mode pipeline pipeline relied on hardcoded vendor heuristics: Engeman
placeholder names, Brazilian-PT synonym table, canonical Histórico /
Responsabilidade extractors, regex-based `Aprovador (es):` /
`IT.PRO.URE.387.0005` parsers, etc. That worked for one vendor's
templates; it did not generalise.

the previous LLM-driven mapper ships a vendor-agnostic LLM-driven mode that handles ANY template
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
  - `"rules"` (default) — the rules-mode pipeline pipeline, free, deterministic, but
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

### Added

New subpackage `engine.section_mapper` covers the case the existing pipeline did not: templates that ship with named-but-empty sections (no `{{X}}` placeholders) and rely on heading hierarchy + tables. Validated against an industrial procedure template (Engeman / NR-style) that the the batch orchestrator `normalize_batch` could not handle.

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

### Fixed

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

### Fixed

- **Renderer: tokens fragmented across runs.** `batch._apply_mapping_to_template` now uses a two-pass strategy: per-run replacement (preserves intra-paragraph formatting) followed by paragraph-level fallback when a token spans multiple `<w:r>` elements (the common case in Word-edited templates). 6 new tests cover token-in-single-run, fragmented `{{X}}` across 3+ runs, multiple fragmented tokens, table cells, no-op, and direct unit on `_replace_tokens_in_paragraph`.

### Added

- **5 new bundled formats** (10 total now): `abnt_relatorio_tecnico` (NBR 10719), `nr13` (caldeiras / vasos de pressão), `nr35` (permissão de trabalho em altura), `ata_reuniao` (genérico), `procuracao_simples` (instrumento particular).
- **`.github/workflows/publish.yml`** — automated PyPI release on `v*.*.*` tag push using PyPA trusted publishing (no `PYPI_API_TOKEN` secret needed once the project is configured at <https://pypi.org/manage/account/publishing/>).

### Removed

- **`examples/`** moved out of the main repo to keep the lib focused. POCs continue to exist as reference but are no longer shipped with the package. Prior examples (`08`-`14`) are preserved in git history.

### Changed

- **README/README.pt + docs/index.pt.md**: dropped any mention of specific customer numbers, paying customers, or unverified case-study figures. The cost-by-tier table remains as the only quantitative claim.
- ``__version__`` bumped to ``0.7.0``.

### Added

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

### Added

- **`engine.security.mask_pii(text)`** — reversible PII masking. Replaces CPF / CNPJ / email / phone (BR) / RG / CEP with stable tokens (``<CPF_001>`` etc). Returns ``(masked_text, PIIMask)``. Repeated occurrences of the same value reuse the same token. ``mask.unmask(text)`` restores originals.
- **`engine.security.detect_prompt_injection(text, mode='warn'|'reject')`** — pattern-based detector for adversarial inputs. 7 rules covering EN + PT-BR ("ignore previous", "respond only with", role hijack, system override, delimiter injection). ``mode='reject'`` raises ``PromptInjectionDetected``.
- **`engine.security.AuditLog(path)`** — append-only JSON Lines audit trail. Fixed schema: ``ts``, ``event``, ``doc_hash``, ``dimension``, ``source``, ``llm_provider``, ``llm_model``, ``fields_touched``, ``llm_input_hash``, ``llm_output_hash``, ``extra``. Records sha256 hashes — never raw content. Thread-safe per instance.
- **`engine.security.sha256_hex(text)`** — convenience helper for audit hashes.
- **``local_only=True``** flag on ``normalize_batch`` and ``check_conformity``. Raises ``RefusedRemoteCallError`` if any LLM provider is supplied. Hard guarantee for LGPD/HIPAA deployments.
- **``SECURITY-MODEL.md``** — threat model, operating-mode matrix, provider data residency table, reproducibility guarantees, framework guidance (LGPD/HIPAA/SOC2/ISO).
- 26 new unit tests for security (163 → **189 passing**).

Public API exports added: ``AuditLog``, ``InjectionMatch``, ``PIIMask``, ``PromptInjectionDetected``, ``RefusedRemoteCallError``, ``detect_prompt_injection``, ``mask_pii``, ``sha256_hex``, ``unmask``.

### Changed

- ``__version__`` bumped to ``0.5.0`` (the security primitives milestone ships security primitives).
- README rewritten — leads with the differential ("audit-grade, regex-first, LLM-as-judge, zero LibreOffice"), adds an ASCII pipeline diagram, an operating-cost table by tier, and a "Design decisions" section. PT-BR mirror updated.

### Added

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

### Removed

Drops the legacy preset-bundle pipeline in favor of the the batch orchestrator schema-driven path. **Breaking change.** Users on the old pipeline must migrate to ``template-engine normalize``.

- **Source modules dropped:** ``engine.preset_creator``, ``engine.preset_loader``, ``engine.preset_schemas``, ``engine.renderer``, ``engine.render_ops/`` (entire package), ``engine.validator``, ``engine.visual_validator``, ``engine.llm_mapper``.
- **LLM module dropped:** ``engine.llm.gemini_vision`` and ``engine.llm.base.VisualLLMProvider`` Protocol. (Will return in the conformity validator milestone under a different name for the conformity validator design dimension.)
- **CLI commands dropped:** ``template-engine convert`` and ``template-engine visual-validate``. Replacement: ``template-engine normalize``.
- **Optional extras dropped:** ``[visual]`` (was ``pdf2image`` + ``pillow``). New ``[poc]`` extra exposes ``pillow`` for the example POC scripts.
- **Examples dropped:** ``examples/01_quickstart.py``, ``examples/02_custom_provider.py``, ``examples/03_validation.py``, ``examples/04_ascii_layout_poc.py``. POCs 08-14 (the regex-inference milestone demos) preserved.
- **Tests dropped:** ``test_preset_creator``, ``test_preset_loader``, ``test_renderer``, ``test_validator``, ``test_visual_validator``, ``test_llm_mapper``. Total tests: 172 → **131 passing**.
- **Docs pages dropped:** ``concepts/preset.{md,pt.md}``, ``concepts/render-ops.{md,pt.md}``, ``concepts/visual-validation.{md,pt.md}``.

### Migration guide

Old pipeline → the batch orchestrator:

```python
# Before (legacy)
from engine import create_preset, load_preset, map_content, render
preset = await create_preset(template_path, gold_paths, llm)
data = await map_content(preset, source_text, llm)
render(preset, data, output_path)

# After (the batch orchestrator)
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
# (visual validation returns in the conformity validator milestone as part of conformity check)
```

### Changed

- **`engine.confidence`** decoupled from `engine.validator`. ``calculate_confidence`` now accepts any object exposing ``critical_tokens_found/total`` and ``sections_present/required`` via a structural Protocol (no more hard import).
- **`__version__`** bumped to ``0.3.0`` (the consolidation milestone completes the v0.3 milestone).
- **LOC stats:** src 4594 → 3045 (-34%), tests 2655 → 1884 (-29%), total py 9897 → 7329 (-26%).


### Added

- **`engine.pattern_inference`** — `infer_field_patterns(gold_docs, field_examples) -> dict[str, InferredPattern]` synthesizes a regex per field from gold docs + example values. Three-tier value-shape detection:
  1. **Predefined shapes** (Tier 1): `iso_date`, `br_date`, `doc_code`, `cpf`, `cep`, `uf`, `decimal_br`, `integer`, `version`, `fullname`, `month_year_pt`.
  2. **grex-learned shapes** (Tier 2, optional dep `[inference]`): `RegExpBuilder.from_test_cases(...).with_conversion_of_digits().with_conversion_of_words()` — generalizes `\d` and `\w` while preserving structural anchors (literal hyphens / digit classes). Hybrid policy rejects pure literal alternations (`(?:cat|dog|fox)`) and over-permissive `\w+` whose only anchor is whitespace.
  3. **Free-text fallback** (Tier 3): `[^\n]+` when neither tier produces a meaningful regex.
- **`apply_inferred(inferred, text) -> dict[str, str]`** — applies the synthesized regexes to a new document.
- **POCs 08-13 refactored** — `_FIELD_PATTERNS` hardcoded substituído por `infer_field_patterns(_GOLD_DOCS, _FIELD_EXAMPLES)`. 49/49 fields extracted across 6 designs (laudo / contrato / branded / creative / minimalist / form). Zero LLM in extraction path.
- **`[inference]` extra** — `grex>=1.0,<2`. Install via `pip install 'template-engine[inference]'`.
- 24 new unit tests for pattern_inference (110 → 116 total).

### Added

- **`engine.schema_inference`** — `detect_placeholders(template_text) -> list[FieldSchema]` recognizes 5 placeholder syntaxes: mustache `{{X}}`, single brace `{X}`, bracket `[X]`, chevron `<<X>>`, named-blank `__X__`, anonymous-blank `___`. Optional `enrich_with_llm(schemas, llm)` calls LLM per field to infer `field_type`, `format_hint`, `required` from surrounding context. `infer_template_schema(template_path, llm=...)` is the top-level entry point.
- **`engine.hybrid_mapper`** — `map_hybrid(schemas, inferred_patterns, source_text, llm=None)` runs regex first via `apply_inferred`; the missing fields are batched into a single LLM call (when `llm` is supplied) with a focused prompt + dynamic JSON Schema. Output: `dict[str, MappingResult]` with `value`, `source ∈ {regex, llm, missing}`, `confidence ∈ [0,1]`, optional `notes`. Helper `summarize(results)` returns aggregate stats.
- **`engine.semantic_diff`** — `diff_documents(source_path, output_path, llm=...)` and `diff_texts(source_text, output_text, llm=...)` ask the LLM to surface `missing_in_output` / `value_mismatch` / `extra_in_output` discrepancies with `critical` / `warning` / `info` severity. Text-only — no LibreOffice required. `filter_by_severity(...)` for downstream filtering.
- **`engine.batch`** — `normalize_batch(template_path, source_dir, output_dir, llm=..., gold_docs=..., field_examples=..., enable_semantic_diff=..., max_concurrent=...)` end-to-end orchestrator. Async parallel processing with `asyncio.Semaphore`. Direct token-substitution renderer (`_apply_mapping_to_template`) avoids the legacy preset bundle. Returns `BatchReport` with per-doc `BatchItemResult` (mapping, discrepancies, tier, error). Tier classification: `high` (regex resolved everything, no critical diff) / `medium` (LLM filled or warning-level diff) / `low` (missing required field or critical diff) / `error`. `BatchReport.to_dict()` is JSON-serializable for `report.json`.
- **CLI `template-engine normalize`** — wires the full pipeline. Flags: `--template`, `--source-dir`, `--output-dir`, `--provider` (omit for regex-only), `--gold-doc` (repeatable), `--field-examples` (JSON file), `--report`, `--skip-diff`, `--max-concurrent`. Prints rich summary table by tier, writes `report.json`.
- 55 new unit tests across schema_inference (19) + hybrid_mapper (12) + semantic_diff (12) + batch (12). Total: 116 → **172 passing**.

### Added — Visual validation (legacy, to be deprecated in the consolidation milestone)

- **Visual validation** — `engine.visual_validator.validate_visual()` compares a rendered `.docx` against a gold reference using a multi-modal LLM. Pipeline: LibreOffice headless (`.docx` → PDF) + `pdf2image` (PDF → PNG) + LLM call with structured schema. Returns `VisualValidationResult` with 0-1 score, categorized issues (alignment / spacing / typography / section_order / other), severity (low/medium/high), and rendered images for inspection.
- **`GeminiVisionProvider`** — multi-modal provider in `engine.llm.gemini_vision`. Implements `VisualLLMProvider` Protocol. Reuses existing `[gemini]` extra (no new dep).
- **`VisualLLMProvider`** Protocol added to `engine.llm.base` (text providers untouched).
- **`engine.docx_to_png(path, out_dir, dpi)`** — public helper for raster previews.
- **CLI command** `template-engine visual-validate <gold> <output> --api-key X`.
- **`[visual]` extra** — `pdf2image` + `pillow`.

### Changed

- `__version__` bumped to `0.3.0a1` (alpha — the batch orchestrator + visual validator APIs may evolve before v0.3 stable).
- Pipeline core continues to require **zero LibreOffice**. Only `visual_validator` legacy uses it; replacement (the conformity validator milestone design dimension via direct multimodal upload) is in roadmap.

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
