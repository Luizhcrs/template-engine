# Preset anatomy

A preset is a **versioned directory** that captures everything needed to convert source documents into a target pattern.

## Layout

```
presets/<slug>/
├── manifest.json       # metadata (slug, name, owner, locked, version, created_at)
├── template.docx       # target template (final desired layout)
├── gold/               # reference documents (1-5)
│   ├── gold-01.docx
│   └── gold-02.docx
├── pattern.md          # natural-language pattern description (editable)
├── schema.json         # JSON Schema for content extraction
├── render_ops.yaml     # deterministic ops applied to template
└── validation.yaml     # critical tokens + required sections
```

## File-by-file

### `manifest.json`

Metadata for tooling/display:

```json
{
  "slug": "contrato-prestacao",
  "name": "Contrato de Prestação",
  "version": 1,
  "owner_sub": "user-123",
  "locked": false,
  "created_at": "2026-04-25T17:00:00Z",
  "pattern_last_edited_at": null
}
```

### `pattern.md`

Markdown describing the pattern detected by the LLM during creation. **The brain of the preset.** You can edit it freely to refine tone, conventions, or implicit rules — changes apply on next conversion.

### `schema.json`

JSON Schema describing the expected output shape from the LLM. Drives the `llm_mapper` extraction step.

### `render_ops.yaml`

List of deterministic operations applied to the template. Each op has a name + params. Available ops:

- `set_header_field` — replace `NAME: [A DEFINIR]` placeholder
- `write_section` — append text under a named heading
- `write_list` — append bulleted list under a heading
- `write_table` — populate a table from list of dicts
- `write_steps` — numbered steps with optional notes
- `write_auto_migration` — append next migration row to history table

### `validation.yaml`

```yaml
critical_tokens:
  - {name: doc_code, regex: 'DOC\.\d{3}'}
  - {name: rev_year, regex: '\b20\d{2}\b'}
required_sections: [objetivo, procedimento, responsaveis]
min_completeness: 0.7
```

## Versioning

Presets are plain files — version with git. The `version` field in `manifest.json` is for human-readable bumps. `pattern_last_edited_at` tracks edits to the brain.
