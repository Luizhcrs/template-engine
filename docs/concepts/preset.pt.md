# Anatomia do preset

Um preset é um **diretório versionado** que captura tudo necessário pra converter documentos-fonte num padrão-alvo.

## Estrutura

```
presets/<slug>/
├── manifest.json       # metadata (slug, nome, owner, locked, version, created_at)
├── template.docx       # template-alvo (layout final desejado)
├── gold/               # documentos de referência (1-5)
│   ├── gold-01.docx
│   └── gold-02.docx
├── pattern.md          # descrição em linguagem natural (editável)
├── schema.json         # JSON Schema pra extração de conteúdo
├── render_ops.yaml     # operações determinísticas no template
└── validation.yaml     # tokens críticos + seções obrigatórias
```

## Arquivo a arquivo

### `manifest.json`

Metadata pra tooling/display:

```json
{
  "slug": "contrato-prestacao",
  "name": "Contrato de Prestação",
  "version": 1,
  "owner": "user-123",
  "locked": false,
  "created_at": "2026-04-25T17:00:00Z",
  "pattern_last_edited_at": null
}
```

### `pattern.md`

Markdown descrevendo o padrão detectado pelo LLM na criação. **O cérebro do preset.** Você pode editar livremente pra refinar tom, convenções ou regras implícitas — mudanças valem na próxima conversão.

### `schema.json`

JSON Schema descrevendo a forma esperada do output do LLM. Direciona o passo de extração no `llm_mapper`.

### `render_ops.yaml`

Lista de operações determinísticas aplicadas ao template. Cada op tem nome + params. Ops disponíveis:

- `set_header_field` — substitui placeholder `NAME: [A DEFINIR]`
- `write_section` — adiciona texto sob heading nomeado
- `write_list` — adiciona lista com bullets sob heading
- `write_table` — preenche tabela a partir de lista de dicts
- `write_steps` — passos numerados com notas opcionais
- `write_auto_migration` — adiciona próxima linha de migração na tabela de histórico

### `validation.yaml`

```yaml
critical_tokens:
  - {name: doc_code, regex: 'DOC\.\d{3}'}
  - {name: rev_year, regex: '\b20\d{2}\b'}
required_sections: [objetivo, procedimento, responsaveis]
min_completeness: 0.7
```

## Versionamento

Presets são arquivos simples — versionar via git. O campo `version` em `manifest.json` é pra bumps human-readable. `pattern_last_edited_at` rastreia edições no cérebro.
