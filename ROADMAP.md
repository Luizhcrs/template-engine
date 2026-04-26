# template-engine — Roadmap

Goal: tornar a lib **state-of-the-art** em normalização documental via LLM. Deliberada, sem buzzword soup.

Ordem por impacto + foundation-first. Cada bloco entrega valor sozinho.

---

## Status atual (2026-04-26)

| Versão | Estado | Tag | Highlight |
|---|---|---|---|
| v0.1.0 | ✅ entregue | `v0.1.0` (2026-04-25) | Pipeline básico, Gemini provider, 29 tests |
| v0.1.1 | ✅ entregue | `v0.1.1` (2026-04-25) | Security hardening + breaking API cleanups |
| v0.2.0 | ✅ entregue | `v0.2.0` (2026-04-25) | Multi-provider (5 novos) + LLMRouter |
| v0.2.1 | ✅ entregue | `v0.2.1` (2026-04-26) | OpenAI strict fix + bilingual README, 49 tests |
| Wave A | ✅ entregue | `3c42feb` (2026-04-26) | regex inference automatica (10 shapes pre-def + label aggregation) |
| Wave A v2 | ✅ entregue | `594ee1f` (2026-04-26) | grex Tier 2 — generaliza regex via digit/word conversion |
| Wave D | ✅ entregue | `126b0c0` (2026-04-26) | batch orchestrator (1 template + N docs → N normalized + report) |
| Wave E | ✅ entregue | `(pending push)` (2026-04-26) | drop legacy preset/renderer/validator/visual_validator (~26% LOC ↓) |
| Wave F | 🟡 planejada | — | conformity validator multi-dim (texto + estrutural + visual + design + técnico) |
| v0.3.0 | ✅ entregue | `(pending tag)` (2026-04-26) | Wave A + Wave D + Wave E shipped, single Wave D path |
| v0.4+  | 📋 planejado | — | OCR + extractors + renderer expandido |

**Onde estamos hoje (2026-04-26):**

- Lib estável com 6 providers + LLMRouter
- Wave A entrega regex inference automatica → reduz dependencia de LLM
- Wave A v2 adiciona grex (optional) → generaliza patterns aprendidos
- Wave D entrega orquestrador batch — caso de uso real "1 template + N docs → N normalizados" via CLI `template-engine normalize`
- 172 tests passing, CI verde matrix py3.11/3.12/3.13
- Próximo: Wave E (consolidação) → Wave F (conformidade multi-dim como juiz LLM)

**Tese central comprovada:** LLM como rede de segurança, não motor. 49/49 campos extraidos via regex puro em 6 designs diversos (laudo/contrato/branded/creative/minimalist/form). LLM só atua quando regex falha (Wave D hybrid_mapper) ou pra auditar conformidade final (semantic_diff).

---

## v0.1.0 — entregue 2026-04-25 ✅

Pipeline básico:
- ✅ Extractor `.docx` + `.pdf`
- ✅ Preset creator (LLM gera pattern + schema + render_ops)
- ✅ LLM mapper (prompt + few-shot + JSON Schema)
- ✅ Validator (tokens críticos + cobertura)
- ✅ Renderer (.docx output via render_ops)
- ✅ Provider Gemini

---

## v0.1.1 — entregue 2026-04-25 ✅

Security + breaking API cleanups:
- ✅ Path traversal hardening em `preset_loader`
- ✅ Prompt injection delimiters em `llm_mapper` + `preset_creator`
- ✅ `create_preset` keyword-only com defaults
- ✅ `ConfidenceLabel` enum (HIGH/MEDIUM/LOW)
- ✅ structlog substituiu stdlib logging
- ✅ Gemini captura `ResourceExhausted`/`DeadlineExceeded` SDK-typed
- ✅ `engine.__init__` exporta API pública + `__all__`
- ✅ `py.typed` marker
- ✅ `gemini` virou optional dep `[gemini]`

---

## v0.2.0 — entregue 2026-04-25 ✅

Multi-provider LLM:
- ✅ **`OpenAIProvider`** — `response_format=json_schema` strict mode
- ✅ **`AnthropicProvider`** — tool use forçado pra coerce JSON
- ✅ **`GroqProvider`** — JSON mode (OpenAI-compatible)
- ✅ **`OllamaProvider`** — local via httpx
- ✅ **`OpenRouterProvider`** — subclass de OpenAI com base_url
- ✅ **`LLMRouter`** — fallback automático em rate-limit/timeout
- ✅ `_retry_after_from_error` extrai header dinâmico (era hardcoded 60s)
- ✅ Optional deps por provider: `[gemini|openai|anthropic|groq|ollama|openrouter|all]`
- ✅ 36 tests passing (29 anteriores + 7 novos pro router)

**Não entregue (movido pra v0.3+):**
- ❌ `LLMConfig` tipada (max_tokens, temperature, retry_attempts, timeout) — providers aceitam kwargs ad-hoc
- ❌ Streaming `generate_structured_stream` — não tinha caso de uso urgente
- ❌ Tool use uniformizado cross-provider — Anthropic usa, OpenAI usa schema, outros injetam — dívida técnica

---

## Wave A — regex inference (entregue 2026-04-26 ✅)

Substitui `_FIELD_PATTERNS` hardcoded por inferência mecânica.

- ✅ `engine.pattern_inference` — `infer_field_patterns(gold_docs, field_examples)` aprende regex de exemplos
- ✅ Tier 1: 10 shapes pre-definidas (iso_date, doc_code, cpf, cep, uf, fullname, version, br_date, decimal_br, integer, month_year_pt)
- ✅ Label aggregation via Counter — alterna múltiplos rótulos no mesmo campo
- ✅ Wave A v2: integração `grex` (optional dep `[inference]`) — Tier 2 generaliza patterns
- ✅ Heurística hybrid digits-only/words: aceita generalização só com structural anchors
- ✅ POCs 08-13 refatorados — 49/49 campos extraídos sem regex hardcoded em 6 designs

**Commits:** `cfc9b71` (v1) + `594ee1f` (v2). Tests: +24 (49 → 110 → 116).

---

## Wave D — batch orchestrator (entregue 2026-04-26 ✅)

End-to-end: 1 template + N source docs → N normalized + report.json.

- ✅ `engine.schema_inference` — detecta placeholders no template (5 sintaxes: mustache/bracket/chevron/named-blank/anonymous-blank), opcional LLM enrichment de field_type/format_hint/required
- ✅ `engine.hybrid_mapper` — regex first via pattern_inference, single batched LLM call só nos missing. Output `MappingResult{value, source: regex|llm|missing, confidence}`
- ✅ `engine.semantic_diff` — text-only LLM compare (zero LibreOffice). Discrepancies tipadas: `missing_in_output` / `value_mismatch` / `extra_in_output`. Severity: critical / warning / info
- ✅ `engine.batch.normalize_batch()` — async paralelo, max_concurrent configurável, direct token-substitution renderer (sem PresetBundle)
- ✅ `BatchReport.to_dict()` — JSON-serializable com per-doc mapping summary, discrepancies, tier
- ✅ Tier classification: `high` (regex resolveu tudo, sem critical diff) / `medium` (LLM filled OR warning) / `low` (missing required OR critical) / `error`
- ✅ CLI `template-engine normalize --template T --source-dir SD --output-dir OD --provider gemini --gold-doc G --field-examples FE.json --report R --skip-diff --max-concurrent N`

**Smoke test real:** 5 docs → 5/5 high tier, ZERO LLM calls quando regex resolve. Commit: `126b0c0`. Tests: +55 (116 → 172).

---

## Wave E — consolidação (planejada, 1 dia)

**Por quê:** lib hoje tem 2 caminhos paralelos (preset legacy vs Wave D schema). Confunde usuário e duplica manutenção.

### Drops

- [ ] `engine.preset_creator` — substituído por `schema_inference`
- [ ] `engine.preset_loader` (PresetBundle, list_*_presets) — substituído por direct schema usage
- [ ] `engine.preset_schemas` — sem consumidor após drop dos 2 acima
- [ ] `engine.renderer` + `engine.render_ops/` — substituído por `batch._apply_mapping_to_template`
- [ ] `engine.validator` (legacy tokens críticos) — substituído por `hybrid_mapper` confidence + `semantic_diff`
- [ ] `engine.visual_validator` (LibreOffice obrigatório) — substituído por Wave F design dimension
- [ ] CLI `convert` + `visual-validate` — apenas `normalize` permanece

### Refactor

- [ ] `examples/` (2648 LOC, 7 POCs) → repo separado `template-engine-examples`
- [ ] `__init__.py` exports limpos (drop símbolos legacy)
- [ ] CLI `info` ainda lista providers, mas remove menção a presets
- [ ] CHANGELOG: marcar removals como BREAKING (bump pra v0.3.0a2 → v0.3.0)

### Critério done

- ~5k LOC src (de ~9.9k atual)
- 1 caminho só: `template-engine normalize`
- Tests passando (≥150 — alguns dos 172 atuais saem com legacy modules)
- CHANGELOG documenta breaking changes
- Migration guide pra quem usava `convert` + presets

---

## Wave F — conformity validator multi-dim (planejada, 3-5 dias)

**Por quê:** o usuário pediu — LLM como juiz multi-dimensional ("este doc está sim no padrão"). Não só texto: visual + design + estrutura + técnico.

### API alvo

```python
from engine.conformity import check_conformity, ConformityReport

report = await check_conformity(
    template_path="padrao.docx",
    candidate_path="candidato.docx",
    *,
    llm=llm,                 # texto + design (multimodal)
    schemas=schemas,          # pra technical_dimension
    inferred_patterns=...,    # pra technical_dimension
    dimensions=["text", "structural", "visual", "design", "technical"],
)

report.is_conformant   # bool
report.score           # 0-1 weighted
report.failures        # list[Failure(dimension, field, expected, actual, severity)]
report.by_dimension    # dict[str, DimensionResult]
```

### 5 dimensões

| Dimensão | Implementação | LLM? |
|----------|---------------|------|
| **text** | wraps `engine.semantic_diff` existente | sim (juiz) |
| **structural** | NEW: parser python-docx — conta headings (níveis), tables (dimensões), sections, lists. Compara template vs candidate | não |
| **visual** | NEW: wrapper sobre `engine.ascii_layout` — render template+candidate como PNG via PIL, extrai LayoutFeatures, compara densidade/headings/tables/placeholders | não |
| **design** | NEW: multimodal LLM (Gemini File API) recebe os 2 docx direto, prompt comparar fonte/cor/spacing/alinhamento. SEM LibreOffice | sim (juiz) |
| **technical** | NEW aggregator: `hybrid_mapper` output + format validators (CPF dígito verificador, CEP dígitos, ISO date validade, email, etc) + zero-orphan check (`{{X}}` não substituídos) | não |

### Componentes novos

- [ ] `engine.conformity.text` — wraps semantic_diff
- [ ] `engine.conformity.structural` — `_count_structural_elements(docx)` + comparator
- [ ] `engine.conformity.visual` — render docx → PIL → ascii_layout → diff features
- [ ] `engine.conformity.design` — multimodal upload via provider, prompt + structured schema
- [ ] `engine.conformity.technical` — format validators (cpf_valid, cep_valid, iso_date_valid, etc)
- [ ] `engine.conformity.aggregator` — `check_conformity()` top-level, weighted score
- [ ] `engine.conformity.report` — `ConformityReport` + `Failure` dataclasses
- [ ] CLI: `template-engine conformity --template T --candidate C --provider gemini`
- [ ] Integration com `batch.py`: `BatchReport.items[i].conformity` opcional

### Tests alvo

- Cada dimensão isolada (5 grupos, ~10 tests cada = 50)
- Aggregator integration (10 tests)
- CLI smoke (5 tests)
- **Total: ~65 novos tests**

### Critério done

- 5 dimensões funcionando + tests
- CLI `conformity` shipping + docs
- Smoke test real: doc conforme passa, doc com problema visual flagado
- batch_orchestrator integra report (opcional via flag `--check-conformity`)
- v0.3.0 bump

---

## v0.3 — Eval suite + CI + docs site 🟡

### Eval suite ❌

- [ ] **`benchmarks/datasets/`** — 3 datasets gold anonimizados (contratos, laudos, relatórios). 20-30 docs cada.
- [ ] **`benchmarks/eval.py`** — runner que executa pipeline em dataset + compara output vs gold
- [ ] **Métricas**: token preservation rate, schema validity, structural accuracy, latency, cost
- [ ] **LLM-as-judge** — Claude/GPT-4 avaliando saída vs gold em critérios estruturados
- [ ] **CLI**: `template-engine eval --provider gemini --dataset contratos`
- [ ] **Report HTML** — diff visual + métricas por etapa
- [ ] **Regression tests** — eval roda em PR, falha se cai >10% em qualquer métrica

### CI ✅ (parcial)

- [x] **GitHub Actions** workflow: lint (ruff) + format (ruff format) + type (mypy) + tests (pytest com coverage)
- [x] **Matrix** Python 3.11, 3.12, 3.13
- [x] **Coverage badge** README (via codecov)
- [ ] **Windows runner** — só ubuntu hoje
- [ ] **Auto-publish PyPI** em tag (release-please ou semver-action)
- [ ] **Dependabot** configurado
- [ ] **CodeQL** scan de segurança

### Docs site ✅ (mostly done)

- [x] **mkdocs-material** site em `docs/` → GitHub Pages live em https://luizhcrs.github.io/template-engine/
- [x] **Bilingual EN/PT-BR** via `mkdocs-static-i18n`
- [x] Pages: Home, Quickstart, Concepts/{pipeline,preset,render-ops}, Providers/index, Contributing
- [x] **Custom theme**: paleta brand orange, hero card, feature grid, custom CSS
- [ ] **API reference** auto-gerada via mkdocstrings
- [ ] **Examples cookbook** — atualmente 3 examples (`01_quickstart`, `02_custom_provider`, `03_validation`); meta = 5+ casos reais (contratos jurídicos, laudos técnicos, migração legacy, RH, etc)
- [ ] **Mike** — versionamento de docs por release
- [ ] **Social cards** via mkdocs-material[imaging]

### Critério done v0.3

- Eval suite com ≥1 dataset rodando + métricas reproduzíveis
- CLI básica `template-engine convert|eval`
- mkdocstrings gerando API reference
- 5+ examples cookbook

---

## v0.4 — Extractors avançados

**Por quê:** PDFs escaneados, tabelas complexas, e formatos além de docx/pdf são casos reais que hoje falham.

### OCR

- [ ] **`engine.extractor.ocr`** — easyocr ou tesseract para PDFs sem texto
- [ ] **Auto-detect** — se PDF tem zero texto extraível, dispara OCR
- [ ] Suporte a multi-language (pt, en, es)

### Formatos novos

- [ ] **ODT** (LibreOffice) — via `odfpy`
- [ ] **RTF** — via `striprtf`
- [ ] **HTML** — via `beautifulsoup4`
- [ ] **Markdown** input — passthrough estruturado
- [ ] **Spreadsheet** (.xlsx, .csv) — via `openpyxl` + `pandas`
- [ ] **Imagens com texto** (.png, .jpg) — OCR direto

### Layout-aware extraction

- [ ] **GROBID integration** (opcional) — pra papers científicos com extração estrutural
- [ ] **LayoutLM/Donut** (opcional, Hugging Face) — extração estruturada de PDFs complexos
- [ ] Detecção de **headers/footers/footnotes/comments/track changes** em .docx

### Tabelas

- [ ] Tabelas multi-página em PDFs (camelot ou tabula-py)
- [ ] Tabelas com células mescladas
- [ ] Tabelas embutidas em outras tabelas

---

## v0.5 — Renderer expandido

**Por quê:** hoje só sai `.docx`. Cliente real quer PDF, HTML, Markdown.

- [ ] **PDF output** — via `weasyprint` ou `docx2pdf` (Linux + Windows)
- [ ] **HTML output** — clean semantic HTML5
- [ ] **Markdown output** — pra docs estáticas / Notion-like
- [ ] **TOC generation** automática a partir de `schema.json`
- [ ] **Headers/footers dinâmicos** com placeholders (page number, doc title, version)
- [ ] **Imagens embutidas** preservadas no output
- [ ] **Render ops Jinja-like** — sintaxe expressiva pra condicionais e loops em `render_ops.yaml`

---

## v0.6 — Smart preset learning

**Por quê:** preset_creator atual é one-shot. Estado-da-arte é continuous learning + feedback.

- [ ] **Active learning** — engine pergunta dúvidas durante criação ("este campo é obrigatório?")
- [ ] **Feedback loop** — usuário corrige output → correção vira exemplo few-shot do preset
- [ ] **Preset versioning** — `pattern.md` versionado, diff entre versões
- [ ] **Multi-template auto-detect** — engine identifica qual preset aplicar dado um documento-fonte (classificador)
- [ ] **Preset marketplace** (futuro) — comunidade publica/compartilha presets em hub público

---

## v0.7 — Validation & quality

**Por quê:** validator hoje só checa tokens críticos. Estado-da-arte tem hallucination detection + calibrated confidence.

- [ ] **Strict schema validation** — `jsonschema` em toda saída do LLM
- [ ] **Hallucination detector** — cross-reference: cada campo do output deve ter origem no texto-fonte (BM25/embedding similarity)
- [ ] **Confidence calibration** — score 0-1 calibrado contra eval suite (não apenas heurística)
- [ ] **Diff visualizer** — HTML side-by-side source vs output, highlight de diferenças
- [ ] **Coverage por seção** — métricas de quanto cada seção do schema foi preenchida com confiança alta

---

## v0.8 — Observability

**Por quê:** prod sem trace = caixa preta. Lib séria expõe hooks pra observabilidade.

- [ ] **OpenTelemetry tracing** — span por etapa do pipeline (extract, map, validate, render)
- [ ] **Logging estruturado** com `structlog` — JSON logs com correlation_id
- [ ] **Metrics** — Prometheus exporter opcional (latência, throughput, error rate por provider)
- [ ] **Cost tracking** — quanto cada conversão custou em USD por LLM call
- [ ] **Hooks system** — `engine.hooks.before_extract`, `engine.hooks.after_render`, etc

---

## v0.9 — Performance

**Por quê:** escala matters quando tem 1000 docs/dia.

- [ ] **Async pipeline real** — `asyncio.gather` em paralelizações possíveis
- [ ] **Caching** — extracted docs cached por hash, embeddings em LRU, prompt cache (Anthropic feature)
- [ ] **Batch processing** — processar N docs em paralelo com semaphore
- [ ] **Streaming pra docs grandes** — extractor streaming pra .docx multi-MB
- [ ] **Worker pool** — `engine.batch.run_batch(docs, max_workers=8)`

---

## v1.0 — Production-ready

**Por quê:** v1.0 = sinaliza estabilidade pra adoção corporate.

### Security

- [ ] **PII detection** opcional (presidio ou similar) — mask CPF/email/telefone antes do LLM
- [ ] **Path traversal** — sanitize todos paths de input
- [ ] **Prompt injection guard** — detect+reject inputs com instruções suspeitas
- [ ] **Local-only mode** — modo sem LLM (apenas determinístico) pra docs sensíveis
- [ ] **Encryption at rest** opcional — `cryptography` pra presets sensíveis

### API

- [ ] **CLI completa** — `template-engine extract|preset|convert|eval|serve`
- [ ] **REST API server** opcional (`engine.serve.app` FastAPI built-in) — útil pra dev local
- [ ] **Python SDK** com type hints completos + mypy strict
- [ ] **JS/TS SDK** que chama REST API (pra frontends consumirem)
- [ ] **Docker image** oficial publicada em ghcr.io

### Plugin system

- [ ] **Custom extractors** via entry_points (`engine.extractors`)
- [ ] **Custom renderers** via entry_points (`engine.renderers`)
- [ ] **Custom providers** via entry_points (`engine.providers`)
- [ ] **Plugin docs** explicando como contribuir

### Stability

- [ ] **API freeze** — semver estrito a partir de v1.0
- [ ] **Migration guide** v0.x → v1.0
- [ ] **Deprecation policy** documentada

---

## Beyond v1.0 — Research

Coisas exploratórias que vão depender de validação prática.

- [ ] **Multi-modal extraction** — modelos vision (Gemini Vision, GPT-4o, Claude vision) extraindo de imagens/scans direto
- [ ] **Fine-tuning suite** — fine-tune modelo pequeno (Phi, Llama, Qwen) num dataset de presets — provider local barato
- [ ] **Self-improving prompts** — prompt evolution via DSPy ou similar
- [ ] **Federated learning** — clientes treinam local, agregam global sem expor dados
- [ ] **Document graph** — knowledge graph extraído + entity linking entre docs
- [ ] **Real-time collaboration** — múltiplos usuários editando preset simultaneamente

---

## Critérios "estado da arte"

Não basta features. Pra ser referência:

1. **Eval pública** — benchmark suite open + leaderboard mostrando vs concorrentes (unstructured.io, llamaindex, langchain readers)
2. **Reprodutibilidade** — toda métrica do README é reproduzível com `make benchmark`
3. **Type-safe** — mypy strict 100%
4. **Lint zero warnings** — ruff strict
5. **Coverage ≥85%**
6. **Doc site** com 5+ tutoriais cookbook
7. **3+ contributors externos** (sinaliza tração real)
8. **PyPI downloads >1k/mês**
9. **GitHub Stars >100** (nice-to-have, não core)
10. **Citado em paper ou blog técnico** de terceiro

---

## Princípios não-negociáveis

- **Renderer permanece determinístico.** Nada de LLM decidindo formatação visual.
- **Stateless engine.** Nenhuma I/O implícita. Recebe paths/bytes, retorna paths/bytes.
- **Multi-provider obrigatório a partir de v0.2.** Lock-in em 1 LLM = não é estado da arte.
- **Tests acompanham features.** Nada merge sem teste novo.
- **Apache 2.0 forever.** Não migrar pra BSL/proprietário depois.

---

## Métricas norte (12 meses)

- v1.0 lançado até 2027-04-25
- Pipeline rodando em ≥3 produtos/aplicações distintas
- Eval suite com ≥3 datasets gold
- ≥1k downloads/mês PyPI
- Cited em ≥1 blog/paper técnico
- ≥3 PRs externos merged
