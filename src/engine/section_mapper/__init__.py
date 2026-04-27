"""Section mapper (Wave L) — fill structural docx templates from source documents.

Companion subpackage to :mod:`engine.batch`. Wave D handled placeholder
templates (``{{X}}`` style); Wave L handles **structural** templates that
ship with named-but-empty sections (``"1. OBJETIVO\\n\\n2. APLICAÇÃO..."``)
and rely on heading hierarchy + tables instead of explicit tokens.

Modules:

- :mod:`.parser` — heading detection from docx + plain text.
- :mod:`.similarity` — match source heading -> target heading
  (``string`` / ``embeddings`` / ``llm``).
- :mod:`.renderer` — multi-line content rendering preserving formatting.
- :mod:`.table_filler` — populate empty tables from caller-supplied data.
- :mod:`.orchestrator` — :func:`map_sections` and
  :func:`map_sections_async`.

Top-level usage:

```python
from engine.section_mapper import map_sections, TableSpec

report = map_sections(
    template_path=Path("template.docx"),
    source_path=Path("dados.pdf"),
    output_path=Path("out.docx"),
    similarity_mode="string",
    table_specs=[
        TableSpec(
            headers=["Rev.", "Data", "Alteração"],
            rows=[{"Rev.": "00", "Data": "2026-04-26", "Alteração": "Emissão inicial"}],
        ),
    ],
)
print(report.to_dict())
```
"""

from __future__ import annotations

from engine.section_mapper.numbering import (
    NumberingResolver,
    load_resolver_from_docx,
)
from engine.section_mapper.orchestrator import (
    SectionMappingReport,
    map_sections,
    map_sections_async,
)
from engine.section_mapper.parser import (
    DocxSection,
    TextSection,
    parse_docx,
    parse_docx_source,
    parse_text,
)
from engine.section_mapper.renderer import (
    detect_orphan_paragraphs,
    render_section_content,
)
from engine.section_mapper.similarity import (
    HeadingMatch,
    match_embeddings,
    match_llm,
    match_string,
)
from engine.section_mapper.table_filler import TableSpec, fill_tables

__all__ = [
    "DocxSection",
    "HeadingMatch",
    "NumberingResolver",
    "SectionMappingReport",
    "TableSpec",
    "TextSection",
    "detect_orphan_paragraphs",
    "fill_tables",
    "load_resolver_from_docx",
    "map_sections",
    "map_sections_async",
    "match_embeddings",
    "match_llm",
    "match_string",
    "parse_docx",
    "parse_docx_source",
    "parse_text",
    "render_section_content",
]
