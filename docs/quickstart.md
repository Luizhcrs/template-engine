# Quickstart

## Install

```bash
pip install "template-engine[gemini]"
```

Para outros providers, use o extra correspondente (ex: `template-engine[openai]` quando disponível).

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

    # 1. Aprende padrão
    preset_dir = await create_preset(
        llm=provider,
        template_path=Path("template.docx"),
        gold_paths=[Path("gold_01.docx"), Path("gold_02.docx")],
        dest_dir=Path("./presets/my-template"),
    )

    # 2. Carrega
    preset = load_preset(preset_dir)

    # 3. Mapeia
    doc = extract(Path("source.docx"))
    data = await map_content(preset, doc.text, provider)

    # 4. Renderiza
    render(preset, data, output_path=Path("out.docx"))

asyncio.run(main())
```

## O que cada passo faz

1. **`create_preset`** — chama LLM 1x para analisar template + gold docs e gerar `pattern.md`, `schema.json`, `render_ops.yaml`, `validation.yaml`.
2. **`load_preset`** — carrega o bundle pronto pra uso (cacheia).
3. **`map_content`** — chama LLM com prompt few-shot pra extrair JSON estruturado a partir do source.
4. **`render`** — aplica operações YAML sobre o template + JSON e produz `.docx` final determinístico.

## Validar saída

```python
from engine import validate, calculate_confidence, confidence_label

result = validate(doc.text, data, preset.validation)
score = calculate_confidence(result)
label = confidence_label(score)
print(f"{score:.2f} → {label.value}")
```
