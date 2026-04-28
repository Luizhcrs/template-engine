# Master Roadmap — 100% Magic Document Copilot

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement each phase of this plan task-by-task.

**Goal:** Drop ANY template + ANY source → get correctly-filled docx, every cell type-validated, with audit trail. Zero manual schema declarations. Zero per-template config.

**Tech Stack:** Python 3.11+, python-docx, lxml, OpenAI / Anthropic / Gemini LLM providers, Tesseract OCR, pydantic v2 schemas, pytest, mypy strict.

**Sessions:** 6 phases. Each phase ships independently and improves coverage / quality / robustness incrementally. Plan estimates assume one focused engineer-week per phase.

---

## Current State (2026-04-28, v0.13.3)

Working:
- Profiler (slot inventory) handles sdt content controls, vmerge, drawings, placeholder shapes
- Schema-driven path for 4 BR-PT POP table types (contact_list, revision_table, participant_table, signature_box)
- Slot pipeline fallback for body paragraphs and unknown tables
- Closed-loop reviewer with banned-token guard
- 438 tests, mypy strict, ruff clean
- UNIFAP POP renders correctly (95% cells right)

Gaps:
- New template with header outside the 4 builtins → falls back to slot path → quality drops
- PDFs / images / scanned docs → no extraction
- No semantic schema detection (header match alone misclassifies content-shifted tables)
- Validators are basic regex (phone / email / date)
- No corpus / benchmark / regression dataset
- CLI-only, no UI

---

## Phase 1 — Schema-from-vision (this session)

**Problem:** schema layer covers 4 builtins. Any template with different headers is uncovered.

**Solution:** when no builtin matches, ask the LLM to extract a schema from the template (multimodal: PNG + raw header texts). Cache by sha256(headers) to avoid repeat cost.

**File structure:**
- Create: `src/engine/section_mapper/schemas/detector_vision.py` — `detect_schema_from_table_async(table_xml, headers, llm) -> TableSchema | None`
- Create: `src/engine/section_mapper/schemas/cache.py` — sha256-keyed disk cache
- Modify: `src/engine/section_mapper/orchestrator.py:_run_auto_mode` — fall back to vision detection
- Test: `tests/test_schemas_vision.py`

**Tasks (this phase, complete in this session):**

### Task 1.1: Vision detector signature + JSON Schema for response

- [ ] Write failing test for `detect_schema_from_table_async` returning a `TableSchema` from canned LLM response
- [ ] Implement minimal version (mocked LLM)
- [ ] Run, commit

### Task 1.2: Build prompt with header context

- [ ] Test that prompt carries headers + first body row sample text
- [ ] Implement prompt builder
- [ ] Commit

### Task 1.3: Schema cache (disk-backed)

- [ ] Test cache load / save round trip
- [ ] Implement keyed by sha256(joined headers + first sample row)
- [ ] Cache hits skip the LLM call
- [ ] Commit

### Task 1.4: Wire into orchestrator

- [ ] In `_run_auto_mode`, when `detect_table_schema` returns None, call vision detector
- [ ] Treat the returned schema same as a builtin (record extraction → align → typed_fill)
- [ ] Real-world test with UNIFAP: assert no regression on already-matched tables
- [ ] Commit + tag

---

## Phase 2 — OCR + multi-format input

**Problem:** scanned PDFs, images, ODT, RTF are not extractable today.

**Solution:** layered extractor. Try native extraction first (python-docx for docx, pdfplumber / pypdf for digital PDFs); when text yield is below threshold, fall through to OCR (EasyOCR or Tesseract).

**File structure:**
- Create: `src/engine/extractor/ocr.py` — `extract_with_ocr(path, lang="por")`
- Modify: `src/engine/extractor/__init__.py` — auto-route by detected text yield
- Add: optional dep group `[ocr]` in pyproject (`easyocr`, `pdf2image`)
- Test: `tests/test_extractor_ocr.py` with synthetic image-only PDF

**Tasks:**

### Task 2.1: OCR adapter
- Wrap EasyOCR / Tesseract behind one function returning `ExtractedDoc` shape
- Per-page extraction so layout context survives

### Task 2.2: Auto-route extractor
- Run native extraction first
- Compute `text_density = len(non_whitespace) / page_count`
- If below threshold, swap to OCR

### Task 2.3: Multi-format adapters
- ODT via `odfpy`
- RTF via `striprtf`
- HTML via `beautifulsoup4`
- Plain image (.png / .jpg) directly to OCR

---

## Phase 3 — Robust validator pipeline

**Problem:** today validators are 5 regex patterns. They miss: invalid CPF (digit checksum), UF outside the 27-state list, dates in the future for "Data de Aprovação" past records, NCM codes outside the catalogue, name = "John Doe" which passes regex but is template default.

**Solution:** validator pipeline applied AFTER typed_fill. Each validator returns `ValidationIssue(cell, severity, reason)`. Issues are collected in the report; `severity=critical` blocks shipping.

**File structure:**
- Create: `src/engine/section_mapper/validators/` package
- Validators: `regex.py` (existing logic moved here), `dictionary.py` (UF / NCM / department lists), `cpf.py` / `cnpj.py` (digit checksum), `dates_consistency.py` (no future dates in past columns), `llm_judge.py` (semantic check for free-form columns)
- Modify: `_run_auto_mode` to run the pipeline post-fill, embed results in `SectionMappingReport.validation_issues`

**Tasks:**

### Task 3.1: Validator base class + regex move
### Task 3.2: Dictionary validators (UF, NCM, common departments)
### Task 3.3: CPF / CNPJ checksums
### Task 3.4: Date consistency (monotonic, not future)
### Task 3.5: LLM-as-judge for NAME / SECTOR / FREE columns
### Task 3.6: Wire into orchestrator + report serialisation
### Task 3.7: CLI flag `--strict` blocks output when critical issues found

---

## Phase 4 — Semantic schema detection

**Problem:** UNIFAP table 4 has headers `Atividade | Data | Nome | Função` (matches `signature_box`) but actual row content is revision history. Current detector classifies on headers alone and misclassifies.

**Solution:** detector samples row 0 + first body row. If the body row content looks like a different schema's data (date in Atividade column suggests revision), return that schema instead.

**File structure:**
- Modify: `engine.section_mapper.schemas.detector` — add `detect_table_schema_with_samples(headers, sample_row)` 
- Add: per-schema `signature_score(headers, sample_row) -> float`
- Modify: detector picks highest-scoring schema

**Tasks:**

### Task 4.1: Per-schema sample-row signature scoring
### Task 4.2: Header + sample composite scorer
### Task 4.3: Update orchestrator to pass first-body-row text into detection
### Task 4.4: Regression test: UNIFAP table 4 now classifies as revision_table, not signature_box

---

## Phase 5 — LLM model upgrade + prompt engineering

**Problem:** GPT-4o occasionally hallucinates, drops one-row shifts on numbered headings (Corentocantins sections 3-6), repeats values across rows. Needs newer model + better prompts.

**Solution:**
- Migrate primary provider to Claude Opus 4.7 (1M context) or GPT-5 / Gemini 2.5 Pro (whichever benchmarks best on POP fixtures at the time)
- Prompt-tune via DSPy on a held-out corpus
- Optional: fine-tune a small model (Phi-4, Qwen 2.5 small, Llama 3.3) on `(template, source) → records` triples

**Tasks:**

### Task 5.1: Provider matrix benchmark on UNIFAP + Corentocantins + 5 synthetic templates
### Task 5.2: DSPy prompt-tuning loop on slot_filler / record_extractor / reviewer prompts
### Task 5.3: Fine-tune candidate selection + dataset packaging
### Task 5.4: Evaluation harness with 95th-percentile cell accuracy

---

## Phase 6 — Golden corpus, benchmark suite, web UI

**Problem:** no reproducible quality bar. Each release relies on user screenshots; CI does not catch regressions on real templates. No public-facing UI.

**Solution:** assemble a public-friendly corpus (anonymised contracts, POPs, NR laudos), run them through CI on every PR, ship a web UI that takes the same inputs the CLI does.

**File structure:**
- Create: `benchmarks/datasets/<name>/{template.docx, source.json, expected.json}`
- Create: `benchmarks/eval.py` — harness producing per-template pass / fail + cell accuracy
- Create: `apps/web/` — FastAPI + minimal frontend
- Add: GitHub Actions workflow runs `benchmarks/eval.py` on PR

**Tasks:**

### Task 6.1: Anonymise + commit 100+ template fixtures (mix of real-world public templates + synthetic stress tests)
### Task 6.2: Eval harness + per-template metrics (cell accuracy, latency, cost)
### Task 6.3: CI gate: PR fails if cell accuracy on any fixture drops > 1%
### Task 6.4: FastAPI server with `/fill` endpoint
### Task 6.5: Minimal SPA: drop template + source → preview output → download

---

## Open questions / risks

- **Cost:** schema-from-vision adds 1 extra LLM call per uncached template. Most users send the same template repeatedly so cache should keep cost flat after warm-up.
- **Regression risk on builtin schemas:** the orchestrator MUST try builtin first; vision detection runs only on tables that builtin didn't match. Tested in Task 1.4.
- **OCR quality:** EasyOCR is hit-and-miss on Brazilian PT scans with poor scan quality. May need cloud-vision fallback (Google Document AI / Azure Form Recognizer) for production.
- **Fine-tune corpus availability:** depends on Phase 6 corpus. Sequence Phase 6 before Phase 5 fine-tune step.

---

## Self-review

- Each phase produces working software on its own.
- Phase 1 (this session) ships before any later phase needs it.
- No phase introduces a hard dependency on a not-yet-built phase.
- CI gates (Phase 6) come last so we have the corpus to validate against.
