from engine.render_ops.sections import write_table


def write_auto_migration(ctx: dict, params: dict) -> None:
    """Adds a migration entry to the history table and renders it.

    params: heading, columns (e.g. ['Rev', 'Data', 'Alteração']), default_text, source_key (default 'historico')
    Appends {col0: next_rev, col1: today (DD/MM/YYYY), col2: default_text} to content[source_key]
    before rendering.
    """
    today = ctx["today"]
    columns = params["columns"]
    default_text = params.get("default_text", "Migração para o novo padrão.")
    source_key = params.get("source_key", "historico")
    content = ctx["content"]

    history = list(content.get(source_key, []) or [])
    new_rev = str(len(history)).zfill(2)
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
