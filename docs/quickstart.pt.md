# Comece aqui

Pipeline ponta-a-ponta em menos de 60 segundos.

## Instalação

=== "Gemini (padrão)"

    ```bash
    pip install "template-engine[gemini]"
    ```

=== "OpenAI"

    ```bash
    pip install "template-engine[openai]"
    ```

=== "Anthropic"

    ```bash
    pip install "template-engine[anthropic]"
    ```

=== "Todos providers"

    ```bash
    pip install "template-engine[all]"
    ```

## Setup

Defina sua API key:

```bash
export GEMINI_API_KEY="AIza..."
```

## Pipeline em 4 passos

```python
import asyncio
from pathlib import Path
from engine import (
    create_preset, load_preset, extract, map_content, render,
)
from engine.llm.gemini_free import GeminiFreeProvider

async def main():
    provider = GeminiFreeProvider(api_key="AIza...")

    # 1. Aprende padrão a partir do template + docs de referência
    preset_dir = await create_preset(
        llm=provider,
        template_path=Path("template.docx"),
        gold_paths=[Path("gold_01.docx"), Path("gold_02.docx")],
        dest_dir=Path("./presets/my-template"),
    )

    # 2. Carrega
    preset = load_preset(preset_dir)

    # 3. Mapeia conteúdo do source em JSON estruturado
    doc = extract(Path("source.docx"))
    data = await map_content(preset, doc.text, provider)

    # 4. Renderiza .docx final
    render(preset, data, output_path=Path("out.docx"))

asyncio.run(main())
```

## O que cada passo faz

1. **`create_preset`** chama o LLM 1x para analisar template + gold docs. Gera `pattern.md`, `schema.json`, `render_ops.yaml`, `validation.yaml`.
2. **`load_preset`** carrega o bundle pronto pra uso.
3. **`map_content`** chama o LLM com prompt few-shot e extrai JSON estruturado do source.
4. **`render`** aplica as operações YAML sobre o template + JSON e produz `.docx` final determinístico.

## Validar saída

```python
from engine import validate, calculate_confidence, confidence_label

result = validate(doc.text, data, preset.validation)
score = calculate_confidence(result)
label = confidence_label(score)
print(f"{score:.2f} -> {label.value}")
```

## Com router (fallback)

```python
from engine.llm import LLMRouter
from engine.llm.groq_provider import GroqProvider
from engine.llm.gemini_free import GeminiFreeProvider
from engine.llm.openai_provider import OpenAIProvider

router = LLMRouter([
    GroqProvider(api_key=g_key),         # rápido + barato
    GeminiFreeProvider(api_key=ge_key),  # fallback grátis
    OpenAIProvider(api_key=o_key),       # último recurso
])

# Mesma interface dos providers individuais
data = await map_content(preset, source_text, router)
```

## Próximos passos

- [Conceitos → Pipeline](concepts/pipeline.md)
- [Conceitos → Anatomia do preset](concepts/preset.md)
- [Providers → Visão geral](providers/index.md)
- [Contribuindo](contributing.md)
