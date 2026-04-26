---
title: Início
---

<div class="te-hero" markdown>
<div class="badges" markdown>
<span>v0.2.0</span> <span>Apache 2.0</span> <span>Python 3.11+</span>
</div>

# template-engine

<p class="lead" markdown>
Engine de normalização documental. Aprende o padrão de documentos-exemplo e converte qualquer documento-fonte pro padrão automaticamente via LLM.
</p>

[Comece aqui](quickstart.md){ .md-button .md-button--primary }
[GitHub](https://github.com/Luizhcrs/template-engine){ .md-button }
</div>

## Por quê

Padronizar documentos é trabalho repetitivo, sujeito a erro, e geralmente feito por copy-paste entre `.docx`. **template-engine** aprende o padrão a partir de 1-5 documentos-exemplo (gold docs) e converte qualquer documento-fonte pro mesmo padrão automaticamente.

## Princípio

**Renderer determinístico, conteúdo via LLM.** Regras de formatação vivem em YAML; conteúdo é extraído pelo modelo. Trocar de LLM (Gemini → GPT → Claude) não muda o resultado visual.

## Pipeline

```
extractor → preset_creator → llm_mapper → validator → renderer
```

<div class="te-feature-grid" markdown>

<div class="te-feature" markdown>
### Multi-provider
6 provedores LLM prontos: Gemini, OpenAI, Anthropic, Groq, Ollama, OpenRouter. Adicione o seu via Protocol `LLMProvider`.
</div>

<div class="te-feature" markdown>
### Engine stateless
Recebe paths/bytes, retorna paths/bytes/dicts. Sem acoplamento com FastAPI/SQLAlchemy/auth. Plugue em qualquer app.
</div>

<div class="te-feature" markdown>
### Tokens críticos preservados
Códigos, siglas e valores técnicos preservados com precisão entre conversões. Validador detecta drift.
</div>

<div class="te-feature" markdown>
### Fallback inteligente
`LLMRouter` encadeia provedores com fallback automático em rate-limit / timeout. Orquestração consciente de custo.
</div>

<div class="te-feature" markdown>
### Type-safe
Marker `py.typed`, type hints em toda API pública. Mypy-friendly em apps downstream.
</div>

<div class="te-feature" markdown>
### Open source
Apache 2.0. Issues, PRs e contribuições de novos providers bem-vindos.
</div>

</div>

## Casos de uso

- Padronização de contratos jurídicos
- Normalização de laudos técnicos
- Migração de documentos legados para template novo
- Compliance: forçar tipografia + preservação de tokens críticos
- Extração estruturada de PDFs → `.docx` polido

## Instalação rápida

```bash
pip install "template-engine[gemini]"
```

[Continuar com Quickstart →](quickstart.md){ .md-button .md-button--primary }

## Licença

[Apache 2.0](https://github.com/Luizhcrs/template-engine/blob/main/LICENSE) · Copyright 2026 luizhcrs
