# template-engine — Roadmap

Goal: tornar a lib **state-of-the-art** em normalização documental via LLM. Deliberada, sem buzzword soup.

Ordem por impacto + foundation-first. Cada bloco entrega valor sozinho.

---

## v0.1.0 — Atual (released 2026-04-25)

Pipeline básico funcionando:
- Extractor `.docx` + `.pdf`
- Preset creator (LLM gera pattern + schema + render_ops)
- LLM mapper (prompt + few-shot + JSON Schema)
- Validator (tokens críticos + cobertura)
- Renderer (.docx output via render_ops)
- 1 provider: Gemini free
- 29 tests passing

**Limitações conhecidas:**
- 1 provider só
- Sem OCR (PDF escaneado falha)
- Sem suporte de tabelas multi-página
- API ainda recebe muito `Path`/`dict` solto, sem objetos tipados consistentes
- Zero observabilidade
- Zero CLI

---

## v0.2 — Multi-provider LLM (foundation)

**Por quê primeiro:** sem multi-provider, lib é "Gemini wrapper". Multi-provider abre testes A/B, cost-aware routing, e independência de fornecedor.

### Tasks

- [ ] **`engine.llm.openai_provider`** — OpenAI (gpt-4o-mini, gpt-4o, gpt-5)
- [ ] **`engine.llm.anthropic_provider`** — Claude (Sonnet 4.6, Opus 4.6, Haiku 4.5)
- [ ] **`engine.llm.groq_provider`** — Groq (Llama 3.3 70B, mixtral)
- [ ] **`engine.llm.ollama_provider`** — local (Ollama com modelo configurável)
- [ ] **`engine.llm.openrouter_provider`** — universal (400+ modelos)
- [ ] **`engine.llm.router`** — policy: `[primary, fallback1, fallback2]` com auto-rotation em rate limit / erro
- [ ] **`LLMConfig`** — config tipada (max_tokens, temperature, retry_attempts, timeout)
- [ ] **Streaming optional** — interface `generate_structured_stream` pra futuros casos
- [ ] **Tool use uniformizado** — abstração de function calling cross-provider

### Critério done

- 5 providers implementados, todos passando suite de tests comum
- Router faz fallback automático em rate limit
- Doc + exemplo no README pra cada provider

---

## v0.3 — Eval suite + CI + docs site

**Por quê:** sem eval, "qual provider é melhor" é chute. Sem CI, contribuições quebram main. Sem docs, OSS não cresce.

### Eval suite

- [ ] **`benchmarks/datasets/`** — 3 datasets gold anonimizados (contratos, laudos, relatórios). 20-30 docs cada.
- [ ] **`benchmarks/eval.py`** — runner que executa pipeline em dataset + compara output vs gold
- [ ] **Métricas**: token preservation rate, schema validity, structural accuracy, latency, cost
- [ ] **LLM-as-judge** — Claude/GPT4 avaliando saída vs gold em critérios estruturados
- [ ] **CLI**: `template-engine eval --provider gemini --dataset contratos`
- [ ] **Report HTML** — diff visual + métricas por etapa
- [ ] **Regression tests** — eval roda em PR, falha se cai >10% em qualquer métrica

### CI

- [ ] **GitHub Actions** workflow: lint (ruff) + format (black) + type (mypy strict) + tests (pytest com coverage >80%)
- [ ] **Matrix** Python 3.11, 3.12, 3.13
- [ ] **Coverage badge** README
- [ ] **Auto-publish** PyPI em tag (release-please ou semver-action)

### Docs site

- [ ] **mkdocs-material** site em `docs/` → GitHub Pages
- [ ] Pages: Quickstart, Concepts (preset/pipeline/render_ops), Providers, API Reference, Examples, Contributing
- [ ] **Examples cookbook** — 5+ casos reais (contratos, laudos, migração legacy, RH, etc)
- [ ] **API reference** auto-gerada via mkdocstrings

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
- Pipeline rodando em ≥3 SaaS distintos (normadocs + 2 outros)
- Eval suite com ≥3 datasets gold
- ≥1k downloads/mês PyPI
- Cited em ≥1 blog/paper técnico
- ≥3 PRs externos merged
