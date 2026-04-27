"""Section content renderer — inserts multi-line content into a docx template.

The vanilla approach of stuffing multi-line text into a single ``<w:t>``
yields garbage when the host paragraph has ``<w:jc w:val="both"/>``
(justified) — Word distributes words across the line width and the output
looks like newspaper columns.

This renderer does it right:

1. Find the heading paragraph in the template.
2. Locate the first empty body paragraph below it (the "anchor").
3. Drop ``<w:jc>`` from the anchor's pPr to prevent the justified-blowout.
4. Set the anchor's text to line 1 of the content.
5. For each remaining line, clone the anchor's ``<w:p>``, clear inner
   ``<w:t>`` text, set line N, insert via ``addnext`` so paragraph order
   is preserved.

Bullet points / dash-prefixed lines stay as separate paragraphs (the
template usually has list paragraphs already styled); we don't rewrite
the list level.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from engine.section_mapper.parser import DocxSection


_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _strip_jc(p_elem) -> None:  # type: ignore[no-untyped-def]
    """Drop ``<w:jc>`` so a multi-line block doesn't render as columns."""
    pPr = p_elem.find(f"{_W_NS}pPr")
    if pPr is None:
        return
    jc = pPr.find(f"{_W_NS}jc")
    if jc is not None:
        pPr.remove(jc)


def _split_into_lines(content: str) -> list[str]:
    """Conservative line split. Drops empty lines, keeps bullets intact."""
    raw = [ln.strip() for ln in content.splitlines()]
    return [ln for ln in raw if ln]


def _set_paragraph_text(paragraph, text: str) -> None:  # type: ignore[no-untyped-def]
    """Set the paragraph's rendered text to *text*.

    For paragraphs that already have ``<w:r>`` runs, replaces every
    ``<w:t>`` payload (preserves run formatting). For empty paragraphs
    (no runs yet, common on template body slots), creates a fresh run via
    ``python-docx``.
    """
    p_elem = paragraph._p
    text_elements = p_elem.findall(f".//{_W_NS}t")
    if text_elements:
        text_elements[0].text = text
        for t in text_elements[1:]:
            t.text = ""
        return
    # Empty paragraph: add a fresh run so a <w:t> exists.
    paragraph.add_run(text)


def render_section_content(
    template_path: Path,
    output_path: Path,
    *,
    docx_sections: list[DocxSection],
    content_by_target: dict[str, str],
) -> None:
    """Open template, fill each empty section with its mapped content, save."""
    from docx import Document

    doc = Document(str(template_path))
    paragraphs = list(doc.paragraphs)

    # Build a quick {target_name -> heading_paragraph_idx} map
    heading_idx = {s.name: s.heading_paragraph_idx for s in docx_sections}

    for target_name, content in content_by_target.items():
        if not content.strip():
            continue
        idx = heading_idx.get(target_name)
        if idx is None:
            continue

        # Find the first empty body paragraph between this heading and the next
        next_heading_idx = _next_heading_idx(idx, docx_sections)
        anchor = None
        for j in range(idx + 1, next_heading_idx if next_heading_idx else len(paragraphs)):
            if not paragraphs[j].text.strip():
                anchor = paragraphs[j]
                break
        if anchor is None:
            continue

        lines = _split_into_lines(content)
        if not lines:
            continue

        _strip_jc(anchor._p)
        _set_paragraph_text(anchor, lines[0])

        # Append the rest as cloned siblings (insertion order preserved
        # by adding each new paragraph immediately AFTER the previous one).
        cursor = anchor._p
        for line in lines[1:]:
            new_p = deepcopy(anchor._p)
            _strip_jc(new_p)
            # Walk <w:t> directly on the cloned XML (no python-docx wrapper).
            ts = new_p.findall(f".//{_W_NS}t")
            if ts:
                ts[0].text = line
                for t in ts[1:]:
                    t.text = ""
            cursor.addnext(new_p)
            cursor = new_p

    doc.save(str(output_path))


def _next_heading_idx(current_idx: int, sections: list[DocxSection]) -> int | None:
    """Return the next heading's paragraph index after *current_idx*, or None."""
    candidates = [s.heading_paragraph_idx for s in sections if s.heading_paragraph_idx > current_idx]
    return min(candidates) if candidates else None


def detect_orphan_paragraphs(output_path: Path) -> list[str]:
    """Return paragraph texts that still contain ``{{X}}`` / ``[X]`` / ``___``.

    Useful as a post-render sanity check.
    """
    from docx import Document

    doc = Document(str(output_path))
    pattern = re.compile(r"\{\{[A-Za-z_][\w.-]*\}\}|\[[A-Za-z_][\w.-]*\]|_{3,}")
    return [p.text for p in doc.paragraphs if pattern.search(p.text)]
