"""Section-mapping orchestrator (Wave L).

End-to-end driver that wires the four section_mapper modules together:

```
parse_docx(template)        ─┐
parse_text(extract(source)) ─┴─► match (string -> embeddings -> llm)
                                  │
                                  ▼
                       content_by_target_heading
                                  │
                                  ▼
                       render_section_content (preserves format)
                                  │
                                  ▼
                       fill_tables (optional metadata)
                                  │
                                  ▼
                       SectionMappingReport
```

The report distinguishes *mapped* (heading paired with content), *unmapped*
(source heading with no target counterpart) and *unfilled* (target
heading that no source heading maps to). Callers can review the report
before shipping the rendered docx.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

import structlog

from engine.extractor import extract
from engine.section_mapper.parser import (
    DocxSection,
    TextSection,
    parse_docx,
    parse_docx_source,
    parse_text,
)
from engine.section_mapper.renderer import detect_orphan_paragraphs, render_section_content
from engine.section_mapper.similarity import (
    HeadingMatch,
    match_embeddings,
    match_llm,
    match_string,
)
from engine.section_mapper.table_filler import TableSpec, fill_tables

if TYPE_CHECKING:
    from pathlib import Path

    from engine.llm.base import LLMProvider

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class SectionMappingReport:
    """Outcome of a single section-mapping run."""

    template_path: Path
    source_path: Path
    output_path: Path
    target_sections: list[DocxSection]
    source_sections: list[TextSection]
    matches: list[HeadingMatch]
    tables_filled: int
    orphan_paragraphs: list[str]

    @property
    def mapped_count(self) -> int:
        return sum(1 for m in self.matches if m.target_name is not None)

    @property
    def unmapped_source_headings(self) -> list[str]:
        return [m.source_name for m in self.matches if m.target_name is None]

    @property
    def unfilled_target_headings(self) -> list[str]:
        filled = {m.target_name for m in self.matches if m.target_name}
        return [s.name for s in self.target_sections if s.name not in filled]

    def to_dict(self) -> dict:
        return {
            "template_path": str(self.template_path),
            "source_path": str(self.source_path),
            "output_path": str(self.output_path),
            "summary": {
                "target_sections": len(self.target_sections),
                "source_sections": len(self.source_sections),
                "mapped": self.mapped_count,
                "unmapped_source": self.unmapped_source_headings,
                "unfilled_target": self.unfilled_target_headings,
                "tables_filled": self.tables_filled,
                "orphan_paragraphs": self.orphan_paragraphs,
            },
            "matches": [asdict(m) for m in self.matches],
        }


_AUTO_COVERAGE_THRESHOLD = 0.6


def _coverage(matches: list[HeadingMatch], target_names: list[str]) -> float:
    """Fraction of target headings that received at least one source match."""
    if not target_names:
        return 1.0
    filled = {m.target_name for m in matches if m.target_name}
    return len(filled & set(target_names)) / len(target_names)


def _select_matches(
    source_sections: list[TextSection],
    target_names: list[str],
    *,
    similarity_mode: str,
    llm: LLMProvider | None,
) -> list[HeadingMatch]:
    """Run similarity in the requested mode, with graceful fallback.

    ``"auto"`` mode tries string first; falls back to embeddings when the
    optional dep is installed and string coverage is below the threshold.
    LLM fallback is only available through the async wrapper.
    """
    if similarity_mode == "string":
        return match_string(source_sections, target_names)

    if similarity_mode == "embeddings":
        return match_embeddings(source_sections, target_names)

    if similarity_mode == "auto":
        string_matches = match_string(source_sections, target_names)
        if _coverage(string_matches, target_names) >= _AUTO_COVERAGE_THRESHOLD:
            return string_matches
        emb_matches = match_embeddings(source_sections, target_names)
        if _coverage(emb_matches, target_names) > _coverage(string_matches, target_names):
            return emb_matches
        return string_matches

    if similarity_mode == "llm":
        if llm is None:
            log.warning("section_mapper.llm_mode_no_provider_falling_back_to_string")
            return match_string(source_sections, target_names)
        # match_llm is async; we'll handle it in the async wrapper below.
        raise RuntimeError("llm mode requires await; use map_sections_async")

    raise ValueError(f"unknown similarity_mode: {similarity_mode!r}")


def map_sections(
    template_path: Path,
    source_path: Path,
    output_path: Path,
    *,
    similarity_mode: str = "auto",
    table_specs: list[TableSpec] | None = None,
    auto_tables: bool = True,
) -> SectionMappingReport:
    """Synchronous entry point — ``auto`` / ``string`` / ``embeddings`` modes.

    Default ``similarity_mode="auto"`` runs string first and falls back to
    embeddings (when the optional dep is installed) if string coverage is
    below 60%. ``auto_tables=True`` synthesizes sensible defaults for
    canonical empty tables (Histórico Rev/Data/Alteração) so the caller does
    not need to pass a TableSpec for them.
    """
    from engine.section_mapper.auto_tables import detect_default_specs, merge_specs

    target_sections = parse_docx(template_path)
    source_sections = _dedupe_sections_by_richest(_parse_source(source_path))

    target_names = [s.name for s in target_sections]
    matches = _select_matches(
        source_sections,
        target_names,
        similarity_mode=similarity_mode,
        llm=None,
    )

    content_by_target = _build_content_map(source_sections, matches)
    render_section_content(
        template_path,
        output_path,
        docx_sections=target_sections,
        content_by_target=content_by_target,
    )

    effective_specs = table_specs
    if auto_tables:
        effective_specs = merge_specs(detect_default_specs(template_path), table_specs)

    filled = 0
    if effective_specs:
        filled = fill_tables(template_path, output_path, effective_specs)

    orphans = detect_orphan_paragraphs(output_path)

    report = SectionMappingReport(
        template_path=template_path,
        source_path=source_path,
        output_path=output_path,
        target_sections=target_sections,
        source_sections=source_sections,
        matches=matches,
        tables_filled=filled,
        orphan_paragraphs=orphans,
    )
    log.info(
        "section_mapper.done",
        mapped=report.mapped_count,
        unmapped=len(report.unmapped_source_headings),
        unfilled=len(report.unfilled_target_headings),
        tables_filled=filled,
        orphans=len(orphans),
    )
    return report


async def map_sections_async(
    template_path: Path,
    source_path: Path,
    output_path: Path,
    *,
    similarity_mode: str = "auto",
    llm: LLMProvider | None = None,
    table_specs: list[TableSpec] | None = None,
    auto_tables: bool = True,
) -> SectionMappingReport:
    """Async entry — supports the ``llm`` similarity mode in addition to
    ``auto`` / ``string`` / ``embeddings``.

    ``auto`` mode runs string + (embeddings if installed); when an LLM
    provider is supplied AND coverage is still below the threshold, the LLM
    matcher is invoked as the final tier.
    """
    from engine.section_mapper.auto_tables import detect_default_specs, merge_specs

    target_sections = parse_docx(template_path)
    source_sections = _dedupe_sections_by_richest(_parse_source(source_path))

    target_names = [s.name for s in target_sections]
    if similarity_mode == "llm" and llm is not None:
        matches = await match_llm(source_sections, target_names, llm=llm)
    elif similarity_mode == "auto":
        matches = _select_matches(source_sections, target_names, similarity_mode="auto", llm=None)
        # Final tier: LLM when string + embeddings still fell short
        if llm is not None and _coverage(matches, target_names) < _AUTO_COVERAGE_THRESHOLD:
            llm_matches = await match_llm(source_sections, target_names, llm=llm)
            if _coverage(llm_matches, target_names) > _coverage(matches, target_names):
                matches = llm_matches
    else:
        matches = _select_matches(
            source_sections,
            target_names,
            similarity_mode=similarity_mode,
            llm=llm,
        )

    content_by_target = _build_content_map(source_sections, matches)
    render_section_content(
        template_path,
        output_path,
        docx_sections=target_sections,
        content_by_target=content_by_target,
    )

    effective_specs = table_specs
    if auto_tables:
        effective_specs = merge_specs(detect_default_specs(template_path), table_specs)

    filled = 0
    if effective_specs:
        filled = fill_tables(template_path, output_path, effective_specs)

    orphans = detect_orphan_paragraphs(output_path)

    return SectionMappingReport(
        template_path=template_path,
        source_path=source_path,
        output_path=output_path,
        target_sections=target_sections,
        source_sections=source_sections,
        matches=matches,
        tables_filled=filled,
        orphan_paragraphs=orphans,
    )


def _parse_source(source_path: Path) -> list[TextSection]:
    """Route source parsing by file type.

    ``.docx`` sources go through :func:`parse_docx_source` which preserves
    Word's auto-numbering (numbered headings, sub-sections, list markers)
    by resolving ``<w:numPr>`` against ``word/numbering.xml``. Everything
    else falls back to plain-text extraction (PDF, txt, etc) where Word
    has already rendered the numbering into the text.
    """
    if source_path.suffix.lower() == ".docx":
        return parse_docx_source(source_path)
    text = extract(source_path).text
    return parse_text(text)


def _dedupe_sections_by_richest(
    sections: list[TextSection],
) -> list[TextSection]:
    """When the same heading appears multiple times (PDF table of contents +
    body section), keep only the occurrence with the most content. PDFs
    routinely reproduce headings in a TOC where the "content" between two
    consecutive TOC entries is empty or nearly empty.
    """
    by_name: dict[str, TextSection] = {}
    for s in sections:
        existing = by_name.get(s.name)
        if existing is None or len(s.content.strip()) > len(existing.content.strip()):
            by_name[s.name] = s
    # Preserve original order of the first occurrence
    seen: set[str] = set()
    out: list[TextSection] = []
    for s in sections:
        if s.name in seen:
            continue
        seen.add(s.name)
        out.append(by_name[s.name])
    return out


_FOOTER_MARKERS = re.compile(
    r"(?im)^\s*(?:"
    r"FORM\.[\w./-]+"
    r"|REPRODUCAO\s+PROIBIDA"
    r"|REPRODUÇÃO\s+PROIBIDA"
    r"|FL\.\s*\d+\s*/\s*\d+"
    r"|INTERNA\s+P[áa]gina\s+\d+\s+de\s+\d+"
    r"|Refer[êe]ncias\s+e\s+Anexos"
    r"|Dados\s+da\s+Refer[êe]ncia"
    r")"
)


def _trim_at_footer(content: str) -> str:
    """Cut section content at the first footer / annex marker line."""
    m = _FOOTER_MARKERS.search(content)
    if m is None:
        return content
    return content[: m.start()].rstrip()


def _build_content_map(
    source_sections: list[TextSection],
    matches: list[HeadingMatch],
) -> dict[str, str]:
    """Group matched source content under each target heading."""
    by_source = {s.name: _trim_at_footer(s.content) for s in source_sections}
    grouped: dict[str, list[str]] = {}
    for m in matches:
        if m.target_name is None:
            continue
        content = by_source.get(m.source_name, "")
        if not content.strip():
            continue
        # Avoid duplicating the same content under the same target
        existing = grouped.get(m.target_name, [])
        if content not in existing:
            grouped.setdefault(m.target_name, []).append(content)
    return {k: "\n\n".join(v) for k, v in grouped.items()}
