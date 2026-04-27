# Heavy testing plan — template-engine v0.7.1+

Context: today the lib has **269 unit tests** that exercise correctness on
small, controlled inputs. Real production deployments hit shapes those tests
do not cover — large batches, malformed input, concurrency, unicode, adversarial
content, slow LLM providers. This plan groups the gaps and proposes test
suites that validate behavior under load and stress.

The plan is intentionally broader than what fits into a single wave; treat it
as a roadmap. Each suite stands alone and ships with a green/red gate the
release process can rely on.

## Suite 1 — Renderer stress (fragmented runs)

**Why.** Wave I fixed token-spans-runs in synthetic tests. Word documents in
the wild produce far weirder fragmentation: spell-check splits, language
markers, comment ranges, change-tracking, smart-quotes. The two-pass renderer
must hold up against samples we did not write.

**Scope.**

- 30+ pre-recorded `.docx` fixtures with intentionally fragmented placeholders
  - `{{X}}` split across 2, 3, 5, 10 runs
  - placeholders inside table cells, headers, footers, footnotes, comments
  - mixed scripts (Latin, Cyrillic, CJK, RTL Arabic)
  - placeholder boundary at run with `<w:rPr>` style change (italic / bold mid-token)
  - placeholders in numbered lists, multi-level lists
  - placeholders inside hyperlinks and bookmark spans
- One generated fixture per pattern, committed under `tests/fixtures/runs/*.docx`
- Property-based test (`hypothesis`): generate random run splits of `{{NAME}}`
  across 1-15 runs, assert post-render equals expected value

**Tooling.** `python-docx` for fixture authoring, `hypothesis` for fuzz, `pytest`
parametrized. 50-100 cases.

**Done when.** All 50+ cases pass on Windows + Linux + macOS. No regression
in the 6 existing fragmented-runs tests.

## Suite 2 — Real-world `.docx` corpus

**Why.** Synthetic docs miss the messy parts of Word output: stray
`<w:proofErr>`, `<w:lang>` runs, smart-tags, OLE objects, content controls
(legacy form fields), embedded images.

**Scope.**

- Curate 20-50 anonymized `.docx` files from public sources (gov templates,
  academic templates, open-source legal templates)
- For each: extract text → assert `extract()` returns sane structure
- For 10 of them with placeholders: render via `_apply_mapping_to_template`
  with synthetic mapping → assert no orphan tokens, no corruption
- Snapshot test: re-extract the rendered output, assert paragraph count
  matches template within ±2

**Tooling.** A `tests/corpus/` directory with sources from public repos
(redistribution-safe). `pytest --corpus` flag to run only under request (slow).

**Done when.** 100% of the corpus extracts without `python-docx` errors;
≥95% renders without orphan tokens or schema fingerprint divergence.

## Suite 3 — Batch scale + concurrency

**Why.** `normalize_batch` uses an asyncio Semaphore but the rest of the
pipeline (extract, regex, render) is synchronous. Behaviour at 1k or 10k docs
is unverified. Disk IO contention, memory growth, error-isolation between
items, and Semaphore throughput are unknowns.

**Scope.**

- **Scale**: synthesize 1k, 5k, 10k tiny `.docx` files (same template, varying
  field values). Run `normalize_batch` regex-only. Assert:
  - Wall-clock time scales near-linearly with `max_concurrent`
  - RSS peak under 1 GB at 10k docs
  - Output dir has exactly N rendered files
  - No exceptions raised, all items reported (`high`/`error`)
- **Error isolation**: in a 100-doc batch, intentionally corrupt 5 docs (bad
  zip, missing parts). Assert: 95 items succeed, 5 marked `error`, batch does
  not crash
- **Concurrency stress**: run 4 batches against the same output dir
  concurrently, different file-name prefixes. Assert no file collisions, no
  partial writes
- **LLM rate-limit handling**: stub LLM that raises `LLMRateLimit` randomly
  on 30% of calls. Assert router fallback kicks in, batch still finishes,
  `report.llm_call_count` reflects retries

**Tooling.** `pytest-asyncio` for the orchestrator path; `psutil` for RSS
metrics; `tempfile` for ephemeral source/output dirs.

**Done when.** 10k regex-only batch finishes in <2 min on a 4-core box, RSS
<1 GB, zero false errors, output deterministic across runs.

## Suite 4 — Conformity dimensions under stress

**Why.** Each dimension has a few unit tests on synthetic input. They do
not cover what happens when input violates the dimension's assumptions.

**Scope.**

- **structural**: candidate with 0 paragraphs / no headings / 1000 H1s /
  20-row 50-col table / nested tables / merged cells. Assert no crash, score
  in `[0,1]`
- **visual**: candidate with text in CJK / RTL / huge font sizes. Assert
  PIL rendering does not OOM. With Pillow uninstalled, assert clean skip
  (already covered, regression-only)
- **technical**: feed a candidate with thousands of orphan placeholders
  (`{{X1}} {{X2}} ... {{X9999}}`). Assert linear runtime, no OOM
- **text**: stub LLM returns malformed JSON, raises arbitrary exception,
  returns 1000 discrepancies. Assert graceful degradation
- **design**: stub `ConformityVisualProvider` returns negative score, score
  > 1, missing keys, list instead of dict. Assert clamping + skip behavior

**Tooling.** Existing test patterns. ~40 new tests.

**Done when.** Each dimension survives ≥10 adversarial inputs without crash
or wrong-class score.

## Suite 5 — Security primitives adversarial

**Why.** Security functions need adversarial validation, not just happy-path
tests.

**Scope.**

- **PII masking**:
  - CPF with leading/trailing whitespace, half-width / full-width digits,
    invalid check digits (still should mask, but log warn)
  - CNPJ vs CPF disambiguation when adjacent in same line
  - Email with subdomains, plus-tags, IDN punycode
  - Phone with `+55`, country code, ramal, formatted with parens
  - RG with 'X' check digit, with dots, without dots
  - 1000-occurrence dedup performance
  - Round-trip: `unmask(mask_pii(text)[0]) == text` for 100 random fixtures
- **Prompt injection**:
  - Multi-line attacks ("ignore\nprevious\ninstructions")
  - Unicode normalization bypass (NFKC variants of "ignore")
  - Base64-encoded instructions
  - PT-BR variant coverage gaps
  - ReDoS check: pathological input (`("x" * 100000)`) finishes in <1s
  - False-positive rate on a legit corpus of 100 PT-BR business docs
- **Audit log**:
  - Concurrency: 8 threads, 10k events each, all written, no corruption
  - Multi-process: fail loudly if same `path` opened twice (or document
    OS-level lock guidance)
  - File rotation when log grows > 100 MB (do we need rotation? document
    explicitly)
  - JSONL strict-parse: every line round-trips through `json.loads`
- **local_only**:
  - Audit every code path: `normalize_batch`, `check_conformity`,
    `enrich_with_llm`, `map_hybrid`, `diff_documents`, `check_text`,
    `check_design`. For each, with `local_only=True` + LLM provided, assert
    `RefusedRemoteCallError` is raised before any network call

**Tooling.** `hypothesis` for round-trip property tests; `concurrent.futures`
for concurrency; `timeit` for ReDoS gates.

**Done when.** All adversarial cases handled correctly; PII round-trip 100%;
ReDoS gate <1s on 100k input; local_only audit closes every code path.

## Suite 6 — Format quality property tests

**Why.** Today's format tests assert structural sanity (3 golds, weights sum
to 1, examples appear in golds). They do not assert that the format
**actually works** end-to-end on a synthetic source doc the format itself
generates.

**Scope.**

- For every bundled format:
  1. Build a synthetic candidate by templating one of the format's gold docs
     with a fresh value set
  2. Run `infer_field_patterns(gold_docs, field_examples)` to get patterns
  3. Run `apply_inferred(patterns, candidate)` to extract values
  4. Assert ≥80% of fields extracted match the planted values
  5. Run `check_conformity(template=fresh, candidate=fresh, format=fmt)`
     with all dimensions enabled (LLM dims skipped via `llm=None`)
  6. Assert `is_conformant=True`, `score >= fmt.recommended_threshold`

**Tooling.** Pure pytest, parametrized over `_ALL_FORMATS`.

**Done when.** All 10 formats round-trip with ≥80% extraction and pass their
own recommended threshold against a synthetic conforming doc.

## Suite 7 — Real LLM integration (live, opt-in)

**Why.** All current LLM tests use stubs. We never validate that the prompts
we ship actually work against real Gemini / OpenAI / Anthropic. Drift in
their JSON-mode behavior, schema enforcement, or content policy could break
us silently.

**Scope.**

- `tests/integration/test_live_providers.py` (skipped unless API keys present
  and `--live` flag passed)
- For each of the 6 providers:
  - `generate_structured` round-trip on a small JSON Schema
  - `hybrid_mapper.map_hybrid` LLM fallback with a deliberately ambiguous
    field
  - `semantic_diff.diff_documents` on a 5-paragraph source vs output where 1
    field was lost
- Track cost per run; emit a `live_run_report.json` in CI logs
- Run weekly on a schedule, not per-PR (cost control)

**Tooling.** GitHub Actions cron + `secrets.GEMINI_API_KEY` etc. Hard
budget cap (e.g. abort if accumulated cost > $0.50/run).

**Done when.** All 6 providers + the 3 high-leverage pipelines (hybrid /
semantic_diff / conformity-text) green on a real run.

## Suite 8 — CLI surface tests

**Why.** CLI is the user-facing entry. Today's tests skip it entirely.

**Scope.**

- typer's `CliRunner` to invoke each subcommand
  - `info`, `version`, `extract`, `normalize`, `conformity`, `list-formats`
- Argument validation: missing required args, mutually exclusive flags,
  unknown format, unknown provider
- `--json` output of `extract` is valid JSON
- `--report report.json` of `normalize` is valid JSON and matches schema
- `--format <name>` correctly merges with explicit `--gold-doc` /
  `--field-examples` (explicit wins or merges?)
- `--local-only` end-to-end: provider supplied → exit nonzero with the
  expected error message

**Tooling.** `typer.testing.CliRunner`. ~30 tests.

**Done when.** Every CLI flag covered; help output snapshot-tested.

## Suite 9 — Cross-platform CI matrix expansion

**Why.** CI runs on Ubuntu only today. Windows-specific bugs (cp1252 stdout
encoding, `cp1252` errors with emoji, `\r\n` line endings in audit log) are
silently ignored.

**Scope.**

- Add `windows-latest` and `macos-latest` to the `ci.yml` matrix
- Force `PYTHONIOENCODING=utf-8` environment in workflow steps
- Add a smoke test that prints unicode (CJK) and asserts no encoding error
- Audit `AuditLog` line endings on Windows: must be `\n` only

**Tooling.** GitHub Actions matrix.

**Done when.** Matrix green on `[ubuntu-latest, windows-latest, macos-latest]
× [3.11, 3.12, 3.13]` (9 cells).

## Suite 10 — Performance baseline + regression gate

**Why.** Refactors silently regress performance. We do not measure today.

**Scope.**

- `pytest-benchmark` baseline for hot paths:
  - `extract` on a 100-page docx
  - `pattern_inference.infer_field_patterns` with 10 fields × 3 examples
  - `apply_inferred` on a 50 KB text with 10 patterns
  - `_apply_mapping_to_template` with 10 placeholders × 200 paragraphs
  - `check_conformity(structural+technical)` on a 100-page candidate
- Commit baseline JSON; CI fails if any path regresses by >25%

**Tooling.** `pytest-benchmark`, comparison against committed baseline.

**Done when.** All 5 hot paths benchmarked; regression gate active in CI.

## Priority + sequencing

| Suite | Priority | Why |
|-------|----------|-----|
| 1. Renderer stress | **P0** | Wave I fix needs to hold up; this is the project's most-real bug area |
| 5. Security adversarial | **P0** | Security primitives are a core differentiator; they must withstand red-team |
| 4. Conformity stress | **P1** | Validates the user-facing verdict isn't fragile |
| 3. Batch scale | **P1** | Validates production throughput claim |
| 8. CLI surface | **P1** | User-facing, currently uncovered |
| 6. Format property | **P2** | Quality gate per bundled format |
| 9. Cross-platform CI | **P2** | Catches Windows/macOS regressions |
| 2. Real-world corpus | **P3** | Curation effort high; payoff long-tail |
| 7. Live LLM integration | **P3** | Cost + flakiness; weekly cron only |
| 10. Performance baseline | **P3** | Nice-to-have; only if hot path is suspect |

## Rough effort

| Suite | Effort |
|-------|--------|
| 1 | M (3-5 days, mostly fixture authoring) |
| 5 | L (5-7 days, hypothesis + concurrency + coverage audit) |
| 4 | M (3-4 days) |
| 3 | M (3 days, fixture synthesis + asyncio stress) |
| 8 | S (1-2 days) |
| 6 | S (1 day, parametrized) |
| 9 | S (1 day, workflow edit) |
| 2 | L (5+ days, corpus curation legal) |
| 7 | M (3 days + cost setup) |
| 10 | S (1 day) |

## Critério done

The project ships with a "Heavy tests" workflow run separately from CI:

```
make test-fast    # current 269 tests, runs on every PR (target <60s)
make test-heavy   # suites 1, 4, 5, 6, 8 (target <10 min)
make test-corpus  # suite 2 (manual / weekly cron)
make test-scale   # suite 3 (manual / pre-release)
make test-live    # suite 7 (weekly cron with cost cap)
make test-bench   # suite 10 (pre-release)
```

Heavy gates run on `main` push. P0 + P1 suites must be green before any tag.

The lib will not be considered "production-ready" until P0 + P1 suites are
implemented and green on the full CI matrix. Today's 269 tests are necessary
but not sufficient.
