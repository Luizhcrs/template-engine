# template-engine

**Engine de normalização documental audit-grade. Regex-first, LLM-as-judge, zero LibreOffice. Construído pra ambientes regulados onde conteúdo de doc não pode vazar.**

[![CI](https://github.com/Luizhcrs/template-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/Luizhcrs/template-engine/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Release](https://img.shields.io/github/v/release/Luizhcrs/template-engine?display_name=tag&sort=semver)](https://github.com/Luizhcrs/template-engine/releases)

> **Docs**: <https://luizhcrs.github.io/template-engine/pt/>
> **Modelo de ameaça + residência de dados por provider**: [SECURITY-MODEL.md](SECURITY-MODEL.md)
> **README**: Português (este arquivo) · [English](README.md)

## Por que existe

Três problemas que soluções off-the-shelf não resolvem juntos:

| Problema | Resposta da lib |
|----------|-----------------|
| Custo: pagar LLM por doc quando 95% dos campos são extraíveis mecanicamente | **Hybrid mapper regex-first** — só o que regex não pegou vai pra LLM em uma chamada batched |
| Compliance: regulador quer auditabilidade + garantia que dado LGPD/HIPAA não saiu pra API externa | **`local_only=True`** raise antes de qualquer chamada remota. PII masking, audit log append-only, regex path replayable bit-a-bit |
| Verificação: "candidato bateu com o padrão?" — texto sozinho não basta; estrutura, layout, formatos importam | **`check_conformity` multi-dimensional** — texto + estrutural + visual + design + técnico, score por dimensão, veredito ponderado |

## Como funciona

Duas operações. Um pipeline. Cinco dimensões de conformidade.

```
                  template (.docx)              docs fonte (N x .docx/.pdf)
                        │                                  │
                        ▼                                  ▼
        ┌──────────────────────────┐         ┌──────────────────────────┐
        │ schema_inference         │         │ extractor                │
        │  detecta placeholders    │         │  texto + tabelas         │
        │  ({{X}}, [X], ___, ...)  │         └──────────────────────────┘
        └──────────────────────────┘                       │
                        │                                  ▼
                        ▼                  ┌──────────────────────────┐
        ┌──────────────────────────┐       │ pattern_inference        │
        │ FieldSchema list         │──┐    │  10 shapes pré-definidas │
        │  {name, type, required}  │  │    │  + grex (opcional)       │
        └──────────────────────────┘  │    └──────────────────────────┘
                                      │                    │
                                      ▼                    ▼
                          ┌─────────────────────────────────────┐
                          │ hybrid_mapper                        │
                          │  Tier 1: regex por campo (free)      │
                          │  Tier 2: LLM batched só nos missing  │
                          │  Output: source ∈ {regex, llm, miss} │
                          └─────────────────────────────────────┘
                                          │
                                          ▼
                          ┌─────────────────────────────────────┐
                          │ batch._apply_mapping_to_template     │
                          │  substituição de tokens em copy docx │
                          └─────────────────────────────────────┘
                                          │
                                          ▼
                          ┌─────────────────────────────────────┐
                          │ semantic_diff (LLM como juiz)        │
                          │  flags missing_in_output / mismatch  │
                          │  / extra_in_output                   │
                          └─────────────────────────────────────┘
                                          │
                                          ▼
                            BatchReport: high / medium / low / error
                            mapping summary + discrepancies por doc
```

Pra verificação, mesmas primitivas alimentam `check_conformity`:

```
                             check_conformity(template, candidate)
                                          │
            ┌─────────┬─────────┬─────────┼─────────┬─────────┐
            ▼         ▼         ▼         ▼         ▼         ▼
          text   structural  visual    design    technical    │
          (LLM)   (no LLM)  (no LLM)  (LLM mm)   (no LLM)    │
            │         │         │         │         │         │
            └─────────┴─────────┴─────────┴─────────┘         │
                              │                                │
                              ▼                                │
                  weighted score + threshold                   │
                              │                                │
                              ▼                                │
            is_conformant = (score >= 0.85) AND (zero critical) ◄
```

Custo por tier (Gemini Flash, ~3K tokens input por LLM call):

| Path | LLM calls | $/doc |
|------|-----------|-------|
| Regex resolve tudo | 0 | **$0.0000** |
| Alguns campos vão pra LLM fallback | 1 | ~$0.0006 |
| Com `semantic_diff` ligado | 2 | ~$0.0012 |
| Com `check_conformity(dimensions=[text, design])` | 4 | ~$0.0024 |

## Pipeline section-mapper (Wave L)

Para templates **estruturais** que vêm com seções nomeadas porém vazias (procedimentos industriais, NR-12/13, acadêmico ABNT) e dependem de hierarquia de heading + tabelas em vez de tokens `{{X}}`, use `engine.section_mapper.map_sections`:

```python
from pathlib import Path
from engine.section_mapper import map_sections

report = map_sections(
    template_path=Path("template.docx"),
    source_path=Path("source.docx"),
    output_path=Path("output.docx"),
    # similarity_mode="auto" + auto_tables=True são defaults
)

print(f"sections mapeadas: {report.mapped_count}; tabelas: {report.tables_filled}")
```

End-to-end em Engeman dados.docx com zero config (rules mode): 7/8 sections mapeadas, header preenchido (`IT.PRO.URE.387.0005`, `Rev. 01`, `Elaborado: ...`, `(PARTIDA DA ÁREA DE SÍNTESE)`), tabela Histórico extraída das revisões da fonte, tabela Responsabilidade populada dos parágrafos `Compete à gerência` / `Compete aos supervisores`.

### Modo LLM vendor-agnóstico (Wave M)

`map_sections_async(..., mode="llm", llm=provider)` faz UMA chamada multimodal que cobre QUALQUER par template+source. Sem heurística vendor hardcoded. Pipeline:

```
template.docx → docx2pdf → PDF → PyMuPDF → PNG pages
                                              │
template.docx + source.docx + PNG ──→ OpenAI gpt-4o vision
                                              │
                              MappingPlan (header subs, section content,
                                           paragraph rewrites, table data,
                                           cell-level fills)
                                              │
                                       apply to output.docx
```

Validado em 7 pares:

- **Engeman** (real PT-BR industrial) — paridade DOcStream.
- **Vendor B** (corporate inglês, sintético).
- **Vendor C** (ABNT acadêmico, Title-case + `<<TITULO>>`, sintético).
- **Vendor D** (formulário gov bilíngue, sintético).
- **Vendor E** (contrato com cláusulas numeradas, sintético).
- **UNIFAP POP** (real, `unifap.br`).
- **Corentocantins POP** (real, `corentocantins.org.br`, mega-table).

Smart-default: provider supplied → `"llm"`, sem → `"rules"`. `"hybrid"` roda rules + LLM cobre gaps. Plan cache (sha256 template+source) → re-runs grátis.

```python
import asyncio
from pathlib import Path
from engine.llm.openai_provider import OpenAIProvider
from engine.section_mapper import map_sections_async

async def run():
    provider = OpenAIProvider(api_key="sk-...", model="gpt-4o", timeout=300.0)
    await map_sections_async(
        template_path=Path("template.docx"),
        source_path=Path("source.docx"),
        output_path=Path("output.docx"),
        llm=provider,  # mode auto = "llm"
    )

asyncio.run(run())
```

CLI:

```bash
template-engine map-sections \
    --template template.docx --source source.docx --output out.docx \
    --provider openai --model gpt-4o
```

Veja [Section mapper](https://luizhcrs.github.io/template-engine/concepts/section_mapper/) pra reference completa Wave L (rules) + Wave M (LLM, multimodal vision, cell-level fills, retry, cache, source polimórfico, CLI).

## Rodada típica

```bash
template-engine normalize \
  --template ./padrao.docx \
  --source-dir ./entrada/ \
  --output-dir ./normalizados/ \
  --provider gemini \
  --gold-doc gold_01.docx --gold-doc gold_02.docx --gold-doc gold_03.docx \
  --field-examples ./examples.json \
  --report ./report.json
```

O `report.json` agrupa cada input num tier:

- **`high`** — regex resolveu tudo, sem critical diff. Ship sem review.
- **`medium`** — LLM preencheu pelo menos 1 campo free-text, ou warning-level diff. Spot-check.
- **`low`** — placeholder órfão, campo obrigatório missing, ou critical diff. Abrir e editar.
- **`error`** — extração ou render falhou.

O custo depende da fração de docs que o tier regex resolve. Quando cobre todos os required, o LLM não é chamado e a rodada é grátis; caso contrário o LLM é invocado uma vez por doc com missing fields e (opcional) uma vez no semantic-diff QA.

## Instalação

```bash
pip install template-engine-ia                 # core
pip install "template-engine-ia[gemini]"          # + Google Gemini
pip install "template-engine-ia[openai]"          # + OpenAI
pip install "template-engine-ia[anthropic]"       # + Anthropic Claude
pip install "template-engine-ia[ollama]"          # + LLMs locais (LGPD-safe)
pip install "template-engine-ia[inference]"       # + grex regex learner
pip install "template-engine-ia[all]"             # tudo
```

## Quickstart — normalizar um diretório

```python
import asyncio
from pathlib import Path
from engine import normalize_batch
from engine.llm.gemini_free import GeminiFreeProvider

async def main():
    report = await normalize_batch(
        template_path=Path("template.docx"),
        source_dir=Path("docs/"),
        output_dir=Path("normalized/"),
        llm=GeminiFreeProvider(api_key="AIza..."),
        gold_docs=[open(p).read() for p in Path("gold/").glob("*.txt")],
        field_examples={
            "CODIGO":      ["ABC-001", "ABC-042", "ABC-099"],
            "DATA":        ["2026-01-15", "2026-04-26", "2026-07-30"],
            "RESPONSAVEL": ["Joao Silva", "Maria Souza", "Pedro Lima"],
        },
    )
    print(report.by_tier)         # {"high": 380, "medium": 15, "low": 5, "error": 0}
    print(report.llm_call_count)  # ~25 — 380 high docs custaram zero LLM

asyncio.run(main())
```

## Conformidade

```python
from engine import check_conformity

report = await check_conformity(
    template_path=Path("padrao.docx"),
    candidate_path=Path("candidato.docx"),
    llm=provider,
    schemas=schemas,
    mapping=mapping,
    dimensions=["text", "structural", "visual", "technical"],
    threshold=0.85,
)

print(report.summary_line)
# CONFORMANT score=0.92 threshold=0.85 failures=1 (critical=0)
```

`is_conformant = (score >= threshold) AND (zero critical failures)`. Um único critical (CPF inválido, placeholder órfão, campo perdido) reprova independente do score.

CLI: `template-engine conformity --template T --candidate C --provider gemini --threshold 0.85`.

## Modo local-only (LGPD/HIPAA)

```python
report = await normalize_batch(
    template_path, source_dir, output_dir,
    llm=None,
    field_examples=examples,
    gold_docs=golds,
    local_only=True,   # raise RefusedRemoteCallError se LLM passar
)
```

Em local-only só roda regex. Campos missing ficam missing. Matriz completa em [SECURITY-MODEL.md](SECURITY-MODEL.md).

## PII masking

```python
from engine.security import mask_pii, unmask

masked, mask = mask_pii(source_text)
# masked: "Cliente <CPF_001> nascido em <DATE>... contato <EMAIL_001>"
response = await llm.generate_structured(prompt(masked), schema)
restored = unmask(json.dumps(response), mask)
```

Detecta CPF, CNPJ, email, telefone (BR), RG, CEP. Cada valor único = 1 token estável; `unmask` restaura originais na resposta.

## Multi-provider com fallback

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

report = await normalize_batch(template, source_dir, output_dir, llm=router, ...)
```

Só `LLMRateLimit` / `LLMTimeout` disparam fallback. `LLMError` genérico propaga.

## Decisões de design (por que funciona)

- **Stateless.** Path/bytes in, paths/bytes/dataclasses out. Sem framework web, ORM, app layer.
- **Frozen dataclasses na API pública.** `MappingResult`, `Failure`, `ConformityReport`, etc. Equality + hashing de graça, sem mutação acidental.
- **Provider LLM via Protocol** (não ABC). Adicionar provider = implementar 1 método. Sem herança, sem registry magic.
- **Tier regex rejeita over-generalization.** Quando `grex` aprende padrão `\w+` sem âncoras estruturais, a lib cai pra freetext em vez de aceitar precisão falsa.
- **`is_conformant` exige zero criticals.** Score alto não cancela 1 critical (CPF inválido, placeholder órfão). Bate com mental model do regulador: "qualquer deal-breaker = fail".
- **Audit grava hashes, não conteúdo bruto.** `AuditLog` registra sha256 de inputs/outputs — auditor prova que doc foi processado sem que o log vire data store secundário.

## Adicionar seu provider

```python
from engine.llm.base import LLMError, LLMRateLimit, LLMTimeout

class MyProvider:
    name = "my-provider"
    model = "default"

    def __init__(self, api_key: str, model: str | None = None) -> None:
        if not api_key:
            raise RuntimeError("api_key required")

    async def generate_structured(self, prompt: str, json_schema: dict) -> dict:
        # chama API, parseia JSON; raise LLMRateLimit / LLMTimeout / LLMError quando aplicável
        ...
```

## Desenvolvimento

```bash
pip install -e ".[dev]"
ruff check . && ruff format --check . && mypy src/engine && pytest
```

189 tests — providers, pattern inference (Wave A), batch orchestrator (Wave D), conformity validator (Wave F), primitivas de segurança (Wave G).

## Roadmap

[ROADMAP.md](ROADMAP.md) — Wave A/D/E/F/G/H shipped na v0.6.

## Contribuir

Issues e PRs bem-vindos. Setup, estilo de código em [CONTRIBUTING.md](CONTRIBUTING.md). Reportar issues de segurança em [SECURITY.md](SECURITY.md).

## Licença

[Apache 2.0](LICENSE) — Copyright 2026 luizhcrs.
