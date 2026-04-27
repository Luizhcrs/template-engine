# template-engine

**Audit-grade document normalization engine. Regex-first, LLM-as-judge, zero LibreOffice. Built for regulated environments where document content cannot leak.**

[![CI](https://github.com/Luizhcrs/template-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/Luizhcrs/template-engine/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Release](https://img.shields.io/github/v/release/Luizhcrs/template-engine?display_name=tag&sort=semver)](https://github.com/Luizhcrs/template-engine/releases)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Typed](https://img.shields.io/badge/typed-mypy-2A6DB2.svg)](http://mypy-lang.org/)

> **Docs**: <https://luizhcrs.github.io/template-engine/>
> **Threat model + provider data residency**: [SECURITY-MODEL.md](SECURITY-MODEL.md)
> **README**: English (this file) · [Português](README.pt.md)

## Why this exists

Three problems off-the-shelf solutions don't solve together:

| Problem | This lib's answer |
|---------|------------------|
| Cost: paying the LLM per-doc when 95% of fields are extractable mechanically | **Regex-first hybrid mapper** — only fields regex couldn't fill go to the LLM in a single batched call |
| Compliance: regulators want auditability + a guarantee that LGPD/HIPAA data never reached an external API | **`local_only=True`** raises before any remote call. PII masking, append-only audit log, deterministic regex path replayable bit-for-bit |
| Verification: "did the candidate doc match the standard?" — text alone isn't enough; structure, layout, and required formats matter too | **Multi-dimensional `check_conformity`** — text + structural + visual + design + technical, each scored independently, weighted overall verdict |

## How it works

Two operations. One pipeline. Five dimensions of conformity.

```
                  template (.docx)              source docs (N x .docx/.pdf)
                        │                                  │
                        ▼                                  ▼
        ┌──────────────────────────┐         ┌──────────────────────────┐
        │ schema_inference         │         │ extractor                │
        │  detects placeholders    │         │  text + tables           │
        │  ({{X}}, [X], ___, ...)  │         └──────────────────────────┘
        └──────────────────────────┘                       │
                        │                                  ▼
                        ▼                  ┌──────────────────────────┐
        ┌──────────────────────────┐       │ pattern_inference        │
        │ FieldSchema list         │──┐    │  10 predefined shapes    │
        │  {name, type, required}  │  │    │  + grex (optional)       │
        └──────────────────────────┘  │    └──────────────────────────┘
                                      │                    │
                                      ▼                    ▼
                          ┌─────────────────────────────────────┐
                          │ hybrid_mapper                        │
                          │  Tier 1: regex per field (free)      │
                          │  Tier 2: LLM batched on missing only │
                          │  Output: source ∈ {regex, llm, miss} │
                          └─────────────────────────────────────┘
                                          │
                                          ▼
                          ┌─────────────────────────────────────┐
                          │ batch._apply_mapping_to_template     │
                          │  token substitution in docx copy     │
                          └─────────────────────────────────────┘
                                          │
                                          ▼
                          ┌─────────────────────────────────────┐
                          │ semantic_diff (LLM as judge)         │
                          │  flags missing_in_output / mismatch  │
                          │  / extra_in_output discrepancies     │
                          └─────────────────────────────────────┘
                                          │
                                          ▼
                            BatchReport: high / medium / low / error
                            per-doc mapping summary + discrepancies
```

For verification, the same primitives feed `check_conformity`:

```
                             check_conformity(template, candidate)
                                          │
            ┌─────────┬─────────┬─────────┼─────────┬─────────┐
            ▼         ▼         ▼         ▼         ▼         ▼
          text   structural  visual    design    technical    │
         (LLM)   (no LLM)   (no LLM)  (LLM mm)   (no LLM)    │
            │         │         │         │         │         │
            └─────────┴─────────┴─────────┴─────────┘         │
                              │                                │
                              ▼                                │
                  weighted score + threshold                   │
                              │                                │
                              ▼                                │
            is_conformant = (score >= 0.85) AND (zero critical) ◄
```

Cost by tier (Gemini Flash, ~3K input tokens per LLM call):

| Path | LLM calls | $/doc |
|------|-----------|-------|
| Regex resolves everything | 0 | **$0.0000** |
| Some fields fall back to LLM | 1 | ~$0.0006 |
| With `semantic_diff` enabled | 2 | ~$0.0012 |
| With `check_conformity(dimensions=[text, design])` | 4 | ~$0.0024 |

## Section-mapper pipeline (Wave L)

For **structural** templates that ship with named-but-empty sections (industrial procedures, NR-12/13, ABNT-shaped academic) and rely on heading hierarchy + tables instead of `{{X}}` tokens, use `engine.section_mapper.map_sections`:

```python
from pathlib import Path
from engine.section_mapper import map_sections

report = map_sections(
    template_path=Path("template.docx"),
    source_path=Path("source.docx"),
    output_path=Path("output.docx"),
    # similarity_mode="auto" + auto_tables=True are the defaults
)

print(f"mapped {report.mapped_count} sections; {report.tables_filled} tables filled")
```

End-to-end on Engeman dados.docx with zero config: 7/8 sections mapped, header populated (`IT.PRO.URE.387.0005`, `Rev. 01`, `Elaborado: ...`, `(PARTIDA DA ÁREA DE SÍNTESE)`), Histórico table extracted from source revisions, Responsabilidade table populated from `Compete à gerência` / `Compete aos supervisores` paragraphs.

See [Section mapper](https://luizhcrs.github.io/template-engine/concepts/section_mapper/) for the full pipeline (parser → numbering resolver → similarity matcher → renderer with line-kind decoration → tables → header filler).

## Typical batch run

```bash
template-engine normalize \
  --template ./padrao.docx \
  --source-dir ./entrada/ \
  --output-dir ./normalizados/ \
  --provider gemini \
  --gold-doc gold_01.docx --gold-doc gold_02.docx --gold-doc gold_03.docx \
  --field-examples ./examples.json \
  --report ./report.json
```

The `report.json` groups every input into a tier:

- **`high`** — regex resolved everything, no critical diff. Ship without review.
- **`medium`** — LLM filled at least one free-text field, or warning-level diff. Spot-check.
- **`low`** — orphan placeholder, missing required field, or critical diff. Open and edit.
- **`error`** — extraction or render failed.

Cost depends on what fraction of docs the regex tier resolves. When it covers all required fields, the LLM is never called and the run is free; otherwise the LLM is invoked once per missing-field doc and (optionally) once for the semantic-diff QA pass.

## Install

```bash
pip install template-engine-ia                 # core
pip install "template-engine-ia[gemini]"          # + Google Gemini
pip install "template-engine-ia[openai]"          # + OpenAI
pip install "template-engine-ia[anthropic]"       # + Anthropic Claude
pip install "template-engine-ia[ollama]"          # + local LLMs (LGPD-safe)
pip install "template-engine-ia[inference]"       # + grex regex learner
pip install "template-engine-ia[all]"             # everything
```

## Quickstart — normalize a directory

```python
import asyncio
from pathlib import Path
from engine import normalize_batch
from engine.llm.gemini_free import GeminiFreeProvider

async def main():
    report = await normalize_batch(
        template_path=Path("template.docx"),
        source_dir=Path("docs/"),
        output_dir=Path("normalized/"),
        llm=GeminiFreeProvider(api_key="AIza..."),
        gold_docs=[open(p).read() for p in Path("gold/").glob("*.txt")],
        field_examples={
            "CODIGO":      ["ABC-001", "ABC-042", "ABC-099"],
            "DATA":        ["2026-01-15", "2026-04-26", "2026-07-30"],
            "RESPONSAVEL": ["Joao Silva", "Maria Souza", "Pedro Lima"],
        },
    )
    print(report.by_tier)         # {"high": 380, "medium": 15, "low": 5, "error": 0}
    print(report.llm_call_count)  # ~25 — 380 high docs cost zero LLM

asyncio.run(main())
```

## Conformity check

```python
from engine import check_conformity

report = await check_conformity(
    template_path=Path("padrao.docx"),
    candidate_path=Path("candidato.docx"),
    llm=provider,
    schemas=schemas,
    mapping=mapping,
    dimensions=["text", "structural", "visual", "technical"],
    threshold=0.85,
)

print(report.summary_line)
# CONFORMANT score=0.92 threshold=0.85 failures=1 (critical=0)
```

`is_conformant = (score >= threshold) AND (zero critical failures)`. A single critical (invalid CPF, orphan placeholder, lost field) invalidates the doc regardless of weighted score.

CLI: `template-engine conformity --template T --candidate C --provider gemini --threshold 0.85`.

## Local-only mode (LGPD/HIPAA)

```python
report = await normalize_batch(
    template_path, source_dir, output_dir,
    llm=None,
    field_examples=examples,
    gold_docs=golds,
    local_only=True,   # raises RefusedRemoteCallError if any LLM is supplied
)
```

In local-only mode, only the regex tier runs. Missing fields stay missing. See [SECURITY-MODEL.md](SECURITY-MODEL.md) for the full operating-mode matrix and per-provider data residency.

## PII masking

```python
from engine.security import mask_pii, unmask

masked, mask = mask_pii(source_text)
# masked: "Cliente <CPF_001> nascido em <DATE>... contato <EMAIL_001>"
response = await llm.generate_structured(prompt(masked), schema)
restored = unmask(json.dumps(response), mask)
```

Detects CPF, CNPJ, email, BR phone, RG, CEP. Each unique original value gets one stable token; `unmask` restores originals from the response.

## Multi-provider with fallback

```python
from engine.llm import LLMRouter
from engine.llm.groq_provider import GroqProvider
from engine.llm.gemini_free import GeminiFreeProvider
from engine.llm.openai_provider import OpenAIProvider

router = LLMRouter([
    GroqProvider(api_key=g_key),         # primary: fast + cheap
    GeminiFreeProvider(api_key=ge_key),  # fallback: free tier
    OpenAIProvider(api_key=o_key),       # last resort
])

report = await normalize_batch(template, source_dir, output_dir, llm=router, ...)
```

Only `LLMRateLimit` / `LLMTimeout` trigger fallback. Generic `LLMError` propagates so the caller sees provider-specific issues.

## Design decisions (why it works)

- **Stateless.** Path / bytes in, paths / bytes / dataclasses out. No web framework, no ORM, no app layer to bring along.
- **Frozen dataclasses across the public API.** `MappingResult`, `Failure`, `ConformityReport`, etc. Equality + hashing for free, no accidental mutation across pipeline boundaries.
- **Protocol-based LLM provider** (not ABC). Adding a provider is implementing one method. No inheritance, no registry magic.
- **Regex tier rejects over-generalization.** When `grex` learns a pattern that collapses to `\w+` without structural anchors, the lib falls back to free-text instead of accepting a false sense of precision.
- **`is_conformant` requires zero criticals.** A high weighted score doesn't override a single critical failure (invalid CPF, orphan placeholder). Matches the regulator's mental model: "any deal-breaker = fail".
- **Audit hashes, not raw content.** `AuditLog` records sha256 of inputs and outputs so reviewers can prove a document was processed without the audit file becoming a secondary data store.

## Add your own provider

```python
from engine.llm.base import LLMError, LLMRateLimit, LLMTimeout

class MyProvider:
    name = "my-provider"
    model = "default"

    def __init__(self, api_key: str, model: str | None = None) -> None:
        if not api_key:
            raise RuntimeError("api_key required")

    async def generate_structured(self, prompt: str, json_schema: dict) -> dict:
        # call API, parse JSON; raise LLMRateLimit / LLMTimeout / LLMError as needed
        ...
```

## Development

```bash
pip install -e ".[dev]"
ruff check . && ruff format --check . && mypy src/engine && pytest
```

189 tests across providers, pattern inference (Wave A), batch orchestrator (Wave D), conformity validator (Wave F), security primitives (Wave G).

## Roadmap

[ROADMAP.md](ROADMAP.md) — Wave A/D/E/F/G/H shipped on v0.6.

## Contributing

Issues and PRs welcome. See [CONTRIBUTING.md](CONTRIBUTING.md). For security issues see [SECURITY.md](SECURITY.md).

## License

[Apache 2.0](LICENSE) — Copyright 2026 luizhcrs.
