# template-engine

Document normalization engine: learn a pattern from example documents and convert any source document to that pattern automatically via LLM.

[![CI](https://github.com/Luizhcrs/template-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/Luizhcrs/template-engine/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Release](https://img.shields.io/github/v/release/Luizhcrs/template-engine?display_name=tag&sort=semver)](https://github.com/Luizhcrs/template-engine/releases)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Typed](https://img.shields.io/badge/typed-mypy-2A6DB2.svg)](http://mypy-lang.org/)

> **Docs**: <https://luizhcrs.github.io/template-engine/>
> **README**: English (this file) · [Português](README.pt.md)

## What it does

5-stage pipeline:

```
extractor → preset_creator → llm_mapper → validator → renderer
```

- **`extractor`** — `.docx`/`.pdf` → text + tables + headers
- **`preset_creator`** — template + 1-5 reference docs → `pattern.md` + `schema.json` + `render_ops.yaml`
- **`llm_mapper`** — prompt + few-shot + JSON Schema → structured JSON
- **`validator`** — critical token preservation + section coverage + 0-1 score
- **`renderer`** — template + JSON + render_ops → final deterministic `.docx`

## Principle

**Deterministic renderer, content via LLM.** Formatting rules live in YAML; content is extracted by the model. Switching LLMs (Gemini → GPT → Claude) does not change visual output.

## Install

Core (provider-agnostic):

```bash
pip install template-engine
```

Pick the provider(s) you need:

```bash
pip install "template-engine[gemini]"        # Google Gemini (free tier)
pip install "template-engine[openai]"        # OpenAI
pip install "template-engine[anthropic]"     # Anthropic Claude
pip install "template-engine[groq]"          # Groq (fast inference)
pip install "template-engine[ollama]"        # local LLMs via Ollama
pip install "template-engine[openrouter]"    # OpenRouter (400+ models)
pip install "template-engine[all]"           # all providers
```

Or from source:

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

    # 1. Learn pattern from template + reference docs
    preset_dir = await create_preset(
        llm=provider,
        template_path=Path("template.docx"),
        gold_paths=[Path("gold_01.docx"), Path("gold_02.docx")],
        dest_dir=Path("./presets/my-template"),
    )

    # 2. Load
    preset = load_preset(preset_dir)

    # 3. Convert a source document
    doc = extract(Path("source.docx"))
    data = await map_content(preset, doc.text, provider)
    render(preset, data, output_path=Path("out.docx"))

asyncio.run(main())
```

## Multi-provider with fallback

Wrap providers in `LLMRouter` for automatic failover on rate-limit / timeout:

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

# Same interface as individual providers
data = await map_content(preset, source_text, router)
```

Generic `LLMError` propagates immediately; only `LLMRateLimit` / `LLMTimeout` trigger fallback.

## Architecture

**Stateless.** Receives paths/bytes, returns paths/bytes/dicts. No dependency on web framework, ORM, or application layer.

**Deterministic rendering.** LLM never decides visual format. Everything visual lives in `render_ops.yaml`. Switching models does not change visual output.

**Type-safe.** `py.typed` marker, full type hints, mypy-friendly.

**Add your own provider** by implementing the `LLMProvider` Protocol:

```python
from engine.llm.base import LLMError, LLMRateLimit, LLMTimeout

class MyProvider:
    name = "my-provider"
    model = "default"

    def __init__(self, api_key: str, model: str | None = None) -> None:
        if not api_key:
            raise RuntimeError("api_key required")
        # ... initialize SDK

    async def generate_structured(self, prompt: str, json_schema: dict) -> dict:
        # ... call API, parse JSON
        # raise LLMRateLimit / LLMTimeout / LLMError as needed
        ...
```

See [docs/providers/](https://luizhcrs.github.io/template-engine/providers/) for the full provider checklist.

## Development

```bash
pip install -e ".[dev]"
ruff check . && ruff format --check . && mypy src/engine && pytest
```

Today: 49 tests passing.

## Use cases

- Legal contract standardization
- Technical report normalization
- Migration of legacy documents to a new template
- Compliance: enforce typography + critical token preservation
- Structured PDF extraction → polished `.docx`

## Roadmap

Current status and upcoming work (eval suite, CLI, OCR, PDF output) in [ROADMAP.md](ROADMAP.md).

## Contributing

Issues and PRs welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, code style, and the provider checklist.

For security issues see [SECURITY.md](SECURITY.md).

## License

[Apache 2.0](LICENSE) · Copyright 2026 luizhcrs
