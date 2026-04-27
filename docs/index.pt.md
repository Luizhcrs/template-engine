---
title: Início
---

<div class="te-hero" markdown>
<div class="badges" markdown>
[![Release](https://img.shields.io/github/v/release/Luizhcrs/template-engine?display_name=tag&sort=semver&color=ff7a2a&label=release)](https://github.com/Luizhcrs/template-engine/releases) <span>Apache 2.0</span> <span>Python 3.11+</span>
</div>

# template-engine

<p class="lead" markdown>
Engine de normalização documental audit-grade. Regex-first, LLM-as-judge, zero LibreOffice. Construído pra ambientes regulados onde conteúdo de doc não pode vazar.
</p>

[Quickstart](quickstart.md){ .md-button .md-button--primary }
[GitHub](https://github.com/Luizhcrs/template-engine){ .md-button }
</div>

## Por que existe

Três problemas que soluções off-the-shelf não resolvem juntos:

- **Custo** — pagar LLM por doc quando 95% dos campos são extraíveis mecanicamente.
- **Compliance** — regulador quer auditabilidade + garantia que dado LGPD/HIPAA não saiu pra API externa.
- **Verificação** — "o candidato bateu com o padrão?" — texto sozinho não basta; estrutura, layout, formatos obrigatórios também.

## Como resolve

- **Hybrid mapper** — tier regex resolve o que dá; só missing vai pra LLM em uma chamada batched. Doc resolvido por regex = zero LLM tokens.
- **`local_only=True`** raise antes de qualquer chamada remota. PII masking + audit log append-only + regex path replayable bit-a-bit.
- **`check_conformity`** — veredicto multi-dim em texto + estrutural + visual + design + técnico. Cada dimensão score independente. Um único critical (CPF inválido, placeholder órfão, campo perdido) reprova independente do score médio.

## Pipeline

```
extract → schema_inference → pattern_inference → hybrid_mapper → render → semantic_diff
                                                                                  ↓
                                                                       ConformityReport
```

<div class="te-feature-grid" markdown>

<div class="te-feature" markdown>
### Regex-first
`pattern_inference` aprende regex de 3 gold docs + exemplos de campos. 10 shapes pré-definidas + `grex` opcional. Doc resolvido por regex custa zero LLM tokens.
</div>

<div class="te-feature" markdown>
### LLM como juiz, não autor
`semantic_diff` e dimensões `text` / `design` perguntam ao LLM "alguma coisa sumiu?" e "isso bate com o padrão?". O LLM não escreve conteúdo — ele audita.
</div>

<div class="te-feature" markdown>
### Modo local-only
`local_only=True` em `normalize_batch` e `check_conformity` raise se qualquer LLM for passado. Garantia dura pra deployments LGPD/HIPAA-grade.
</div>

<div class="te-feature" markdown>
### Multi-provider com fallback
6 providers — Gemini, OpenAI, Anthropic, Groq, Ollama, OpenRouter. `LLMRouter` encadeia com fallback automático em rate-limit / timeout.
</div>

<div class="te-feature" markdown>
### Stateless
Path/bytes in, paths/bytes/dataclasses out. Sem framework web, ORM, app layer. Plug em qualquer caller.
</div>

<div class="te-feature" markdown>
### Audit trail
`engine.security.AuditLog` escreve JSON Lines append-only. Registra sha256 hashes — nunca conteúdo bruto.
</div>

<div class="te-feature" markdown>
### Formatos bundled
5 formatos prontos: ABNT NBR 6022 / 14724 / 6023, NR-12 (laudo), contrato simples. `load_format(nome)` traz schemas + golds + conformity weights tunados.
</div>

</div>

## Custo por tier (Gemini Flash)

| Path | LLM calls | $/doc |
|------|-----------|-------|
| Regex resolve tudo | 0 | **$0.0000** |
| Alguns campos vão pra LLM fallback | 1 | ~$0.0006 |
| Com `semantic_diff` ligado | 2 | ~$0.0012 |
| Com `check_conformity(text + design)` | 4 | ~$0.0024 |

## Casos de uso

- Industrial: padronizar laudos de manutenção pro template corporativo (NR-12, NR-13).
- Jurídico: normalização de cláusulas de contrato com audit trail.
- Governo / regulado: processamento de formulários com `local_only=True` + PII masking.
- Migração: trazer documentos legados pro padrão corporativo novo.
- QA: verificar se terceiro entregou docs que batem com a spec (`check_conformity`).

## Instalação rápida

```bash
pip install "template-engine[gemini]"
```

[Continue com Quickstart →](quickstart.md){ .md-button .md-button--primary }

## Licença

[Apache 2.0](https://github.com/Luizhcrs/template-engine/blob/main/LICENSE) · Copyright 2026 luizhcrs
