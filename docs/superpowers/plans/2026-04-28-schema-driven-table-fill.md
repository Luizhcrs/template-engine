# Schema-Driven Table Fill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat slot pipeline with a schema-driven table-fill layer that recognises common BR-PT POP table types, extracts typed records from the source, and writes deterministically per-cell.

**Architecture:**

The current pipeline asks one LLM call to fill 75 disparate slots and hopes the model figures out alignment, type-matching, row-pairing and value extraction simultaneously. It does not work — UNIFAP screenshots after 9 fix releases still show names in phone columns and template defaults left in role cells.

New pipeline:

```
template -> detect_tables -> {table -> TableSchema}        (heuristic + LLM)
source   -> extract_records(schema) -> list[Record]        (LLM, JSON-Schema validated)
records  -> align_to_rows(table, records) -> {(r,c): val}  (deterministic)
fills    -> apply_typed_fills(...)                         (deterministic, type-validated)
        -> validate(output)                                (deterministic; flag, never auto-fix)
```

LLM does only ONE focused thing per stage: schema detection, then record extraction. Alignment and fill are pure code.

**Tech Stack:** python-docx, lxml, pydantic v2 for schemas (already in deps), structlog, OpenAI provider for LLM stages, pytest.

---

## File Structure

- Create: `src/engine/section_mapper/schemas/__init__.py` — schema registry
- Create: `src/engine/section_mapper/schemas/types.py` — `TableSchema`, `ColumnSpec`, `ColumnType` enum
- Create: `src/engine/section_mapper/schemas/builtins.py` — ContactList, RevisionTable, ParticipantTable, SignatureBox
- Create: `src/engine/section_mapper/schemas/detector.py` — `detect_table_schema(headers) -> TableSchema | None`
- Create: `src/engine/section_mapper/record_extractor.py` — `extract_records(source, schema, llm) -> list[Record]`
- Create: `src/engine/section_mapper/record_aligner.py` — `align_records_to_rows(table, records) -> dict[(row,col), str]`
- Create: `src/engine/section_mapper/typed_fill.py` — `apply_typed_fills(template, mapping) -> output`
- Create: `tests/test_schemas.py`, `tests/test_record_extractor.py`, `tests/test_record_aligner.py`, `tests/test_typed_fill.py`
- Modify: `src/engine/section_mapper/orchestrator.py:376-449` — wire schema layer into `_run_auto_mode`
- Create: `tests/golden/unifap/expected.json` — cell-by-cell expected output for UNIFAP
- Create: `tests/golden/corentoc/expected.json` — same for Corentocantins
- Create: `tests/test_golden.py` — runs full pipeline + asserts cell values

---

## Task 1: Schema types

**Files:**
- Create: `src/engine/section_mapper/schemas/__init__.py`
- Create: `src/engine/section_mapper/schemas/types.py`
- Test: `tests/test_schemas.py`

- [ ] Write failing test for `ColumnType` enum + `ColumnSpec` dataclass
- [ ] Implement minimal types
- [ ] Run test, commit

## Task 2: ContactList schema

**Files:**
- Create: `src/engine/section_mapper/schemas/builtins.py`

- [ ] Test that `CONTACT_LIST_SCHEMA` has columns `[number, name, phone, email]` with right types
- [ ] Implement schema constant
- [ ] Commit

## Task 3: Schema detector

**Files:**
- Create: `src/engine/section_mapper/schemas/detector.py`

- [ ] Test `detect_table_schema(["Nº", "Nome", "Telefone", "e-mail"])` returns `CONTACT_LIST_SCHEMA`
- [ ] Test `detect_table_schema(["Foo", "Bar"])` returns `None`
- [ ] Implement header-similarity matcher (string similarity over column names)
- [ ] Add 3 more builtin schemas (RevisionTable, ParticipantTable, SignatureBox)
- [ ] Test detector on each builtin's headers
- [ ] Commit

## Task 4: Record extractor

**Files:**
- Create: `src/engine/section_mapper/record_extractor.py`
- Test: `tests/test_record_extractor.py`

- [ ] Test `extract_records(source_text, CONTACT_LIST_SCHEMA, llm=mock)` returns `[Record(...)]`
- [ ] Implement: build JSON Schema from TableSchema, single LLM call, parse + validate
- [ ] Test malformed LLM response handling (returns empty list, logs warning)
- [ ] Commit

## Task 5: Record-row aligner

**Files:**
- Create: `src/engine/section_mapper/record_aligner.py`
- Test: `tests/test_record_aligner.py`

- [ ] Test 3 records aligned to 3 fillable rows = 1:1 mapping by index
- [ ] Test 4 records aligned to 4 rows including vmerge titular/substituto pairs (Nº repeated for substituto)
- [ ] Test extra records (more records than rows) are dropped + logged
- [ ] Implement: deterministic, no LLM
- [ ] Commit

## Task 6: Typed-fill writer

**Files:**
- Create: `src/engine/section_mapper/typed_fill.py`
- Test: `tests/test_typed_fill.py`

- [ ] Test `apply_typed_fills` writes phone in phone col, email in email col, validates each value against ColumnType regex before writing
- [ ] Test rejects fill that violates column type (logs, skips)
- [ ] Implement using `_iter_row_tcs` from slot_profiler
- [ ] Commit

## Task 7: Wire schema layer into orchestrator

**Files:**
- Modify: `src/engine/section_mapper/orchestrator.py:376-449`

- [ ] After `profile_slots`, run `detect_table_schema` per docx table
- [ ] For each detected schema, call `extract_records` + `align_records_to_rows` + `apply_typed_fills`
- [ ] Tables WITHOUT detected schema fall through to existing `fill_slots` pipeline (no regression)
- [ ] Log summary: schemas detected, records extracted, cells written
- [ ] Run real UNIFAP fixture, eyeball-verify table 1 + table 4 + table 5
- [ ] Commit

## Task 8: Golden fixture suite

**Files:**
- Create: `tests/golden/unifap/expected.json`
- Create: `tests/golden/corentoc/expected.json`
- Create: `tests/test_golden.py`

- [ ] Run pipeline once on UNIFAP, copy actual cell values into expected.json (after eyeball-verifying they're correct)
- [ ] Same for Corentocantins
- [ ] Test loops over expected entries, asserts actual matches
- [ ] CI runs the golden tests on every push — regressions become failed builds, not user screenshots
- [ ] Commit

## Task 9: Drop slot_reviewer integration (optional)

**Files:**
- Modify: `src/engine/section_mapper/orchestrator.py`

- [ ] If schema-driven path covers a table, skip the reviewer for those cells (avoid the over-correction we saw in 0.12.x)
- [ ] Reviewer still runs on body paragraphs + tables without schema
- [ ] Commit

---

## Self-Review

Spec coverage: Tasks 1-3 build schema layer (Phase 1). Task 4 is record extraction (Phase 2). Tasks 5-6 are alignment + deterministic fill (Phase 3). Tasks 7-8 are integration + golden fixtures (Phase 4). Task 9 prevents the reviewer from undoing schema-driven fills.

Type consistency: `TableSchema`, `ColumnSpec`, `ColumnType`, `Record` are introduced in Task 1 and used consistently downstream.

Placeholder scan: each task has concrete files, signatures, and assertions.
