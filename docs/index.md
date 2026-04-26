---
title: Home
---

<div class="te-hero" markdown>
<div class="badges" markdown>
[![Release](https://img.shields.io/github/v/release/Luizhcrs/template-engine?display_name=tag&sort=semver&color=ff7a2a&label=release)](https://github.com/Luizhcrs/template-engine/releases) <span>Apache 2.0</span> <span>Python 3.11+</span>
</div>

# template-engine

<p class="lead" markdown>
Audit-grade document normalization engine. Regex-first, LLM-as-judge, zero LibreOffice. Built for regulated environments where document content cannot leak.
</p>

[Quickstart](quickstart.md){ .md-button .md-button--primary }
[GitHub](https://github.com/Luizhcrs/template-engine){ .md-button }
</div>

## Why this exists

Three problems off-the-shelf solutions don't solve together:

- **Cost** — paying the LLM per-doc when 95% of fields are mechanically extractable.
- **Compliance** — regulators want auditability + a guarantee that LGPD/HIPAA data never reached an external API.
- **Verification** — "did the candidate doc match the standard?" — text alone is not enough; structure, layout, required formats matter too.

## How it solves each

- **Hybrid mapper** — regex tier resolves what it can; only missing fields go to the LLM in a single batched call. Documents the regex resolves cost zero LLM tokens.
- **`local_only=True`** raises before any remote call. PII masking + append-only audit log + deterministic regex path replayable bit-for-bit.
- **`check_conformity`** — multi-dimensional verdict across text + structural + visual + design + technical. Each dimension scored independently. A single critical (invalid CPF, orphan placeholder, lost field) invalidates the doc regardless of the average.

## Pipeline

```
extract → schema_inference → pattern_inference → hybrid_mapper → render → semantic_diff
                                                                                  ↓
                                                                       ConformityReport
```

<div class="te-feature-grid" markdown>

<div class="te-feature" markdown>
### Regex-first
`pattern_inference` learns regexes from 3 gold docs + field examples. 10 predefined value shapes plus optional `grex`-learned. Documents the regex resolves cost zero LLM tokens.
</div>

<div class="te-feature" markdown>
### LLM as judge, not author
`semantic_diff` and the `text` / `design` conformity dimensions ask the LLM "did anything go missing?" and "does this match the standard?". The LLM does not write content; it audits.
</div>

<div class="te-feature" markdown>
### Local-only mode
`local_only=True` on `normalize_batch` and `check_conformity` raises if any LLM provider is supplied. Hard guarantee for LGPD/HIPAA-grade deployments.
</div>

<div class="te-feature" markdown>
### Multi-provider with fallback
6 providers — Gemini, OpenAI, Anthropic, Groq, Ollama, OpenRouter. `LLMRouter` chains them with automatic fallback on rate-limit / timeout.
</div>

<div class="te-feature" markdown>
### Stateless
Path / bytes in, paths / bytes / dataclasses out. No web framework, ORM, or app layer. Plug into any caller.
</div>

<div class="te-feature" markdown>
### Audit trail
`engine.security.AuditLog` writes append-only JSON Lines. Records sha256 hashes — never raw content.
</div>

</div>

## Cost by tier (Gemini Flash)

| Path | LLM calls | $/doc |
|------|-----------|-------|
| Regex resolves everything | 0 | **$0.0000** |
| Some fields fall back to LLM | 1 | ~$0.0006 |
| With `semantic_diff` enabled | 2 | ~$0.0012 |
| With `check_conformity(text + design)` | 4 | ~$0.0024 |

## Use cases

- Industrial: standardize 400 maintenance reports onto a corporate template.
- Legal: contract clause normalization with audit trail.
- Government / regulated: forms processing with `local_only=True` and PII masking.
- Migration: bulk move legacy documents to a new corporate standard.
- QA: verify a third party delivered docs that match your spec (`check_conformity`).

## Quick install

```bash
pip install "template-engine[gemini]"
```

[Continue with Quickstart →](quickstart.md){ .md-button .md-button--primary }

## License

[Apache 2.0](https://github.com/Luizhcrs/template-engine/blob/main/LICENSE) · Copyright 2026 luizhcrs
