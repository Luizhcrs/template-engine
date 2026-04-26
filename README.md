# template-engine

Document normalization engine: learn a pattern from example documents and convert any source document to that pattern automatically via LLM.

[![CI](https://github.com/Luizhcrs/template-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/Luizhcrs/template-engine/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Release](https://img.shields.io/github/v/release/Luizhcrs/template-engine?display_name=tag&sort=semver)](https://github.com/Luizhcrs/template-engine/releases)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Typed](https://img.shields.io/badge/typed-mypy-2A6DB2.svg)](http://mypy-lang.org/)

## What it does

Pipeline em 5 etapas:

```
extractor → preset_creator → llm_mapper → validator → renderer
```

- **`extractor`** — `.docx`/`.pdf` → texto + tabelas + cabeçalhos
- **`preset_creator`** — template + 1-5 docs de referência → `pattern.md` + `schema.json` + `render_ops.yaml`
- **`llm_mapper`** — prompt + few-shot + JSON Schema → JSON estruturado
- **`validator`** — tokens críticos + cobertura + score 0-1
- **`renderer`** — template + JSON + render_ops → `.docx` final determinístico

## Princípio

**Renderer determinístico, conteúdo via LLM.** Regras de formatação vivem em YAML; conteúdo é extraído pelo modelo. Trocar de LLM (Gemini → GPT → Claude) não muda o resultado visual.

## Install

Core (provider-agnostic):

```bash
pip install template-engine
```

Com provider Gemini incluído:

```bash
pip install "template-engine[gemini]"
```

Ou direto do source:

```bash
git clone https://github.com/Luizhcrs/template-engine
cd template-engine
pip install -e ".[dev]"
```

## Quickstart

```python
import asyncio
from pathlib import Path
from engine import (
    create_preset, load_preset, extract, map_content, render,
)
from engine.llm.gemini_free import GeminiFreeProvider

async def main():
    provider = GeminiFreeProvider(api_key="AIza...")

    # 1. Aprende padrão a partir de docs de referência
    preset_dir = await create_preset(
        llm=provider,
        template_path=Path("template.docx"),
        gold_paths=[Path("gold_01.docx"), Path("gold_02.docx")],
        dest_dir=Path("./presets/my-template"),
        # slug, name, owner são opcionais; defaults derivados de dest_dir.name
    )

    # 2. Carrega preset
    preset = load_preset(preset_dir)

    # 3. Converte um documento-fonte
    doc = extract(Path("source.docx"))
    data = await map_content(preset, doc.text, provider)
    render(preset, data, output_path=Path("out.docx"))

asyncio.run(main())
```

## Architecture

**Stateless.** Recebe paths/bytes, retorna paths/bytes/dicts. Sem dependência de FastAPI, SQLAlchemy ou qualquer framework de SaaS.

**Determinístico no rendering.** LLM nunca decide forma visual. Tudo que afeta visual vive em `render_ops.yaml`. Trocar de modelo não muda saída visual.

**Multi-provider.** Suporta Gemini, OpenAI, Anthropic, Groq, Ollama (local) e OpenRouter (400+ modelos) — todos via `engine.llm.base.LLMProvider` Protocol. Use `LLMRouter` pra fallback automático em rate-limit/timeout. Adicione um provider próprio assim:

```python
from engine.llm.base import LLMProvider

class MyProvider:
    name = "my-provider"

    async def generate_structured(self, prompt: str, json_schema: dict) -> dict:
        # ... sua implementação
        return parsed_json
```

## Development

```bash
pip install -e ".[dev]"
pytest                    # 36 tests
pytest --cov              # com coverage
```

## Use cases

- Padronização de contratos jurídicos
- Normalização de laudos técnicos
- Conversão de relatórios entre formatos corporativos
- Migração de documentos legados pra template novo
- Extração estruturada de PDFs em documentos `.docx`

## Roadmap

- [ ] OpenAI provider
- [ ] Anthropic provider
- [ ] Ollama provider (modelos locais)
- [ ] PDF output além de `.docx`
- [ ] Eval suite com benchmark de prompt + LLM rotation
- [ ] CI com pytest

## License

[Apache 2.0](LICENSE) · Copyright 2026 luizhcrs

## Contributing

Issues e PRs bem-vindos. Pra mudanças grandes, abra uma issue antes pra discutir.
