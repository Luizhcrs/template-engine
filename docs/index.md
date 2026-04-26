---
title: Home
---

<div class="te-hero" markdown>
<div class="badges" markdown>
<span>v0.2.0</span> <span>Apache 2.0</span> <span>Python 3.11+</span>
</div>

# template-engine

<p class="lead" markdown>
Document normalization engine. Learn a pattern from example documents and convert any source document to that pattern automatically via LLM.
</p>

[Quickstart](quickstart.md){ .md-button .md-button--primary }
[GitHub](https://github.com/Luizhcrs/template-engine){ .md-button }
</div>

## Why

Padronizar documentos é trabalho repetitivo, sujeito a erro, e geralmente feito por copy-paste entre `.docx`. **template-engine** aprende o padrão a partir de 1-5 documentos-exemplo (gold docs) e converte qualquer documento-fonte pro mesmo padrão automaticamente.

## Principle

**Deterministic renderer, content via LLM.** Formatting rules live in YAML; content is extracted by the model. Switching LLMs (Gemini → GPT → Claude) does not change visual output.

## Pipeline

```
extractor → preset_creator → llm_mapper → validator → renderer
```

<div class="te-feature-grid" markdown>

<div class="te-feature" markdown>
### Multi-provider
6 LLM providers ready: Gemini, OpenAI, Anthropic, Groq, Ollama, OpenRouter. Add yours via the `LLMProvider` Protocol.
</div>

<div class="te-feature" markdown>
### Stateless engine
Receives paths/bytes, returns paths/bytes/dicts. No FastAPI/SQLAlchemy/auth coupling. Plug into any app.
</div>

<div class="te-feature" markdown>
### Critical token preservation
Codes, acronyms, technical values preserved exactly across conversions. Validation catches drift.

</div>

<div class="te-feature" markdown>
### Smart fallback
`LLMRouter` chains providers with automatic fallback on rate-limit / timeout. Cost-aware orchestration.
</div>

<div class="te-feature" markdown>
### Type-safe
`py.typed` marker, type hints across the API. Mypy-friendly for downstream apps.
</div>

<div class="te-feature" markdown>
### Open source
Apache 2.0. Issues, PRs, and provider contributions welcome.
</div>

</div>

## Use cases

- Legal contract standardization
- Technical report normalization
- Migration of legacy documents to modern templates
- Compliance: enforce typography + critical token preservation
- Structured PDF extraction → polished `.docx`

## Quick install

```bash
pip install "template-engine[gemini]"
```

[Continue with Quickstart →](quickstart.md){ .md-button .md-button--primary }

## License

[Apache 2.0](https://github.com/Luizhcrs/template-engine/blob/main/LICENSE) · Copyright 2026 luizhcrs
