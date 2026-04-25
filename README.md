# template-engine

Document normalization engine: learn a pattern from example documents and convert any source document to that pattern automatically via LLM.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

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

```bash
pip install template-engine
```

Ou direto do source:

```bash
git clone https://github.com/Luizhcrs/template-engine
cd template-engine
pip install -e ".[dev]"
```

## Quickstart

```python
from engine.extractor import extract
from engine.preset_creator import create_preset
from engine.llm.gemini_free import GeminiFreeProvider
from engine.llm_mapper import map_content
from engine.renderer import render
from engine.preset_loader import load_preset

provider = GeminiFreeProvider(api_key="AIza...")

# Aprende padrão a partir de docs de referência
preset_dir = create_preset(
    template_path="template.docx",
    gold_paths=["gold_01.docx", "gold_02.docx"],
    out_dir="./presets/my-template",
    llm=provider,
)

# Carrega preset
preset = load_preset(preset_dir)

# Converte um documento-fonte
doc = extract("source.docx")
data = await map_content(doc, preset, provider)
render(preset, data, output_path="out.docx")
```

## Architecture

**Stateless.** Recebe paths/bytes, retorna paths/bytes/dicts. Sem dependência de FastAPI, SQLAlchemy ou qualquer framework de SaaS.

**Determinístico no rendering.** LLM nunca decide forma visual. Tudo que afeta visual vive em `render_ops.yaml`. Trocar de modelo não muda saída visual.

**Multi-provider.** Atualmente suporta Gemini. Adicione providers implementando `engine.llm.base.LLMProvider`:

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
pytest                    # 29 tests
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
