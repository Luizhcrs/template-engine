"""Schema inference — derive field schema from a template document.

Reads a template (.docx or .pdf), detects placeholder tokens, and returns a list
of :class:`FieldSchema` describing the fields the template expects.

Placeholder syntaxes detected (in order of priority):

- ``{{NAME}}``        Mustache style
- ``{NAME}``          Single brace
- ``[NAME]``          Bracket style
- ``<<NAME>>``        Chevron style
- ``__NAME__``        Named blanks (double underscore wrap)
- ``___`` (3+)        Anonymous blanks → auto-named ``BLANK_<n>``

Each detected placeholder yields a :class:`FieldSchema` with surrounding context
text. When an :class:`engine.llm.base.LLMProvider` is supplied, the schema is
enriched with an inferred ``type`` and ``format_hint`` based on the surrounding
context.

Used by Wave D (orchestrator) to convert "1 template" into "JSON schema of fields
to extract per source doc" automatically.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

import structlog

from engine.extractor import extract

if TYPE_CHECKING:
    from pathlib import Path

    from engine.llm.base import LLMProvider

log = structlog.get_logger(__name__)

_CONTEXT_CHARS: Final[int] = 80

# Order matters: longer/more-specific tokens first to avoid partial matches.
# Each entry: (token_kind, full_pattern, name_extractor_pattern_or_None)
_PLACEHOLDER_PATTERNS: Final[list[tuple[str, re.Pattern[str]]]] = [
    ("mustache", re.compile(r"\{\{\s*([A-Z_][A-Z0-9_]*)\s*\}\}")),
    ("chevron", re.compile(r"<<\s*([A-Z_][A-Z0-9_]*)\s*>>")),
    ("named_blank", re.compile(r"__([A-Z][A-Z0-9_]*)__")),
    ("brace", re.compile(r"\{\s*([A-Z_][A-Z0-9_]*)\s*\}")),
    ("bracket", re.compile(r"\[\s*([A-Z_][A-Z0-9_]*)\s*\]")),
    ("anon_blank", re.compile(r"_{3,}")),
]


@dataclass(frozen=True)
class FieldSchema:
    """Describes one field expected by the template.

    Attributes:
        name: identifier (``CODIGO``, ``DATA``, ``BLANK_3``, ...).
        placeholder_token: literal substring as it appears in the template
            (e.g. ``{{CODIGO}}``, ``[DATA]``, ``___``).
        kind: which syntax matched (mustache/bracket/anon_blank/...).
        field_type: inferred type — ``unknown``, ``iso_date``, ``doc_code``,
            ``cpf``, ``cep``, ``fullname``, ``integer``, ``freetext``, etc.
        format_hint: regex hint or one example value, if known.
        context_before: up to 80 chars of template text immediately before the token.
        context_after: up to 80 chars of template text immediately after the token.
        required: whether the field must be filled (default True).
    """

    name: str
    placeholder_token: str
    kind: str
    field_type: str = "unknown"
    format_hint: str | None = None
    context_before: str = ""
    context_after: str = ""
    required: bool = True
    aliases: list[str] = field(default_factory=list)


def detect_placeholders(text: str) -> list[FieldSchema]:
    """Scan template text and return one :class:`FieldSchema` per placeholder occurrence.

    Each occurrence is recorded once (by token+position). Multiple appearances of
    the same name across the template collapse into a single schema entry whose
    ``context_before/after`` come from the first occurrence.
    """
    seen: dict[tuple[str, str], FieldSchema] = {}
    anon_counter = 0

    # Walk patterns in priority order; track consumed spans to avoid double-counting
    # (e.g. ``{{X}}`` should not also match ``{X}``).
    consumed: list[tuple[int, int]] = []

    for kind, pattern in _PLACEHOLDER_PATTERNS:
        for m in pattern.finditer(text):
            start, end = m.span()
            if any(s <= start < e or s < end <= e for s, e in consumed):
                continue
            consumed.append((start, end))

            if kind == "anon_blank":
                anon_counter += 1
                name = f"BLANK_{anon_counter}"
            else:
                name = m.group(1)

            key = (kind, name)
            if key in seen:
                continue

            ctx_before = text[max(0, start - _CONTEXT_CHARS) : start].rstrip()
            ctx_after = text[end : end + _CONTEXT_CHARS].lstrip()

            seen[key] = FieldSchema(
                name=name,
                placeholder_token=m.group(0),
                kind=kind,
                field_type="unknown",
                context_before=ctx_before,
                context_after=ctx_after,
            )

    log.info("schema_inference.detected", count=len(seen))
    return list(seen.values())


# JSON Schema for LLM enrichment response
_ENRICHMENT_SCHEMA: Final[dict] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "field_type": {
            "type": "string",
            "enum": [
                "iso_date",
                "br_date",
                "doc_code",
                "cpf",
                "cep",
                "uf",
                "decimal_br",
                "integer",
                "version",
                "fullname",
                "email",
                "phone_br",
                "currency_brl",
                "freetext",
                "unknown",
            ],
        },
        "format_hint": {"type": ["string", "null"]},
        "required": {"type": "boolean"},
    },
    "required": ["field_type", "format_hint", "required"],
}


def _build_enrichment_prompt(field_schema: FieldSchema) -> str:
    return (
        "You analyze a single placeholder in a document template and infer its "
        "field type from surrounding context.\n\n"
        f"Placeholder name: {field_schema.name}\n"
        f"Placeholder token: {field_schema.placeholder_token}\n"
        f"Context before: {field_schema.context_before!r}\n"
        f"Context after: {field_schema.context_after!r}\n\n"
        "Pick the most specific field_type from the enum. Use 'freetext' only when "
        "no structured type fits. format_hint is an optional example value or short "
        "description (max 60 chars). required=true unless context clearly suggests "
        "the field is optional."
    )


def _build_batch_enrichment_prompt(schemas: list[FieldSchema]) -> str:
    """Single prompt asking the LLM to enrich every field in one shot."""
    field_lines = []
    for s in schemas:
        ctx = (s.context_before + " ___ " + s.context_after).strip()
        field_lines.append(f"- {s.name} (token {s.placeholder_token!r}; context: {ctx[:120]!r})")
    return (
        "Analyze every placeholder below and infer its type from surrounding "
        "context. Return ONLY JSON keyed by field name.\n\n"
        "Fields:\n" + "\n".join(field_lines) + "\n\n"
        "For each field choose the most specific field_type. Use 'freetext' only "
        "when no structured type fits. format_hint is optional (max 60 chars). "
        "required=true unless context clearly suggests optional."
    )


def _batch_enrichment_schema(field_names: list[str]) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": dict.fromkeys(field_names, _ENRICHMENT_SCHEMA),
        "required": list(field_names),
    }


async def enrich_with_llm(
    schemas: list[FieldSchema],
    llm: LLMProvider,
) -> list[FieldSchema]:
    """Enrich every schema's ``field_type`` / ``format_hint`` / ``required`` in
    a single batched LLM call.

    Returns a new list of enriched copies. Original list is not mutated. On
    LLM failure the per-field schemas are returned unchanged with
    ``field_type='unknown'`` and a single warning log.
    """
    if not schemas:
        return []

    field_names = [s.name for s in schemas]

    try:
        response = await llm.generate_structured(
            prompt=_build_batch_enrichment_prompt(schemas),
            json_schema=_batch_enrichment_schema(field_names),
        )
    except Exception as exc:
        log.warning(
            "schema_inference.llm_enrichment_failed",
            count=len(schemas),
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return list(schemas)

    enriched: list[FieldSchema] = []
    for s in schemas:
        entry = response.get(s.name) if isinstance(response, dict) else None
        if not isinstance(entry, dict):
            enriched.append(s)
            continue
        enriched.append(
            FieldSchema(
                name=s.name,
                placeholder_token=s.placeholder_token,
                kind=s.kind,
                field_type=str(entry.get("field_type", "unknown")),
                format_hint=entry.get("format_hint"),
                context_before=s.context_before,
                context_after=s.context_after,
                required=bool(entry.get("required", True)),
                aliases=s.aliases,
            )
        )
    return enriched


async def infer_template_schema(
    template_path: Path,
    *,
    llm: LLMProvider | None = None,
) -> list[FieldSchema]:
    """Top-level helper: extract template text + detect placeholders + optional LLM enrichment.

    Args:
        template_path: path to a ``.docx`` or ``.pdf`` template.
        llm: optional :class:`LLMProvider`. When supplied, each field is enriched
            with an inferred ``field_type``/``format_hint``. Without it, the
            schemas are returned with ``field_type='unknown'``.

    Returns:
        List of :class:`FieldSchema`, one per placeholder.
    """
    extracted = extract(template_path)
    schemas = detect_placeholders(extracted.text)
    if llm is not None:
        schemas = await enrich_with_llm(schemas, llm)
        log.info("schema_inference.llm_enrichment_done", count=len(schemas))
    return schemas
