---
title: Section mapper
---

# Section mapper

Companheiro do [`normalize_batch`][batch] para templates **estruturais** que vêm com seções nomeadas porém vazias (`OBJETIVO`, `APLICAÇÃO`, ...) e dependem de hierarquia de heading + tabelas + layout de células em vez de tokens `{{X}}` explícitos.

Dois modos lado-a-lado:

- **rules engine (`mode="rules"`)** — determinístico, grátis, zero LLM. Heurísticas hardcoded PT-BR/Engeman. Paridade DOcStream no primeiro par real Engeman.
- **LLM-driven mapper (`mode="llm"` / `"hybrid"`)** — vendor-agnostic. UMA chamada multimodal LLM (template renderizado em PNG + JSON estrutural + content fonte) retorna `MappingPlan` completo cobrindo header subs, section content, paragraph rewrites, table data, e cell-level fills. Validado em:
  - Par Engeman original (PT-BR industrial).
  - 5 pares sintéticos adversariais (English corporate, ABNT acadêmico, gov form bilíngue, contrato legal, mega-table layout).
  - 2 templates reais baixados de sites públicos (UNIFAP POP — universidade federal; Corentocantins POP — conselho regional de enfermagem).

[batch]: pipeline.pt.md

## Quando usar

Use `engine.section_mapper.map_sections` no lugar de `normalize_batch` quando:

- O template não tem `{{placeholder}}` — só headings + slots vazios + tabelas vazias.
- A fonte tem a mesma taxonomia de headings que o destino (mesmo com palavras diferentes: `DESCRIÇÃO` ↔ `SISTEMÁTICA`, `ESCOPO` ↔ `APLICAÇÃO`).
- Quer markers de sub-seção (`6.1.`, `6.2.1.`), markers de lista (`a.`, `b.`, `•`) e o header do template (código, autor, aprovador, data, título) preenchidos automaticamente da fonte.

## Pipeline ponta-a-ponta

```
template.docx ──┬─→ parse_docx ──→ list[DocxSection] (índices de parágrafo)
                │
                ├─→ detect_default_specs_with_source(template, source) ──→ list[TableSpec]
                │
                └─→ fill_template_header(output, metadata)

source.docx ────┬─→ parse_docx_source ──→ list[TextSection] (numeração resolvida)
                │
                └─→ extract_source_metadata ──→ HeaderMetadata
                                                    │
                                                    ▼
similarity (string / embeddings / llm) ─→ list[HeadingMatch]
                                                    │
                                                    ▼
_build_content_map ─→ dict[target_name -> conteúdo agregado da fonte]
                                                    │
                                                    ▼
render_section_content (line-kind aware: subheading bold, nota italic)
                                                    │
                                                    ▼
fill_tables (header-set match, escrita de subheader)
                                                    │
                                                    ▼
prune empty body slots + collapse runs vazios
                                                    │
                                                    ▼
fill_template_header (XXXX → IT.PRO.URE.387.0005, TITULO → ...)
                                                    │
                                                    ▼
                                         SectionMappingReport
```

`map_sections_async` é o mesmo fluxo com a tier `llm` da similarity ligada como fallback final quando string + embeddings não cobrem o destino.

## Módulos

| Módulo | Responsabilidade |
|---|---|
| `engine.section_mapper.parser` | Detecção de heading em `.docx` + texto puro. `parse_docx` (template), `parse_docx_source` (fonte com numeração resolvida). |
| `engine.section_mapper.numbering` | `NumberingResolver` lê `word/numbering.xml`, percorre parágrafos com `<w:numPr>`, retorna o marker renderizado. |
| `engine.section_mapper.similarity` | Matcher 3-tier: string (sem deps) → embeddings (opcional) → llm (quando provider). |
| `engine.section_mapper.renderer` | Inserção de conteúdo multi-linha preservando formatação. Detecção de sub-heading + bold + spacing. |
| `engine.section_mapper.table_filler` | Preenchimento de tabela por header-set com `subheaders` opcional para templates com primary headers repetidos. |
| `engine.section_mapper.auto_tables` | Caminha template + fonte; sintetiza `TableSpec` para tabelas canônicas vazias (Histórico Rev/Data/Alteração, Atividades / Responsabilidade). |
| `engine.section_mapper.header_filler` | Extrai metadata do header da fonte + tabela de revisões; substitui `XXXX` / `Rev. 00` / `Elaborado:` / `Aprovado:` / `Data:` / `(TITULO)` no header do template. |
| `engine.section_mapper.orchestrator` | `map_sections` e `map_sections_async` + `SectionMappingReport`. |

## Parser — detecção de heading

Heading detectado quando parágrafo:

1. Tem estilo Word `Heading <N>`.
2. Bate o padrão numerado (`1. OBJETIVO`, `3.2. Etapas...`).
3. Bate o padrão all-caps sem número (`OBJETIVO`, `NORMAS E DOCUMENTOS DE REFERÊNCIA`).

Hardening (cada um documentado com teste de regressão):

- 2+ separadores (`FAFEN-SE/PR/AM`) — rejeitado.
- Single-word ≤4 letras (`PE`, `NA`, `CFM`) — rejeitado.
- Sentenças all-caps > 60 chars — rejeitadas.
- Linhas com `:` (label `EMPRESA: ACME`) — rejeitadas.
- Linhas terminando em dígito (campo `PROTOCOLO 12345`) — rejeitadas.
- Labels parentesizados (`(TITULO)`) — rejeitados.
- Labels de versão single-token (`REV.02`, `VERSAO_1.0`) — rejeitados.

PDFs comumente emitem cada heading duas vezes — uma na ToC, outra no corpo. O orchestrator deduplica por **conteúdo mais rico** por nome de heading, descartando linhas da ToC.

## Resolver de numeração

Quando a fonte é `.docx`, extração de texto puro perde a auto-numeração do Word: `<w:numPr>` referencia `word/numbering.xml` e o marker é renderizado em display, nunca escrito em `<w:t>`. O resolver corrige:

```python
from engine.section_mapper.numbering import load_resolver_from_docx, extract_num_pr

resolver = load_resolver_from_docx(Path("dados.docx"))
for p in doc.paragraphs:
    np = extract_num_pr(p._p.xml)
    if np:
        marker = resolver.marker_for(*np)  # "1.", "5.2.", "a.", "•", ...
```

Estado por `numId`; avançar um nível reseta todos os mais profundos. Fiel ao `numFmt` (`decimal`, `lowerLetter`, `upperLetter`, `lowerRoman`, `upperRoman`).

### Heurística bullet-as-letters (default ligado)

`bullet_as_letters=True` (default) renderiza bullets em `ilvl=0` como letras estilo Excel (`a.`, `b.`, ..., `z.`, `aa.`). Documentos industriais usam bullets Wingdings/Symbol internamente mas esperam saída com letras. `bullet_as_letters=False` para renderização estritamente fiel (`"•"` em todo nível bullet).

`reset_bullet_counters()` é chamado pelo parser sempre que um heading decimal estrutural avança, então cada sub-seção reinicia a sequência de letras em `a.` em vez de continuar entre fronteiras.

## Matcher de similaridade

Três tiers, ordenados por custo:

| Tier | Deps | Velocidade | Quando usar |
|---|---|---|---|
| **string** | nenhuma | µs | Fonte e destino usam mesmo vocabulário; tabela de sinônimos cobre variantes |
| **embeddings** | `pip install "template-engine-ia[embeddings]"` (sentence-transformers, ~80 MB) | ms | Vocabulário diverge entre templates (cross-vendor) |
| **llm** | provider | s + $ | Mapeamentos long-tail que heurísticas perdem |

Modo default é `"auto"`: string primeiro; cai pra embeddings (se instalado) quando cobertura < 60%; o caminho async adiciona llm como tier final quando provider supplied e embeddings ainda sub-cobrem.

Tabela de sinônimos cobre taxonomia industrial brasileira:

| Canônico | Variantes |
|---|---|
| `OBJETIVO` | FINALIDADE, PROPOSITO, FINALIDADES |
| `APLICACAO` | ESCOPO, AMBITO, ABRANGENCIA, ALCANCE |
| `SISTEMATICA` | DESCRICAO, PROCEDIMENTO, METODOLOGIA, DETALHAMENTO, EXECUCAO, PROCESSO |
| `RESPONSABILIDADE` | RESPONSABILIDADES, ATRIBUICOES, REGISTROS, RESPONSABILIDADES E AUTORIDADES |
| `HISTORICO` | HISTORICO DE REVISOES, CONTROLE DE REVISOES, REVISOES, HISTORICO DE REVISAO |
| `DEFINICOES` | TERMOS E DEFINICOES, GLOSSARIO, DEFINICOES SIGLAS |

## Renderer

Insere conteúdo da fonte sob o heading do template:

1. Encontra parágrafo do heading no template.
2. Localiza primeiro parágrafo vazio abaixo (o **âncora**).
3. Remove `<w:jc>` do `pPr` da âncora pra bloco multi-linha não renderizar como colunas justificadas.
4. Define texto da âncora pra linha 1 do conteúdo.
5. Pra cada linha restante: clona `<w:p>` da âncora, limpa `<w:t>` interno, define linha N, insere via `addnext` mantendo ordem.

### Decoração por tipo de linha (Phase 2)

Cada linha inserida classificada pelo prefixo + decorada:

| Prefixo | Tipo | Decoração |
|---|---|---|
| `^\d+\.\d+\.?\s` (ex. `6.1. Foo`) | sub-heading | bold + preto + `before=240/after=120` twips |
| `^\d+\.\d+\.\d+\.?\s` (ex. `6.2.1.`) | sub-sub-heading | bold + preto + `before=180/after=80` |
| `^Nota\s*\d*[:.]\s` | nota | italic |
| qualquer outro | body | inalterado |

Decoração aplicada via direct formatting — sem `<w:pStyle>` — porque os estilos default `Ttulo2`/`Ttulo3` do Word renderizam azul, errado para procedimentos industriais que esperam sub-heading preto bold.

### Limpeza de parágrafos vazios

Após inserção, dois passes evitam os gaps visuais que slots em branco do template deixariam:

- **Prune unused body slots**: percorre siblings de cada âncora preenchida; remove parágrafos vazios até próximo heading.
- **Collapse empty runs**: percorre body uma vez; colapsa qualquer run de 2+ parágrafos vazios consecutivos pra um único vazio. Parágrafos dentro de células de tabela ficam intocados (layout depende da contagem).

### Post-transforms section-aware (Phase 2)

Após parse da fonte, dois transforms section-name-driven rodam:

- Sections `NORMAS` / `REGISTROS` / `ANEXOS` / `DOCUMENTOS DE REFERÊNCIA`: cada linha sem marker recebe `"• "` (auto-bullet de reference list).
- Sections `DEFINIÇÕES`: `"term: "` (até 3 tokens curtos) vira `"term – "` (en-dash).

## Tabelas

`fill_tables(template, output, specs)` casa cada `TableSpec` à tabela do template por **header set** (sem ordem). `rows` da spec preenchem linhas vazias; rows extras são apendadas.

`TableSpec` extras:

- `subheaders: list[str] | None` — quando primary header repete (`["Atividades", "Responsabilidade", "Responsabilidade"]`), passar `["", "Gerente Setorial", "Supervisores"]` escreve esses na row 1 e usa pra mapeamento de coluna.

### Auto-tables

`detect_default_specs_with_source(template, source)` sintetiza specs sem config manual:

- **Histórico de Revisões** (`Rev. | Data | Alteração`): extrai tabela de revisões da fonte (matching `VERSÃO|DATA|AUTOR|ALTERAÇÕES`), renumera de `00`, apenda row `"Migração para o novo modelo padrão"` com data de hoje.
- **Atribuições e Responsabilidades** (`Atividades | Responsabilidade | Responsabilidade`): extrai parágrafos da fonte sob `Compete à gerência` / `Compete aos supervisores`; cada filho vira row com `X` na coluna correta. Fronteira de bucket detectada via `<w:numPr>` `ilvl` para extrator não vazar pra próxima top-level.

Quando auto-table preenche dados de target section (Responsabilidade / Histórico), o orchestrator suprime o body em prosa pra info não aparecer duplicada.

## Header filler

`extract_source_metadata(source_path)` lê fonte `.docx` e coleta:

| Campo | Origem |
|---|---|
| `document_code` | `word/header*.xml` da fonte, código dotted-decimal remontado de runs fragmentados (`IT.PRO.` + `U` + `RE` + `.387.0005`) |
| `title` | header da fonte, run all-caps multi-word mais longo que não seja nome da empresa nem doc code |
| `version` | header da fonte, `Ver.: NN` / `Rev. NN` |
| `author` | tabela de revisões da fonte, coluna `AUTOR / REVISOR`, primeira data row não-vazia |
| `approver` | header da fonte, `Aprovador (es): <nome>` (corta no próximo indicador de página / data) |
| `source_date` | tabela de revisões da fonte, coluna `DATA`, primeira data row não-vazia |

`fill_template_header(output_path, metadata)` percorre `word/header*.xml` no zip do output e substitui:

| Placeholder | Substituição |
|---|---|
| `XXXX` | `metadata.document_code` |
| `Rev. 00` | `Rev. <version>` |
| `Elaborado:` | `Elaborado: <author>` |
| `Aprovado:` | `Aprovado: <approver>` |
| `Data:` | `Data: <today_iso>` |
| `TITULO` | `metadata.title` |

Quando metadata da fonte está faltando para um placeholder, o placeholder fica intacto pra reviewer ver o gap.

### Reassembly de doc-code

Headers da fonte fragmentam código em vários `<w:t>` (`IT.PRO.` + `U` + `RE` + `.387.0005`) E colam company tag sem boundary (`...TRABALHOIT.PRO.URE.387.0005...`).

Extrator gera dois flavors de texto plano — **glued** (sem espaço entre runs, dotted code intacto) e **spaced** (espaço único entre runs, títulos como `PARTIDA DA ÁREA DE SÍNTESE` seguido por `Ver.:` não viram `SÍNTESEVer`). Prefixo `[A-Z]{2,3}\.[A-Z]{2,5}\.` localizado no spaced; state machine no glued consome o código completo, parando na primeira transição letra↔dígito inválida (`...0005PARTIDA` para em `0005`).

## Exemplo rápido

```python
from pathlib import Path

from engine.section_mapper import map_sections

report = map_sections(
    template_path=Path("template.docx"),
    source_path=Path("source.docx"),
    output_path=Path("output.docx"),
    # similarity_mode="auto" + auto_tables=True são defaults
)

print(f"sections mapeadas: {report.mapped_count}")
print(f"tabelas preenchidas: {report.tables_filled}")
print(f"source headings sem destino: {report.unmapped_source_headings}")
print(f"target headings sem origem: {report.unfilled_target_headings}")
print(f"placeholders órfãos: {report.orphan_paragraphs}")
```

`SectionMappingReport.to_dict()` retorna sumário JSON-serializável adequado pra audit log.

## Modos de operação

| Mode | Quando | Custo (Gemini Flash 2.5) |
| --- | --- | --- |
| `rules` (default em `map_sections`) | PT-BR / Engeman; bit-for-bit reproducibility | $0.0000 |
| `llm` (`map_sections_async(mode="llm", llm=...)`) | qualquer vendor / idioma; precisa provider | ~$0.001 |
| `hybrid` (`mode="hybrid", llm=...`) | rules primeiro, LLM cobre gaps | ~$0.001 quando gaps |

### LLM mode end-to-end

```python
import asyncio
from pathlib import Path

from engine.llm.openai_provider import OpenAIProvider
from engine.section_mapper import map_sections_async

async def main() -> None:
    provider = OpenAIProvider(api_key="sk-...", model="gpt-4o", timeout=300.0)
    report = await map_sections_async(
        template_path=Path("template.docx"),
        source_path=Path("source.docx"),
        output_path=Path("output.docx"),
        mode="llm",
        llm=provider,
    )
    print(f"sections no plan: {len(report.matches)}")
    print(f"tabelas preenchidas: {report.tables_filled}")

asyncio.run(main())
```

A chamada LLM retorna `MappingPlan` cobrindo todo placeholder detectado
(header + body), todo heading do template e toda tabela vazia. Falhas
caem em plan vazio pra caller encadear retry com rules.

### Validação cross-vendor

`tests/vendor_b/` traz template corporativo inglês sintético que
difere do par Engeman em toda dimensão:

| Dimensão | Engeman (vendor A) | Vendor B (corporate inglês) |
| --- | --- | --- |
| Idioma | Português | Inglês |
| Placeholders header | `XXXX`, `(TITULO)`, `Elaborado:`, `Aprovado:`, `Data:`, `Rev. 00` | `{{DOC_CODE}}`, `[Title]`, `Author:`, `Reviewer:`, `Issue Date:` |
| Taxonomia sections | `OBJETIVO`, `APLICAÇÃO`, `SISTEMÁTICA`, ... | `PURPOSE`, `SCOPE`, `PROCEDURE`, ... |
| Tabelas | `Atividades \| Responsabilidade \| Responsabilidade` (primary duplicado) + `Rev. \| Data \| Alteração` | `Activity \| Owner` (coluna única) + `# \| Date \| Description` |
| Texto migration row | `Migração para o novo modelo padrão` | `Migration to new standard template` (LLM segue idioma fonte) |

Ambos pares round-trip pra output completo via `mode="llm"`, sem
estender synonym table, sem editar regras por vendor. Regenerar
fixtures com:

```bash
python scripts/build_vendor_b_fixtures.py
```

## Modos de operação

| Modo | Quando | Custo (Gemini Flash 2.5) |
| --- | --- | --- |
| `rules` (default em `map_sections`) | PT-BR / Engeman; reprodutibilidade bit-for-bit | $0.0000 |
| `llm` (`map_sections_async(mode="llm", llm=...)`) | qualquer vendor / idioma; precisa provider | ~$0.001 |
| `hybrid` (`mode="hybrid", llm=...`) | rules primeiro, LLM cobre gaps | ~$0.001 quando gaps |

### Pipeline LLM ponta-a-ponta

```python
import asyncio
from pathlib import Path
from engine.llm.openai_provider import OpenAIProvider
from engine.section_mapper import map_sections_async

async def main() -> None:
    provider = OpenAIProvider(api_key="sk-...", model="gpt-4o", timeout=300.0)
    await map_sections_async(
        template_path=Path("template.docx"),
        source_path=Path("source.docx"),
        output_path=Path("output.docx"),
        mode="llm", llm=provider,
    )

asyncio.run(main())
```

`mode=None` (default) auto-pick: provider→llm, sem→rules.

### Multimodal vision

LLM call recebe PNG renderizado do template (até 3 pages) → vê células merged, geometria de tabela, logos. Pipeline:

```
template.docx → docx2pdf (Word COM) → PDF → PyMuPDF → PNG → base64 → OpenAI gpt-4o vision
```

`engine.section_mapper.template_renderer.render_pages(docx_path, max_pages=3)` retorna `list[PageImage]`. `docx2pdf` + `pymupdf` opcionais — quando faltam, fallback pra text-only. Install: `pip install docx2pdf pymupdf`.

### Cell-level fills

Mega-tables (Corentocantins) tem documento inteiro como tabela. `TemplateCell(table_index, row, col, text, is_fillable)` profile cada célula com heurística de fillability. `MappingPlan.cell_fills` endereça cada célula via coordenadas. `_apply_cell_fills` mirra fill em colunas merged (mesmo texto em N cols → preenche N).

Checklist deduplicado de fillable cells é appended ao prompt — LLM recebe lista uma-entry-por-slot ao invés de 8 idênticas.

### Plan validation + retry

Após call inicial, `_detect_plan_gaps` detecta:

- placeholders empty no plan
- headings empty quando source menciona keyword relevante
- tables empty não endereçadas

Retry focado pede só os slots faltantes. `_merge_plans` overlaya sem apagar valores prévios. `max_retries=1` default.

### Plan cache

`engine.section_mapper.plan_cache` persiste planos em `${XDG_CACHE_HOME:-~/.cache}/template-engine/plans/` keyed por `sha256(template) + sha256(source) + PROMPT_VERSION`. Mesmo par → 0 LLM calls. Override: `TEMPLATE_ENGINE_CACHE_DIR=/path`.

Benchmark Vendor E gpt-4o: 1ª run 20s | 2ª run (cache hit) 4.6s.

CLI `--no-cache` skip pra one-off runs.

### Source polimórfico

`profile_source` aceita `Path | str | bytes | bytearray | BytesIO | URL | SourceStructure`. Bytes/streams/URLs vão pra `NamedTemporaryFile` antes do walk.

### CLI

```bash
template-engine map-sections \
    --template ./template.docx \
    --source ./source.docx \
    --output ./output.docx \
    --provider openai --api-key "$OPENAI_API_KEY" --model gpt-4o
```

Auto-pick mode quando provider supplied. `--no-cache` desliga cache. `--json <path>` emite report.

### Validação cross-vendor

| Par | Domínio | Idioma | Forma |
| --- | --- | --- | --- |
| **A — Engeman** | procedimento industrial | PT-BR | `XXXX` / `(TITULO)` / Atividades \| Resp \| Resp |
| **B — English corporate** | procedimento corporate | EN | `{{DOC_CODE}}` / `[Title]` / Activity \| Owner |
| **C — ABNT academic** | tese | PT-BR Title-case | `<<TITULO>>` / `§§§§§` / nested |
| **D — Bilingual gov form** | formulário | PT-BR / EN | `[______]` / `< nome >` / CNPJ mask |
| **E — Legal contract** | contrato | PT-BR | parties block / cláusulas 1-6 |
| **UNIFAP POP** (real) | procedimento universitário | PT-BR | Title-case / `XXXXXXXX` / contact table |
| **Corentocantins POP** (real) | POP enfermagem | PT-BR | mega-table 20×8 merged |

Resultado vs gpt-4o: A/B/E 7/7 sections; C 6/9 (3 source-empty); D 5/5; UNIFAP 14 plan keys; Corentocantins partial mega-table.

Regenerate via:
```bash
python scripts/build_vendor_b_fixtures.py
python scripts/build_adversarial_fixtures.py
python scripts/build_real_world_source.py
python scripts/run_adversarial_llm.py
python scripts/run_real_world_llm.py
```

## Limites

Veja [REAL-WORLD-LIMITS.md][limits] pra lista completa. Honest call-outs:

[limits]: https://github.com/Luizhcrs/template-engine/blob/main/REAL-WORLD-LIMITS.md

### rules mode

- PDFs escaneados não passam por OCR. Use `.docx` quando possível.
- PDFs multi-coluna interleavam — converta pra single-column.
- Tabelas source não-canônicas vêm flatten.
- Synonym table PT-BR only. Instale `[embeddings]` ou use LLM.
- Sub-seção (`3.2.1.`) preservada como text prefix.

### LLM mode

- **Determinismo perdido** — gpt-4o varia entre runs. Cache mitiga em re-runs.
- **Custo** — ~$0.05/doc gpt-4o, ~$0.001 Gemini Flash. Cache torna follow-up grátis.
- **Multimodal opcional** — sem `docx2pdf`/`pymupdf` cai pra text-only.
- **Token cap** — template JSON 30k chars, source JSON 60k chars. Templates muito grandes truncam.
- **Mega-table body slots** com hint imperativo + heading numerado ainda parcialmente resistem (Corentocantins rows 2-7).

### Universal

- **Variância de templates real é infinita.** 5 vendors hoje. Cada novo vendor é descoberta de novo failure-mode.
- **Sem CI integration test** pra `mode="llm"` (chama API paga). Produção exige smoke real no corpus do cliente.
