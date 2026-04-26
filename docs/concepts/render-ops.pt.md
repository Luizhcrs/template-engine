# Operações de renderização

Operações determinísticas aplicadas pelo renderer no template + JSON. **Sem LLM envolvido.**

## Ops disponíveis

### `set_header_field`

Substitui placeholder `NAME: [A DEFINIR]`.

```yaml
- op: set_header_field
  params:
    name: CODIGO
    source_key: codigo
```

### `write_section`

Adiciona bloco de texto sob heading nomeado.

```yaml
- op: write_section
  params:
    heading: OBJETIVO
    source_key: objetivo
```

### `write_list`

Lista com bullets sob heading.

```yaml
- op: write_list
  params:
    heading: RESPONSÁVEIS
    source_key: responsaveis
    marker: "- "
```

### `write_table`

Preenche tabela a partir de lista de dicts.

```yaml
- op: write_table
  params:
    heading: HISTÓRICO
    source_key: historico
    columns: [Rev, Data, Alteração]
```

### `write_steps`

Passos numerados com notas opcionais.

```yaml
- op: write_steps
  params:
    heading: PROCEDIMENTO
    source_key: passos
    prefix: "Passo "
    note_prefix: "Nota: "
```

### `write_auto_migration`

Adiciona linha next-revision na tabela de histórico. Calcula próxima rev como `max(existing) + 1`.

```yaml
- op: write_auto_migration
  params:
    heading: HISTÓRICO
    columns: [Rev, Data, Alteração]
    default_text: "Migrado para template novo."
    source_key: historico
```

## Criando op customizada

1. Adicione função em `engine/render_ops/<minha_op>.py`:

```python
def minha_op(ctx: dict, params: dict) -> None:
    doc = ctx["doc"]
    content = ctx["content"]
    # ... muta doc via API do docx
```

2. Registre em `engine/render_ops/__init__.py`:

```python
from engine.render_ops.minha_op import minha_op

OP_HANDLERS["minha_op"] = minha_op
```

3. Submeta PR seguindo [Contribuindo](../contributing.md).
