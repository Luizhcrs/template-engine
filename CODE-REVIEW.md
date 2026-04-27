# Code review — template-engine v0.7.1

Reviewer: superpowers:code-reviewer agent (independent, full read access).
Date: 2026-04-26.
Status: 269 unit tests green, ruff/format/mypy clean. Review found 22
concrete issues, **3 CRITICAL** that block PyPI publish.

This document is the verbatim consolidation of the review plus an action
plan. Wave K addresses CRITICAL + HIGH; MEDIUM/LOW are scheduled.

## Verdict

> Found 22 concrete issues. Three are CRITICAL and likely to bite real users
> on day 1. The most damaging: bundled formats produce wrong field values on
> their own gold docs, and `AuditLog` — the centerpiece of the "audit-grade"
> pitch — is exposed but never invoked from any pipeline. The renderer fix
> from Wave I is correct for the cases it tests but misses headers/footers
> and content inside hyperlinks. The injection detector is leaky (misses
> canonical attacks) and has a quadratic-time ReDoS hole on the PT-BR
> pattern.

---

## CRITICAL (block PyPI)

### #1 — Bundled formats produce wrong field values on their own gold docs

**Files:** `src/engine/formats/{nr13,abnt_artigo,abnt_referencia,ata_reuniao,procuracao_simples}.py`

**Reproducible.** Run `infer_field_patterns` on each format's `gold_docs[0]`, then `apply_inferred`:

- `nr13`: `PMTA` returns `"10 kgf/cm2"` (the value of `Pressao de operacao`, not PMTA). `CONCLUSAO` returns `"LAUDO DE INSPECAO - NR-13"` (document title).
- `abnt_artigo`: `AUTORES`, `INTRODUCAO`, `REFERENCIAS` all return the document title.
- `abnt_referencia`: `AUTOR`, `TITULO`, `LOCAL`, `EDITORA` all return `"REFERENCIAS"`. `ANO` returns `"4"` (parsed from `"4. ed."`).
- `ata_reuniao`: `HORA_FIM` returns the start time. `PARTICIPANTES`, `PAUTA`, `DELIBERACOES`, `PROXIMA_REUNIAO` all wrong.
- `procuracao_simples`: `ENDERECO_OUTORGANTE`, `PODERES`, `PRAZO` return `"PROCURACAO"`. `CPF_OUTORGADO` returns the **outorgante's** CPF.

**Two compounding root causes:**

- Fields without a clear `Label:` prefix in the gold doc fall to the empty-label branch in `pattern_inference.py:267-272` which compiles to `([^\n]+)` and matches the FIRST non-empty line.
- Fields with similar nearby labels (`PMTA` next to `Pressao de operacao:`) collect each other's labels via `_extract_label_before` (60-char window in `pattern_inference.py:39`), so both regexes alternate over both labels and silently extract the first match.

**Test gap:** `test_format_hybrid_mapper_extracts_from_gold_doc` only asserts `coverage >= 50%` of fields are `source=='regex'`, never that the extracted **value** equals the expected example. So 269 green tests coexist with broken extractions.

**Fix:**
1. Add value-equality assertion per field in the format integration test.
2. When a field's labels list is empty, refuse to compile a regex and mark the field for LLM-only or warn loudly.
3. When two fields share label tokens AND share a value shape, refuse to alternate the labels and instead anchor each regex to the FIRST occurrence of its OWN unique label or skip the field.

**Effort:** M

**Severity rationale:** the lib's pitch ("regex resolves the bulk for free") is hollow when the regex extracts the wrong values. Users will normalize 100 docs with the wrong CPF, wrong CONCLUSAO, wrong VIGENCIA — and ship to production thinking it worked.

---

### #2 — `AuditLog` is shipped but never wired into any pipeline

**File:** `src/engine/security/audit.py`, exposed via `engine/__init__.py:65`.

`grep -rn "log_event\|AuditLog" src/` shows zero call sites outside the module. `normalize_batch`, `check_conformity`, `map_hybrid`, `diff_documents`, `enrich_with_llm` — none of them invoke the audit log.

The README and SECURITY-MODEL.md sell the library as "audit-grade", but a regulated user instantiating `AuditLog(path=...)` and running `await normalize_batch(...)` gets an empty file. There's no decorator, no DI, no global handle, no instructions to plumb it.

**Fix:** accept an optional `audit: AuditLog | None` kwarg on `normalize_batch` and `check_conformity`, and emit events at LLM call boundaries (one per LLM input/output, with hashes; one at item start/end with doc_hash; one per dimension result). Document the integration in SECURITY-MODEL.md.

**Effort:** M

**Severity rationale:** the entire "audit-grade" framing in the README is currently false. A regulator asking "what touched this doc?" would receive an empty log. This is the highest-stakes gap in the project's positioning.

---

### #3 — ReDoS in `ignore_instructions_pt`

**File:** `src/engine/security/injection.py:36-42`.

The pattern has `\s+` then optional `(?:as?|todas?...)?` then `\s*` then required term then `\s+` then optional final group. The interaction between `\s+` and `\s*` with optional middle group creates ambiguous whitespace partitioning → quadratic backtracking on adversarial whitespace.

**Measured:** 1.8s on 10K spaces, **7.5s on 20K spaces**. A doc with 5–10 such substrings concatenated locks a worker for tens of seconds. `mode="warn"` is the default — every paragraph runs through the detector.

**Fix:** collapse the optional middle group into a single non-optional alternation, drop one of the `\s+`/`\s*`, or precompile with `regex` module timeout. Minimal change:

```diff
-r"(?:as?|todas?|todos?|os?|tudo)?\s*"
+r"(?:(?:as?|todas?|todos?|os?|tudo)\s+)?"
```

**Effort:** S

**Severity rationale:** denial of service against any worker processing user-supplied content. Adversarial PDFs in a normalize_batch could lock a worker pool for minutes.

---

## HIGH

### #4 — Renderer doesn't touch headers, footers, or hyperlink-wrapped runs

**File:** `src/engine/batch.py:208` (`_apply_mapping_to_template`).

Both bugs confirmed:

- Token in `section.header.paragraphs[0]` survives unchanged.
- Token inside a `<w:hyperlink>` child element is invisible to `paragraph.runs` (which only returns direct children). Pass-2's `paragraph.text` concatenates them, so the merge produces correct text BUT writes only to `runs[0]`, leaving the hyperlink's `{{TOKEN}}` text intact → output contains both the substituted value AND the original token.

Same blind spot likely applies to: footers, header/footer tables, text boxes (`<w:txbxContent>`), `<w:smartTag>`, `<w:fldSimple>`, footnotes, comments.

**Fix:** iterate `section.header.paragraphs`, `section.header.tables`, `section.footer.paragraphs`, `section.footer.tables` for every section. For hyperlink/smartTag, walk all `<w:r>` elements via XPath (`paragraph._p.findall('.//w:r', NS)`) instead of `paragraph.runs` and clear the inner `<w:t>` text after the merge. Simpler defensive option: regex-replace on the raw XML of every paragraph element before passing through python-docx; not pretty but covers everything.

**Effort:** M

---

### #5 — Injection detector misses canonical English attacks

**File:** `src/engine/security/injection.py:28-32`.

Confirmed misses: `"Ignore the previous instructions"`, `"IGNORE ALL PRIOR PROMPTS"`, `"Forget the above context"`. The regex has only ONE qualifier slot (`all|every|the|previous|...`), so any attack that stacks two qualifiers ("the previous", "all prior") slides through. Same shape problem in `ignore_instructions_pt`.

**Fix:** change `(?:all|...)\s+` to `(?:(?:all|the|every|previous|...)\s+){1,3}` or use a non-greedy run of qualifier words.

**Effort:** S

---

### #6 — PII patterns: bare phone numbers misclassified as CPF

**File:** `src/engine/security/pii.py:34, 48`.

Confirmed: `"Telefone: 81999999999"` masks as `<CPF_001>` because the CPF pattern's `\b\d{11}\b` alternative runs first and any 11-digit run wins. Phone-without-formatting is actively wrong, not just missed.

Confirmed misses: `"Tel: 8133334444"` (10-digit bare phone), `"Whats: 81 99999-9999"` (no parens, not in PHONE pattern), CEP without dash like `"CEP 01310100"` is undetected (only `\d{5}-\d{3}` pattern).

Documentation says "Detection order matters — longer/more-specific patterns (CNPJ before CPF, etc) run first" but PHONE comes after CPF in `_PATTERNS`. CPF's `\b\d{11}\b` will eat any unformatted 11-digit phone.

**Fix:** drop the bare-digit alternative in CPF and CNPJ regexes (or move PHONE before CPF and add a 10-digit phone alternative). Add CEP-without-dash to the CEP pattern. Document the trade-off (raw 11-digit blocks are inherently ambiguous).

**Effort:** S

---

### #7 — Conformity check returns `is_conformant=True` when all dimensions are skipped

**File:** `src/engine/conformity/aggregator.py:54-59, 140`.

Confirmed: `await check_conformity(a, b, dimensions=["text"])` with no LLM returns `score=1.0, is_conformant=True`. The text dimension was silently skipped (no LLM) → score=1.0. The aggregator divides weighted sum by `total_weight` of dimensions present, normalizing to 1.0. User asked for a "conformity check", got an unconditional pass.

Worse: this is the exact pattern a `local_only=True` regulated user hits — they explicitly opted out of LLM, and the design dimension also requires LLM, so a conformity report could be entirely composed of skipped dimensions and still pass.

**Fix:** when the report is composed entirely of skipped dimensions, set `is_conformant=False` and add a top-level failure `"all_dimensions_skipped"`. Or: separate `is_conformant` and `is_evaluable` properties; default to "not evaluable" when no real dimension ran.

**Effort:** S

---

### #8 — `check_design` and `diff_texts` swallow LLM errors as "score=1.0 / no discrepancies"

**Files:** `src/engine/conformity/design.py:109-116`, `src/engine/semantic_diff.py:198-200`.

Both wrap the LLM call in `except Exception` and return a "passing" outcome on failure. Effect: a transient network blip during a conformity check produces a green report. There's a `log.warning` but no failure surfaced.

**Fix:** emit a `Failure(severity="warning")` plus `skipped=True/skip_reason` instead of `score=1.0`. Or expose a strict-mode flag `raise_on_provider_error=True`.

**Effort:** S

---

### #9 — Hybrid mapper schema-enrichment is N sequential LLM calls per template

**File:** `src/engine/schema_inference.py:186-213`.

For a template with 30 placeholders, `enrich_with_llm` does 30 sequential `await llm.generate_structured(...)` calls. No batching, no `asyncio.gather`. The README's "regex resolves the bulk for free; LLM only touches what regex couldn't" is misleading: schema enrichment is a per-field LLM call that always fires.

**Fix:** batch the enrichment into a single LLM call with a JSON schema returning `Dict[field_name, EnrichmentEntry]`, like `_llm_fallback_schema` already does. Falls back to per-field on parse error.

**Effort:** M

---

### #10 — Stem collision silently overwrites outputs in `normalize_batch`

**File:** `src/engine/batch.py:256` (`output_path = output_dir / f"{source_path.stem}.normalized.docx"`).

Confirmed: a directory with `doc1.docx` and `doc1.pdf` produces a single `doc1.normalized.docx`; whichever finishes second wins. No warning, no `error` tier. Quiet data loss.

**Fix:** include the source extension in the output name (`f"{source_path.stem}{source_path.suffix}.normalized.docx"`), or detect collisions ahead of time and raise.

**Effort:** S

---

## MEDIUM

### #11 — Cross-token replacement: a value containing another field's placeholder triggers re-substitution

`src/engine/batch.py:183-185, 197-199`. If `mapping["A"].value == "user content with {{B}}"`, then when the loop processes `B`, the `{{B}}` inside A's already-substituted text gets replaced with B's value. Order-dependent on dict iteration. Injection vector when source content is untrusted.

**Fix:** single-pass alternation regex OR sentinel pattern. **S**

---

### #12 — `required_headings` is documented as enforced but is unused

`src/engine/formats/_base.py:30-32`. `grep` finds no consumer beyond `describe_formats()`.

**Fix:** wire into structural OR remove field. **S to remove, M to wire.**

---

### #13 — `_classify_tier` returns `"high"` when there are no schemas and no mapping

`src/engine/batch.py:127-153`. A template with zero placeholders processes any source as "high confidence" success.

**Fix:** return `"low"` or surface `"no_fields_in_template"` error. **S**

---

### #14 — AuditLog file handle lifecycle on missed `close()`

`src/engine/security/audit.py:46-122`. No `__del__`. Forgotten `close()` keeps fd open until GC. In long-running server: leaks per request.

**Fix:** `__del__` with defensive try/except OR open-per-write pattern. **S**

---

### #15 — AuditLog mutable defaults inside a `@dataclass`

`src/engine/security/audit.py:46-58`. `_events` and `_lock` are public dataclass fields included in `__eq__`/`__repr__`.

**Fix:** `field(..., compare=False, repr=False, init=False)`. **S**

---

### #16 — Hybrid mapper catches `Exception` too broadly on LLM failure

`src/engine/hybrid_mapper.py:168-171`. Catches config errors, auth errors, rate limits — all map to "no LLM hits". User can't distinguish.

**Fix:** catch `(LLMError, ValidationError, json.JSONDecodeError, asyncio.TimeoutError)`. Re-raise rest. **S**

---

### #17 — PyPI publish workflow pins to a mutable tag

`.github/workflows/publish.yml:47`. `pypa/gh-action-pypi-publish@release/v1` is moving. Same for `actions/checkout@v4`, etc. Supply-chain risk on the PyPI publish path.

**Fix:** pin all third-party actions to full SHA. Dependabot for updates. **S**

---

### #18 — Publish workflow uses `skip-existing: true`

`.github/workflows/publish.yml:53`. Silently no-ops if the version is already on PyPI. Hides version-mismatch bugs.

**Fix:** default `false`; only enable for explicit re-runs. **S**

---

### #19 — `check_technical` orphan placeholder regex doesn't catch lowercase or namespaced tokens

`src/engine/conformity/technical.py:146-153`. Only matches uppercase. Templates with `{{name}}` or `{{user.name}}` invisible.

**Fix:** relax regex OR document loudly. **S**

---

## LOW

### #20 — Test claim "regex coverage on gold doc itself" doesn't actually validate values

`tests/test_formats.py:140-162`. Asserts `coverage >= 0.5` based on `source == "regex"` only. Never compares `mapping[s.name].value` to expected. **This is why #1 went undetected.**

**Fix (also resolves #1):** `assert mapping[s.name].value == fmt.field_examples[s.name][0]` per field. **S**

---

### #21 — Empty-doc edge in `_classify_tier` for skipped-only batches

Already in #13. Inconsistency between empty-batch (correct) and empty-schema-item (wrong).

---

### #22 — Pass-2 dead code in `_replace_tokens_in_paragraph`

`src/engine/batch.py:200-201`. After the early-return when `not needs_merge`, `if merged == full_text: return` is unreachable.

**Fix:** remove dead branch. **S**

---

## What looks good

- `validate_cpf` correctly checks the two check digits and rejects 11-of-the-same-digit patterns. Real digit-verification, not just length.
- `_has_structural_anchors` in `pattern_inference.py:138-150` is the right defense against grex's `with_conversion_of_words()` collapsing to `\w+`.
- Pass-1 / Pass-2 strategy in `_replace_tokens_in_paragraph` is correct for the cases it tests. The fragmented-runs fix is real.
- `local_only` flag is enforced consistently in both `normalize_batch` and `check_conformity` entry points (modulo the audit-not-wired issue).
- `RefusedRemoteCallError` correctly catches both `llm` and `visual_llm` parameters.
- Format dataclass is `frozen=True`. Conformity weights sum-to-1 invariant is tested across all 10 formats.
- mypy `# type: ignore` usages are minimal (7 sites) and all justified — none mask logic bugs.

---

## Test gaps confirmed

Zero tests for:

- multi-megabyte docx (memory profile)
- unicode in field values (Cyrillic / CJK / emoji)
- zip bombs (malformed archive)
- concurrent batches against shared output dir
- output stem collisions (#10)
- tokens in headers/footers/hyperlinks (#4)
- audit log integration (#2)
- `is_conformant` semantics for all-skipped (#7)
- provider error semantics for design/diff (#8)

The `test_batch.py:281` malformed-docx test only writes garbage bytes; never tests structurally-valid-but-malicious docx (e.g., a docx with an oversized media file, or a content-type spoof).

Skipping the `test_format_hybrid_mapper_extracts_from_gold_doc` value check (#20) is the single most damaging test gap because it silently masks #1.

---

## Wave K — fix order

| # | Severity | Effort | Description |
|---|----------|--------|-------------|
| 1 | CRITICAL | M | Formats produce wrong values — add value-equality test, fix pattern_inference no-label fallback |
| 3 | CRITICAL | S | ReDoS in injection_pt — single-line regex tighten |
| 5 | HIGH | S | Injection misses canonical attacks — alternation tighten |
| 7 | HIGH | S | Conformity all-skipped → is_conformant=False |
| 8 | HIGH | S | Design/diff: error → Failure not score=1.0 |
| 10 | HIGH | S | Stem collision → include extension |
| 6 | HIGH | S | PII bare-phone → CPF misclassification |
| 2 | CRITICAL | M | AuditLog wired into normalize_batch + check_conformity |
| 4 | HIGH | M | Renderer headers/footers/hyperlinks |
| 9 | HIGH | M | Schema enrichment batched into 1 LLM call |
| 17 | MED | S | Pin actions to SHA |
| 18 | MED | S | Drop `skip-existing` |
| 11 | MED | S | Single-pass replacement |
| 12 | MED | S | required_headings used or removed |
| 13 | MED | S | classify_tier on empty schemas |
| 14 | MED | S | AuditLog `__del__` |
| 15 | MED | S | AuditLog dataclass field flags |
| 16 | MED | S | Hybrid mapper exception scope |
| 19 | MED | S | Orphan placeholder regex |
| 22 | LOW | S | Dead code in pass-2 |
| 20 | LOW | S | Add value-equality test (resolves #1) |
| 21 | LOW | S | Documented as #13 |

**Estimated total to clear CRITICAL + HIGH: ~3 days of focused work.**

## PyPI block

Publish to PyPI is **blocked** until at least the 3 CRITICAL items are fixed:

1. **#1 formats produce wrong values** — shipping a "broken at first use" lib to PyPI burns the project's reputation on day 1.
2. **#2 AuditLog not wired** — README's "audit-grade" claim is false; either wire it or strip the framing.
3. **#3 ReDoS** — regulated workloads will hit adversarial input quickly.

Wave K target: clear all CRITICAL + HIGH (10 items, ~3 days). Then publish v0.8.0 to PyPI. MEDIUM/LOW can ship as v0.8.x patches.
