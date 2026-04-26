# template-engine

Engine de normalização documental: aprende um padrão a partir de documentos-exemplo e converte qualquer documento-fonte pro mesmo padrão automaticamente via LLM.

[![CI](https://github.com/Luizhcrs/template-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/Luizhcrs/template-engine/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Release](https://img.shields.io/github/v/release/Luizhcrs/template-engine?display_name=tag&sort=semver)](https://github.com/Luizhcrs/template-engine/releases)

> **Docs**: <https://luizhcrs.github.io/template-engine/pt/>
> **README**: Português (este arquivo) · [English](README.md)

## O que faz

Pipeline em 5 etapas:

```
extractor → preset_creator → llm_mapper → validator → renderer
```

- **`extractor`** — `.docx`/`.pdf` → texto + tabelas + cabeçalhos
- **`preset_creator`** — template + 1-5 docs de referência → `pattern.md` + `schema.json` + `render_ops.yaml`
- **`llm_mapper`** — prompt + few-shot + JSON Schema → JSON estruturado
- **`validator`** — preservação de tokens críticos + cobertura + score 0-1
- **`renderer`** — template + JSON + render_ops → `.docx` final determinístico

## Princípio

**Renderer determinístico, conteúdo via LLM.** Regras de formatação vivem em YAML; conteúdo é extraído pelo modelo. Trocar de LLM (Gemini → GPT → Claude) não muda o resultado visual.

## Instalação

Core (sem provider):

```bash
pip install template-engine
```

Escolha o(s) provider(s):

```bash
pip install "template-engine[gemini]"        # Google Gemini (free tier)
pip install "template-engine[openai]"        # OpenAI
pip install "template-engine[anthropic]"     # Anthropic Claude
pip install "template-engine[groq]"          # Groq (inferência rápida)
pip install "template-engine[ollama]"        # LLMs locais via Ollama
pip install "template-engine[openrouter]"    # OpenRouter (400+ modelos)
pip install "template-engine[all]"           # todos providers
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
from engine import create_preset, load_preset, extract, map_content, render
from engine.llm.gemini_free import GeminiFreeProvider

async def main():
    provider = GeminiFreeProvider(api_key="AIza...")

    # 1. Aprende padrão a partir de template + docs de referência
    preset_dir = await create_preset(
        llm=provider,
        template_path=Path("template.docx"),
        gold_paths=[Path("gold_01.docx"), Path("gold_02.docx")],
        dest_dir=Path("./presets/my-template"),
    )

    # 2. Carrega
    preset = load_preset(preset_dir)

    # 3. Converte um documento-fonte
    doc = extract(Path("source.docx"))
    data = await map_content(preset, doc.text, provider)
    render(preset, data, output_path=Path("out.docx"))

asyncio.run(main())
```

## Multi-provider com fallback

Encapsule providers no `LLMRouter` pra failover automático em rate-limit / timeout:

```python
from engine.llm import LLMRouter
from engine.llm.groq_provider import GroqProvider
from engine.llm.gemini_free import GeminiFreeProvider
from engine.llm.openai_provider import OpenAIProvider

router = LLMRouter([
    GroqProvider(api_key=g_key),         # primário: rápido + barato
    GeminiFreeProvider(api_key=ge_key),  # fallback: free tier
    OpenAIProvider(api_key=o_key),       # último recurso
])

# Mesma interface dos providers individuais
data = await map_content(preset, source_text, router)
```

`LLMError` genérico propaga imediatamente; só `LLMRateLimit` / `LLMTimeout` disparam fallback.

## Arquitetura

**Stateless.** Recebe paths/bytes, retorna paths/bytes/dicts. Sem dependência de framework web, ORM ou camada de aplicação.

**Renderização determinística.** LLM nunca decide forma visual. Tudo que afeta visual vive em `render_ops.yaml`. Trocar de modelo não muda saída visual.

**Type-safe.** `py.typed` marker, type hints completos, mypy-friendly.

**Adicione seu provider** implementando o Protocol `LLMProvider`:

```python
from engine.llm.base import LLMError, LLMRateLimit, LLMTimeout

class MyProvider:
    name = "my-provider"
    model = "default"

    def __init__(self, api_key: str, model: str | None = None) -> None:
        if not api_key:
            raise RuntimeError("api_key obrigatório")
        # ... inicializa SDK

    async def generate_structured(self, prompt: str, json_schema: dict) -> dict:
        # ... chama API, parseia JSON
        # levanta LLMRateLimit / LLMTimeout / LLMError quando apropriado
        ...
```

Veja [docs/providers/](https://luizhcrs.github.io/template-engine/pt/providers/) pra checklist completa.

## Desenvolvimento

```bash
pip install -e ".[dev]"
ruff check . && ruff format --check . && mypy src/engine && pytest
```

Hoje: 49 testes passando.

## Casos de uso

- Padronização de contratos jurídicos
- Normalização de laudos técnicos
- Migração de documentos legados pra template novo
- Compliance: forçar tipografia + preservação de tokens críticos
- Extração estruturada de PDFs → `.docx` polido

## Roadmap

Status atual e próximas frentes (eval suite, CLI, OCR, output PDF) em [ROADMAP.md](ROADMAP.md).

## Contribuindo

Issues e PRs bem-vindos. Veja [CONTRIBUTING.md](CONTRIBUTING.md) pra setup, code style e checklist de provider.

Pra issues de segurança veja [SECURITY.md](SECURITY.md).

## Licença

[Apache 2.0](LICENSE) · Copyright 2026 luizhcrs
