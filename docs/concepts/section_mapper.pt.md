---
title: Section mapper (Wave L)
---

# Section mapper

Companheiro do [`normalize_batch`][batch] para templates **estruturais** que vêm com seções nomeadas porém vazias (`OBJETIVO`, `APLICAÇÃO`, ...) e dependem de hierarquia de heading + tabelas em vez de tokens `{{X}}` explícitos. Construído e validado contra documentos industriais (Engeman, NR-12 / NR-13, ABNT acadêmico).

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

## Limites

Veja [REAL-WORLD-LIMITS.md][limits] pra lista completa. Notáveis para `section_mapper`:

[limits]: https://github.com/Luizhcrs/template-engine/blob/main/REAL-WORLD-LIMITS.md

- PDFs escaneados não passam por OCR. Use fonte `.docx` quando possível.
- PDFs multi-coluna interleavam colunas no extract; converta pra coluna única primeiro.
- Tabelas da fonte (exceto Histórico/Responsabilidade canônicos) vêm como texto flatten.
- Tabela de sinônimos é PT-BR. Instale `[embeddings]` pra match cross-language ou use LLM provider.
- Hierarquia de sub-seção (`3.2.1.`) preservada como text prefix, não como anchors hierárquicos aninhados.
