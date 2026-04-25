from docx.oxml.ns import qn


def set_header_field(ctx: dict, params: dict) -> None:
    """Replaces "NAME: [A DEFINIR]" with "NAME: VALUE" in any w:t element of the doc.

    Scans all text elements (body paragraphs, headers, text-boxes) in order and
    performs the first match. Falls back to raw [A DEFINIR] replacement if the
    named pattern is not found.
    """
    doc = ctx["doc"]
    content = ctx["content"]
    name = params["name"].upper()
    source_key = params["source_key"]
    value = str(content.get(source_key, "A DEFINIR"))

    target = f"{name}: [A DEFINIR]"
    replacement = f"{name}: {value}"

    for t_el in doc.element.iter(qn("w:t")):
        if t_el.text and target in t_el.text:
            t_el.text = t_el.text.replace(target, replacement, 1)
            return

    # fallback
    for t_el in doc.element.iter(qn("w:t")):
        if t_el.text and "[A DEFINIR]" in t_el.text:
            t_el.text = t_el.text.replace("[A DEFINIR]", value, 1)
            return
