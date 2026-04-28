# Comece aqui

Normalização ponta-a-ponta em menos de 60 segundos.

## Instalação

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

=== "Local-only (Ollama, sem LLM remoto)"

    ```bash
    pip install "template-engine-ia[ollama]"
    ```

=== "Todos os providers"

    ```bash
    pip install "template-engine-ia[all]"
    ```

## Setup

Defina sua API key:

```bash
export GEMINI_API_KEY="AIza..."
```

## Normalizar um diretório

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
    print(report.llm_call_count)  # ~25 — 380 high docs custaram zero LLM

asyncio.run(main())
```

## O que cada estágio faz

1. **`schema_inference`** escaneia o template buscando placeholders (`{{X}}`, `[X]`, `___`, etc) e monta a lista `FieldSchema`. Com `llm=` o LLM enriquece cada campo com `field_type` / `format_hint` / `required` inferidos.
2. **`pattern_inference`** sintetiza uma regex por campo a partir dos gold docs + valores de exemplo. Três tiers: shapes pré-definidas, opcional `grex`-learned, fallback freetext.
3. **`hybrid_mapper`** roda regex por campo em cada source. Campos que regex pega ficam `source="regex"`. Campos que não pega vão pra LLM em uma chamada batched. Output: `{field: MappingResult{value, source, confidence}}`.
4. **Renderer** copia o template, substitui os placeholders pelos valores mapeados, salva em `output_dir`.
5. **`semantic_diff`** pergunta ao LLM se algo do source sumiu. Discrepancies graduadas `critical` / `warning` / `info`.
6. **Tier classification** classifica cada doc em `high` / `medium` / `low` / `error`.

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

## Formatos bundled

5 formatos prontos: `abnt_artigo`, `abnt_tcc`, `abnt_referencia`, `laudo_nr12`, `contrato_simples`. Cada um traz schemas + gold docs + field examples + conformity weights tunados.

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

Com `--format`, weights e threshold do format viram default (`laudo_nr12` = technical 0.45, threshold 0.90).

## Verificar conformidade

Após normalizar, verificar se um candidato bate com o padrão:

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

## Modo local-only (LGPD/HIPAA)

```python
report = await normalize_batch(
    template_path, source_dir, output_dir,
    llm=None,
    field_examples=examples,
    gold_docs=golds,
    local_only=True,    # raise se qualquer LLM for passado
)
```

Em local-only só roda o tier regex. Campos missing ficam missing. Veja [Security model](https://github.com/Luizhcrs/template-engine/blob/main/SECURITY-MODEL.md) pra matriz de modos e residência de dados por provider.

## Com router (fallback)

```python
from engine.llm import LLMRouter
from engine.llm.groq_provider import GroqProvider
from engine.llm.gemini_free import GeminiFreeProvider
from engine.llm.openai_provider import OpenAIProvider

router = LLMRouter([
    GroqProvider(api_key=g_key),         # rápido + barato
    GeminiFreeProvider(api_key=ge_key),  # fallback free
    OpenAIProvider(api_key=o_key),       # último recurso
])

report = await normalize_batch(template, source_dir, output_dir, llm=router, ...)
```

## PII masking antes do LLM

```python
from engine.security import mask_pii, unmask

masked, mask = mask_pii(source_text)
response = await llm.generate_structured(prompt(masked), schema)
restored = unmask(json.dumps(response), mask)
```

Detecta CPF, CNPJ, email, telefone (BR), RG, CEP. Cada valor único = 1 token estável; `unmask` restaura originais quando a resposta volta.

## Próximos passos

- [Conceitos → Pipeline](concepts/pipeline.md)
- [Conceitos → Arquitetura](concepts/architecture.md)
- [Providers → Visão geral](providers/index.md)
- [Contribuir](contributing.md)
