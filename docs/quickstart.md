# Quickstart

End-to-end normalization in under 60 seconds.

## Install

=== "Gemini (default)"

    ```bash
    pip install "template-engine-ia[gemini]"
    ```

=== "OpenAI"

    ```bash
    pip install "template-engine-ia[openai]"
    ```

=== "Anthropic"

    ```bash
    pip install "template-engine-ia[anthropic]"
    ```

=== "Local-only (Ollama, no remote LLM)"

    ```bash
    pip install "template-engine-ia[ollama]"
    ```

=== "All providers"

    ```bash
    pip install "template-engine-ia[all]"
    ```

## Setup

Set your API key:

```bash
export GEMINI_API_KEY="AIza..."
```

## Normalize a directory

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

## What each stage does

1. **`schema_inference`** scans the template for placeholders (`{{X}}`, `[X]`, `___`, etc) and builds a `FieldSchema` list. With `llm=` supplied, the LLM enriches each field with an inferred `field_type` / `format_hint` / `required`.
2. **`pattern_inference`** synthesizes one regex per field from the gold docs + example values. Three tiers: predefined shapes, optional `grex`-learned, free-text fallback.
3. **`hybrid_mapper`** runs the regex per field on each source. Fields the regex fills get `source="regex"`. Fields it can't get sent to the LLM in a single batched call. Output: `{field: MappingResult{value, source, confidence}}`.
4. **Renderer** copies the template, substitutes the placeholder tokens with mapped values, and saves to `output_dir`.
5. **`semantic_diff`** asks the LLM whether anything from the source went missing. Discrepancies are graded `critical` / `warning` / `info`.
6. **Tier classification** buckets each doc into `high` / `medium` / `low` / `error`.

## CLI

```bash
template-engine normalize \
  --template template.docx \
  --source-dir docs/ \
  --output-dir normalized/ \
  --provider gemini \
  --gold-doc gold1.docx --gold-doc gold2.docx --gold-doc gold3.docx \
  --field-examples examples.json \
  --report report.json
```

## Bundled formats (Wave H)

5 ready-to-use formats: `abnt_artigo`, `abnt_tcc`, `abnt_referencia`, `laudo_nr12`, `contrato_simples`. Each ships schemas + gold docs + field examples + tuned conformity weights.

```python
from engine import load_format, list_formats, normalize_batch

print(list_formats())
# ['abnt_artigo', 'abnt_referencia', 'abnt_tcc', 'contrato_simples', 'laudo_nr12']

fmt = load_format("laudo_nr12")
report = await normalize_batch(
    template_path=Path("template.docx"),
    source_dir=Path("docs/"),
    output_dir=Path("normalized/"),
    field_examples=fmt.field_examples,    # auto-fill
    gold_docs=fmt.gold_docs,              # auto-fill
)
```

CLI:

```bash
template-engine list-formats
template-engine normalize --format laudo_nr12 --template T --source-dir SD --output-dir OD
template-engine conformity --format abnt_tcc --template T --candidate C --provider gemini
```

With `--format`, the format's weights and threshold become defaults (`laudo_nr12` = technical 0.45, threshold 0.90).

## Conformity check

After normalization, verify a candidate matches the standard:

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

for dim, dr in report.by_dimension.items():
    print(f"  {dim:<11} score={dr.score:.3f}  failures={len(dr.failures)}")
```

CLI: `template-engine conformity --template T --candidate C --provider gemini --threshold 0.85`.

## Local-only mode (LGPD/HIPAA)

```python
report = await normalize_batch(
    template_path, source_dir, output_dir,
    llm=None,
    field_examples=examples,
    gold_docs=golds,
    local_only=True,    # raises if any LLM is supplied
)
```

In local-only mode, only the regex tier runs. Missing fields stay missing. See [Security model](https://github.com/Luizhcrs/template-engine/blob/main/SECURITY-MODEL.md) for the operating-mode matrix and provider data residency.

## With router (fallback)

```python
from engine.llm import LLMRouter
from engine.llm.groq_provider import GroqProvider
from engine.llm.gemini_free import GeminiFreeProvider
from engine.llm.openai_provider import OpenAIProvider

router = LLMRouter([
    GroqProvider(api_key=g_key),         # fast + cheap
    GeminiFreeProvider(api_key=ge_key),  # free fallback
    OpenAIProvider(api_key=o_key),       # last resort
])

report = await normalize_batch(template, source_dir, output_dir, llm=router, ...)
```

## PII masking before LLM

```python
from engine.security import mask_pii, unmask

masked, mask = mask_pii(source_text)
response = await llm.generate_structured(prompt(masked), schema)
restored = unmask(json.dumps(response), mask)
```

Detects CPF, CNPJ, email, BR phone, RG, CEP. Each unique value gets one stable token; `unmask` restores originals after the response comes back.

## Next steps

- [Concepts → Pipeline](concepts/pipeline.md)
- [Concepts → Architecture](concepts/architecture.md)
- [Providers → Overview](providers/index.md)
- [Contributing](contributing.md)
