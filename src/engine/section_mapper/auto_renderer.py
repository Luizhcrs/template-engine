"""Apply a :class:`MappingPlan` to a template, producing the output docx.

Wraps the existing renderer / table_filler / header_filler primitives:

- ``plan.section_content`` → ``render_section_content``
- ``plan.table_data`` → ``fill_tables`` with synthesized
  :class:`TableSpec`s (one per template-table index in the plan).
- ``plan.header_substitutions`` → run-preserving substitution in every
  ``word/header*.xml`` (same engine as ``header_filler`` but driven by
  the plan instead of the hardcoded placeholder map).

Output is the same format the rules-mode pipeline produces, so callers
can swap modes without changing downstream consumers.
"""

from __future__ import annotations

import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

from engine.section_mapper.parser import parse_docx
from engine.section_mapper.renderer import render_section_content
from engine.section_mapper.table_filler import TableSpec, fill_tables

if TYPE_CHECKING:
    from engine.section_mapper.auto_mapper import MappingPlan
    from engine.section_mapper.template_profiler import TemplateStructure


_HEADER_FILE_RE = re.compile(r"^word/header\d*\.xml$")
_BODY_FILE_RE = re.compile(r"^word/document\.xml$")


def apply_mapping_plan(
    template_path: Path,
    output_path: Path,
    *,
    plan: MappingPlan,
    template: TemplateStructure,
) -> int:
    """Materialize *plan* into ``output_path``.

    Returns the number of tables filled.
    """
    target_sections = parse_docx(template_path)

    render_section_content(
        template_path,
        output_path,
        docx_sections=target_sections,
        content_by_target=plan.section_content,
    )

    specs = _build_table_specs(plan, template)
    filled = 0
    if specs:
        filled = fill_tables(template_path, output_path, specs)

    if plan.header_substitutions:
        _apply_header_substitutions(output_path, plan.header_substitutions)
        # Body placeholders (e.g. ``{{DOC_CODE}}``, ``[Title]`` on the
        # cover page) get the same substitution map applied to
        # ``word/document.xml``.
        _apply_body_substitutions(output_path, plan.header_substitutions)

    return filled


def _build_table_specs(
    plan: MappingPlan,
    template: TemplateStructure,
) -> list[TableSpec]:
    """Translate the plan's ``table_data`` into ``TableSpec``s anchored
    to the template's empty tables (matched by ``template_table_index``).
    """
    by_index = {t.index: t for t in template.empty_tables}
    out: list[TableSpec] = []
    for entry in plan.table_data:
        tpl = by_index.get(entry.template_table_index)
        if tpl is None:
            continue
        if not entry.rows:
            continue
        out.append(
            TableSpec(
                headers=tpl.primary_headers,
                rows=entry.rows,
                subheaders=entry.sub_headers or None,
            )
        )
    return out


def _apply_header_substitutions(docx_path: Path, subs: dict[str, str]) -> None:
    """Inline-substitute placeholders in every ``word/header*.xml``.

    Placeholder match is per-``<w:t>`` (atomic node). Templates almost
    always store each header field as its own run group, so this works
    well for ``XXXX``, ``Rev. 00``, ``Elaborado:``, etc. For literals
    that span runs (rare), the LLM picks an alternate placeholder text
    that does sit in one ``<w:t>``.
    """
    if not subs:
        return

    with tempfile.NamedTemporaryFile(
        suffix=".docx",
        delete=False,
        dir=str(docx_path.parent),
    ) as tmp:
        tmp_path = Path(tmp.name)

    try:
        with (
            zipfile.ZipFile(str(docx_path), "r") as zin,
            zipfile.ZipFile(str(tmp_path), "w", zipfile.ZIP_DEFLATED) as zout,
        ):
            for item in zin.infolist():
                data = zin.read(item.filename)
                if _HEADER_FILE_RE.match(item.filename):
                    text = data.decode("utf-8")
                    text = _replace_in_runs(text, subs)
                    data = text.encode("utf-8")
                zout.writestr(item, data)
        shutil.move(str(tmp_path), str(docx_path))
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def _apply_body_substitutions(docx_path: Path, subs: dict[str, str]) -> None:
    """Same in-run substitution as the header path, but applied to
    ``word/document.xml`` so cover-page placeholders get filled too.
    """
    if not subs:
        return

    with tempfile.NamedTemporaryFile(
        suffix=".docx",
        delete=False,
        dir=str(docx_path.parent),
    ) as tmp:
        tmp_path = Path(tmp.name)

    try:
        with (
            zipfile.ZipFile(str(docx_path), "r") as zin,
            zipfile.ZipFile(str(tmp_path), "w", zipfile.ZIP_DEFLATED) as zout,
        ):
            for item in zin.infolist():
                data = zin.read(item.filename)
                if _BODY_FILE_RE.match(item.filename):
                    text = data.decode("utf-8")
                    text = _replace_in_runs(text, subs)
                    data = text.encode("utf-8")
                zout.writestr(item, data)
        shutil.move(str(tmp_path), str(docx_path))
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def _replace_in_runs(xml: str, subs: dict[str, str]) -> str:
    """Apply each ``placeholder -> replacement`` inside every ``<w:t>``."""

    def repl(m: re.Match[str]) -> str:
        prefix = m.group(1)
        inner = m.group(2)
        suffix = m.group(3)
        for placeholder, replacement in subs.items():
            if not placeholder:
                continue
            if placeholder in inner:
                inner = inner.replace(placeholder, _xml_escape(replacement), 1)
        return f"{prefix}{inner}{suffix}"

    pattern = re.compile(r"(<w:t(?:\s[^>]*)?>)([^<]*)(</w:t>)")
    return pattern.sub(repl, xml)


def _xml_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


__all__ = ["apply_mapping_plan"]
