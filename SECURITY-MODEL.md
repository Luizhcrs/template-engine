# Security Model — template-engine

This document describes the threat model, security primitives, and provider
data residency for `template-engine` v0.5+.

Audience: operators deploying the lib in regulated environments (LGPD, HIPAA,
internal data-sovereignty policies). If you only run prototypes, the defaults
are safe but you can ignore the audit / local-only sections.

## Threat model

| Threat | Mitigation |
|--------|------------|
| Document content leaking to a remote LLM | `local_only=True` flag on `normalize_batch` and `check_conformity`. Engine raises `RefusedRemoteCallError` if any LLM provider is supplied while the flag is set. |
| Personal data (CPF, email, phone) reaching the LLM provider | `engine.security.mask_pii(text)` returns reversible tokens. Use before building any prompt; restore via `unmask` on the response. |
| Adversarial input ("ignore previous instructions") manipulating the LLM | Two layers: (1) prompts wrap untrusted content in `<<<UNTRUSTED_*>>>` delimiters with explicit instructions never to follow content inside; (2) `engine.security.detect_prompt_injection(text, mode="reject")` blocks known patterns before the call. |
| Hallucinated fields surviving extraction | `hybrid_mapper` records the source of each value (`regex` / `llm` / `missing`). Tier `low` in `BatchReport` flags any LLM-sourced field that lacks regex backing. `conformity` `technical` dimension validates formats and rejects orphan placeholders. |
| Audit gap (regulator asks "what touched this doc?") | `engine.security.AuditLog(path)` writes append-only JSON Lines. Records hashes (sha256) of inputs/outputs — no raw content. |
| Provider compromised / unavailable | `LLMRouter` fails over to the next provider on `LLMRateLimit` / `LLMTimeout`. `AllProvidersFailed` raised when exhausted. |
| Path traversal via untrusted template path | Caller must sanitize. Engine reads exactly the path supplied. No magic resolution. |
| Malicious docx (xml bomb, invalid zip) | `python-docx` raises on parse failure → wrapped as `tier="error"` per item, batch continues. |

## Operating modes

### 1. Local-only (zero LLM)

Strongest. The engine touches no external service. Required for highly
sensitive deployments.

```python
from engine import normalize_batch, check_conformity

# Pattern inference + token substitution only
report = await normalize_batch(
    template_path,
    source_dir,
    output_dir,
    llm=None,
    field_examples=examples,
    gold_docs=gold_docs,
    local_only=True,
)

# Conformity: structural / visual / technical only (no text/design)
conf = await check_conformity(
    template,
    candidate,
    schemas=schemas,
    mapping=mapping,
    dimensions=["structural", "visual", "technical"],
    local_only=True,
)
```

Capabilities in this mode:

- Schema inference (placeholder detection)
- Pattern inference (regex + grex)
- Hybrid mapping — regex tier only; missing fields stay missing
- Token-substitution rendering
- Structural / visual / technical conformity dimensions
- Format validators (CPF / CEP / iso_date / br_date / email / phone_br / uf)
- Orphan-placeholder check

Out of scope in this mode:

- Schema enrichment (no `field_type` inference)
- LLM fallback for unrecognized fields
- `semantic_diff` text dimension
- `design` conformity dimension

### 2. PII-masked LLM

Documents have personal data, but the LLM still adds value (free-text mapping,
conformity judging).

```python
from engine.security import mask_pii, unmask

source_text = open(source_path).read()
masked, mask = mask_pii(source_text)
result = await llm.generate_structured(prompt(masked), schema)
restored = unmask(json.dumps(result), mask)
```

Patterns detected: CPF, CNPJ, email, phone (Brazilian), RG, CEP. Each unique
value gets one stable token (`<CPF_001>`); repeated occurrences reuse the
token.

### 3. Audit-trace LLM

Same as mode 2 but every LLM-touching operation logs a structured record.

```python
from engine.security import AuditLog, sha256_hex
from pathlib import Path

audit = AuditLog(path=Path("audit/run-2026-04-26.jsonl"))

# After each pipeline step:
audit.log_event(
    "hybrid_mapper.llm_call",
    doc_hash=sha256_hex(source_text),
    llm_provider=llm.name,
    llm_model=llm.model,
    fields_touched=["NOTAS", "OBSERVACOES"],
    llm_input_hash=sha256_hex(prompt),
    llm_output_hash=sha256_hex(json.dumps(response)),
)
```

The audit file is JSON Lines (one event per line) with these fixed fields when
present: `ts`, `event`, `doc_hash`, `dimension`, `source`, `llm_provider`,
`llm_model`, `fields_touched`, `llm_input_hash`, `llm_output_hash`, `extra`.

Hashes — not raw content — are recorded. Reviewers can prove a document was
processed without the audit file becoming a secondary data store.

## Provider data residency

`template-engine` does not select a region for you. The provider you wire in
controls where data flows. This table reflects vendor defaults as of
2026-04-26; verify with each vendor before relying on it.

| Provider | Default region | Notes |
|----------|----------------|-------|
| `engine.llm.gemini_free` | US (Google) | Free tier may be excluded from data-deletion contracts. Paid Gemini Vertex AI lets you pin a region. |
| `engine.llm.openai_provider` | US | OpenAI Enterprise contracts can route to EU. Standard API does not. |
| `engine.llm.anthropic_provider` | US | AWS Bedrock Anthropic offers EU regions; the direct API does not. |
| `engine.llm.groq_provider` | US | Groq runs only in US data centers as of 2026. |
| `engine.llm.ollama_provider` | local host | No external network call. Use this for LGPD/HIPAA. |
| `engine.llm.openrouter_provider` | varies (OpenRouter routes per model) | Their dashboard exposes per-model region. |

Local-only mode (`local_only=True` + `llm=None`) is the only configuration
guaranteed to keep data on the host.

## Reproducibility guarantees

| Path | Deterministic? |
|------|----------------|
| `extract` (docx / pdf → text) | yes |
| `schema_inference.detect_placeholders` | yes |
| `pattern_inference.infer_field_patterns` | yes |
| `pattern_inference.apply_inferred` | yes |
| `hybrid_mapper.map_hybrid` (regex tier) | yes |
| `hybrid_mapper.map_hybrid` (LLM fallback) | no (provider-dependent) |
| `batch._apply_mapping_to_template` (renderer) | yes |
| `semantic_diff.diff_documents` | no (LLM) |
| `conformity.check_structural` | yes |
| `conformity.check_visual` | yes |
| `conformity.check_technical` | yes |
| `conformity.check_text` | no (LLM) |
| `conformity.check_design` | no (LLM multimodal) |

For audit purposes: anything marked "yes" can be replayed bit-for-bit. LLM
paths cannot — record `llm_input_hash` + `llm_output_hash` so the regulator
sees what was sent and what came back.

## Choosing a mode for common compliance frameworks

| Framework | Recommended mode |
|-----------|------------------|
| LGPD (Brazilian general data) | Mode 2 + audit, or Mode 1 if data is sensitive (saúde, financeiro). |
| HIPAA | Mode 1 only. No PHI may transit a non-BAA-covered LLM. Ollama on-prem is the supported path. |
| SOC 2 / ISO 27001 internal | Mode 3. Record every LLM touch. |
| Internal R&D / non-regulated | Default (no special flags). Mode 2 if you want to be cautious. |

## Reporting vulnerabilities

See `SECURITY.md` for the responsible disclosure process.

## What this lib does NOT do

- No PII detection beyond the patterns listed (no name detection, address
  parsing, etc). For broader detection, integrate Presidio or a managed
  service before calling the engine.
- No encryption at rest. Caller owns disk encryption / KMS.
- No client-side PKI / signed audit logs. Pipe `AuditLog` output through a
  signing layer if your regulator requires non-repudiation.
- No multi-tenant isolation. The lib is stateless; the calling application is
  responsible for tenant separation.
