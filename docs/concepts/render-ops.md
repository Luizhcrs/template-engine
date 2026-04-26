# Render ops

Deterministic operations the renderer applies to a template + JSON content. **No LLM involved.**

## Available ops

### `set_header_field`

Replace `NAME: [A DEFINIR]` placeholder.

```yaml
- op: set_header_field
  params:
    name: CODIGO
    source_key: codigo
```

### `write_section`

Append a text block under a named heading.

```yaml
- op: write_section
  params:
    heading: OBJETIVO
    source_key: objetivo
```

### `write_list`

Bulleted list under a heading.

```yaml
- op: write_list
  params:
    heading: RESPONSÁVEIS
    source_key: responsaveis
    marker: "- "
```

### `write_table`

Populate a table from a list of dicts.

```yaml
- op: write_table
  params:
    heading: HISTÓRICO
    source_key: historico
    columns: [Rev, Data, Alteração]
```

### `write_steps`

Numbered steps with optional notes.

```yaml
- op: write_steps
  params:
    heading: PROCEDIMENTO
    source_key: passos
    prefix: "Passo "
    note_prefix: "Nota: "
```

### `write_auto_migration`

Append next-revision row to history table. Computes next rev as `max(existing) + 1`.

```yaml
- op: write_auto_migration
  params:
    heading: HISTÓRICO
    columns: [Rev, Data, Alteração]
    default_text: "Migrated to new template."
    source_key: historico
```

## Adding a custom op

1. Add a function in `engine/render_ops/<my_op>.py`:

```python
def my_op(ctx: dict, params: dict) -> None:
    doc = ctx["doc"]
    content = ctx["content"]
    # ... mutate doc using docx API
```

2. Register in `engine/render_ops/__init__.py`:

```python
from engine.render_ops.my_op import my_op

OP_HANDLERS["my_op"] = my_op
```

3. Submit a PR following [Contributing](../contributing.md).
