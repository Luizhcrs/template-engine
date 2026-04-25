from __future__ import annotations
from engine.render_ops.sections import write_table


def _next_revision(history: list[dict], rev_col: str) -> str:
    """Compute next revision number as max(existing) + 1, zero-padded to 2 digits."""
    max_rev = 0
    for entry in history:
        raw = entry.get(rev_col, "")
        try:
            n = int(str(raw).strip())
            if n > max_rev:
                max_rev = n
        except (ValueError, TypeError):
            continue
    return str(max_rev + 1).zfill(2)


def write_auto_migration(ctx: dict, params: dict) -> None:
    """Add a migration entry to the history table and render it.

    params:
        heading: nome da seção/heading da tabela
        columns: e.g. ['Rev', 'Data', 'Alteração']
        default_text: texto descritivo da migração (obrigatório, sem default PT-BR)
        source_key: chave do array no content (default 'historico')

    Appends {col0: next_rev, col1: today (DD/MM/YYYY), col2: default_text} to content[source_key].
    Computes next_rev as max(existing rev) + 1.
    """
    today = ctx["today"]
    columns = params["columns"]
    if "default_text" not in params:
        raise KeyError("write_auto_migration requires 'default_text' param (no PT-BR default)")
    default_text = params["default_text"]
    source_key = params.get("source_key", "historico")
    content = ctx["content"]

    history = list(content.get(source_key, []) or [])
    new_rev = _next_revision(history, columns[0])
    history.append({
        columns[0]: new_rev,
        columns[1]: today.strftime("%d/%m/%Y"),
        columns[2]: default_text,
    })

    new_content = dict(content)
    new_content[source_key] = history

    write_table(
        {"doc": ctx["doc"], "content": new_content, "today": today, "preset": ctx["preset"]},
        {"heading": params["heading"], "source_key": source_key, "columns": columns},
    )
