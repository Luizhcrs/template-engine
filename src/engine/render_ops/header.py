from __future__ import annotations
import structlog
from docx.oxml.ns import qn

log = structlog.get_logger(__name__)


def set_header_field(ctx: dict, params: dict) -> None:
    """Replace "NAME: [A DEFINIR]" with "NAME: VALUE" in the first matching w:t element.

    Scans body paragraphs, headers and text-boxes in document order. Replaces the FIRST occurrence
    where the named field placeholder appears. If the named pattern is not found, logs a warning
    and skips — never replaces a generic `[A DEFINIR]` placeholder belonging to another field.
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

    log.warning(
        "render_ops.set_header_field.no_match",
        name=name,
        source_key=source_key,
        hint="Template may be missing the named placeholder; skipping op",
    )
