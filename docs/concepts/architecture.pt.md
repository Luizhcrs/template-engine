# Arquitetura

## Mapa de módulos

```
engine/
├── extractor.py             docx/pdf -> ExtractedDoc (text, paragraphs, tables, header_fields)
├── schema_inference.py      detect_placeholders + enrich_with_llm + FieldSchema
├── pattern_inference.py     infer_field_patterns + grex Tier 2 + apply_inferred
├── hybrid_mapper.py         map_hybrid (regex first, LLM batched fallback)
├── batch.py                 normalize_batch orchestrator + token-substitution renderer
├── semantic_diff.py         diff_documents / diff_texts (LLM como juiz)
├── confidence.py            ConfidenceLabel + calculate_confidence (Protocol structural)
├── ascii_layout.py          features de layout via luminance (sem LLM)
├── cli.py                   typer CLI: info, version, extract, normalize, conformity
├── llm/
│   ├── base.py              LLMProvider Protocol + LLMError, LLMRateLimit, LLMTimeout
│   ├── router.py            LLMRouter + AllProvidersFailed
│   ├── gemini_free.py       GeminiFreeProvider
│   ├── openai_provider.py   OpenAIProvider (strict mode opt-in)
│   ├── anthropic_provider.py AnthropicProvider (tool-use coercion)
│   ├── groq_provider.py     GroqProvider (JSON mode)
│   ├── ollama_provider.py   OllamaProvider (local httpx)
│   ├── openrouter_provider.py OpenRouterProvider (subclass de OpenAI w/ base_url)
│   ├── _schema.py           normalize_for_strict (OpenAI strict mode)
│   └── _utils.py            retry_after_from_error
├── conformity/
│   ├── report.py            ConformityReport, DimensionResult, Failure
│   ├── text.py              wrap em semantic_diff
│   ├── structural.py        parser python-docx + StructuralFingerprint
│   ├── visual.py            render PIL + ascii_layout fingerprint compare
│   ├── design.py            ConformityVisualProvider Protocol + check_design
│   ├── technical.py         format validators (cpf/cep/iso/...) + orphan check
│   └── aggregator.py        check_conformity top-level + score ponderado
├── security/
│   ├── pii.py               mask_pii / unmask + PIIMask
│   ├── injection.py         detect_prompt_injection + 7 regras regex
│   ├── audit.py             AuditLog (JSONL append-only) + sha256_hex
│   └── local_only.py        RefusedRemoteCallError
└── section_mapper/
    ├── parser.py            parse_docx (template) / parse_docx_source (numbering-aware)
    ├── numbering.py         NumberingResolver (lê word/numbering.xml, renderiza markers)
    ├── similarity.py        match_string / match_embeddings / match_llm + sinônimos
    ├── renderer.py          render_section_content (decoração por tipo + prune vazios)
    ├── table_filler.py      fill_tables (header-set match + subheaders)
    ├── auto_tables.py       detect_default_specs_with_source (Histórico + Resp da fonte)
    ├── header_filler.py     extract_source_metadata + fill_template_header
    ├── template_profiler.py profile_template (Wave M: cells + placeholders + headings)
    ├── source_profiler.py   profile_source (Wave M: input polimórfico, body fallback)
    ├── auto_mapper.py       build_mapping_plan (Wave M: LLM call + retry + checklist)
    ├── auto_renderer.py     apply_mapping_plan (Wave M: header/body subs + cell_fills)
    ├── template_renderer.py render_pages (Wave M: docx → PDF → PNG pra vision)
    ├── plan_cache.py        load_plan / save_plan (Wave M: cache sha256)
    └── orchestrator.py      map_sections / map_sections_async + SectionMappingReport
```

## Grafo de dependências

```
extractor ─────┐
               ├─→ schema_inference ─┐
               ├─→ semantic_diff ────┤
pattern_inference ─→ hybrid_mapper ─┤
                                    ├─→ batch (orquestrador)
                                    │
schema_inference ───────────────────┘

conformity.{text, structural, visual, design, technical} ─→ conformity.aggregator
                                                                  ↓
                                                          ConformityReport

security.{pii, injection, audit, local_only} ─→ usado onde houver chamada LLM
```

DAG, sem ciclos. Cada módulo tem 1 responsabilidade.

## Superfície da API pública

`engine.__init__` exporta ~71 símbolos. Categorizados:

- **Dados core:** `ExtractedDoc`, `FieldSchema`, `InferredPattern`, `MappingResult`, `BatchReport`, `ConformityReport`, `Failure`, `Discrepancy`.
- **Operações:** `extract`, `infer_field_patterns`, `apply_inferred`, `map_hybrid`, `normalize_batch`, `check_conformity`, `diff_documents`.
- **Validators:** `validate_cpf`, `validate_cep`, `validate_iso_date`, `validate_br_date`, `validate_email`, `validate_phone_br`, `validate_uf`.
- **Segurança:** `mask_pii`, `unmask`, `detect_prompt_injection`, `AuditLog`, `RefusedRemoteCallError`, `sha256_hex`.
- **Layout:** `image_to_ascii`, `detect_layout_features`, `summarize_layout`.
- **Section mapper:** `map_sections`, `map_sections_async`, `SectionMappingReport`, `TableSpec`, `HeadingMatch`, `NumberingResolver`, `parse_docx_source`, `extract_source_metadata`, `fill_template_header`. Veja a página dedicada [Section mapper](section_mapper.pt.md).

Todos os tipos públicos são frozen dataclasses ou Protocols — sem herança, sem mutação.

## Decisões de design

### Stateless

Path/bytes in, paths/bytes/dataclasses out. A lib não dona um banco, cache, arquivo de config ou processo. App caller dona isso. Permite embed em FastAPI, CLI, batch job, Lambda — mesmo código, shells diferentes.

### Frozen dataclasses na API pública

`MappingResult`, `Failure`, `ConformityReport`, `BatchItemResult`, `FieldSchema`, `InferredPattern`. Equality + hashing de graça, zero mutação acidental, fácil serializar (`to_dict` retorna dict puro).

### Provider LLM via Protocol

`LLMProvider` é `typing.Protocol`, não ABC. Adicionar provider novo = implementar 1 método (`generate_structured`); sem subclasse, sem registry magic. Providers existentes não compartilham base class — compartilham shape. Desacopla a superfície da lib de qualquer SDK.

### Tier regex rejeita over-generalization

`pattern_inference._has_structural_anchors` exige punctuation literal ou digit-class antes de aceitar pattern com `\w` do grex. Sem isso, grex colapsaria `["Joao Silva", "Maria Souza"]` em `\w+ \w+` — matchearia frases arbitrárias de 2 palavras. A lib cai pra freetext ao invés.

### `is_conformant` exige zero critical failures

Score alto não cancela 1 critical. Bate com mental model do regulador: "qualquer deal-breaker = fail". Implementado no aggregator: `is_conformant = (score >= threshold) AND not has_critical`.

### Audit grava hashes, não conteúdo bruto

`AuditLog` registra sha256 de inputs/outputs. Auditor prova que doc foi processado sem que o log vire data store secundário. Alinha com princípio de minimização de dados da LGPD.

### Renderer por substituição direta de token

`batch._apply_mapping_to_template` não depende de preset bundle. Anda em parágrafos e células de tabela do `python-docx`, substitui tokens direto. Sem camada YAML render-ops, sem LibreOffice. Output preserva formatação do template intacta.

## Modos de operação

Três modos de deploy, ordenados por rigor:

1. **Local-only** — `llm=None, local_only=True`. Engine nunca contata rede. Só roda tier regex; campos missing ficam missing. Obrigatório pra HIPAA, recomendado pra dados LGPD altamente sensíveis.
2. **PII-masked** — envolve `mask_pii` / `unmask` em qualquer chamada LLM. Identificadores pessoais nunca chegam ao provider.
3. **Audit-trace** — `AuditLog(path=...)` pra toda operação que toca LLM. Hashes de inputs/outputs preservados.

Veja [`SECURITY-MODEL.md`](https://github.com/Luizhcrs/template-engine/blob/main/SECURITY-MODEL.md) pra guidance completa por framework regulatório.

## O que não faz explicitamente

- **Sem banco/cache embutido.** Caller dona persistência.
- **Sem detecção de PII além dos patterns.** Sem heurística de nome/endereço; integre Presidio antes de `mask_pii` se precisa cobertura mais ampla.
- **Sem encryption at rest.** Caller dona disk encryption / KMS.
- **Sem isolamento multi-tenant.** A lib é stateless; caller dona separação.
- **Sem telemetria / phone-home.** A lib não faz nenhuma chamada de rede além do provider LLM passado explícito.

## Cobertura de testes

189 tests cobrindo:

- providers (Gemini / OpenAI / Anthropic / Groq / Ollama / OpenRouter / Router)
- pattern_inference (Tier 1 + Tier 2 grex + label aggregation)
- schema_inference (5 sintaxes de placeholder + LLM enrichment)
- hybrid_mapper (tier regex + fallback LLM batched)
- batch orchestrator (tier classification + report serialization)
- conformity (5 dimensões + aggregator + threshold)
- security (PII mask, prompt injection, audit log, local_only)

Suite de validação: `ruff check . && ruff format --check . && mypy src/engine && pytest`. Verde em Python 3.11 / 3.12 / 3.13 no CI.
