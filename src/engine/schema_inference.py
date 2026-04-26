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


async def enrich_with_llm(
    schemas: list[FieldSchema],
    llm: LLMProvider,
) -> list[FieldSchema]:
    """Call the LLM once per schema entry to infer ``field_type``, ``format_hint``, ``required``.

    Returns a new list with enriched copies. Original list is not mutated.
    Failures per-field log a warning and keep ``field_type='unknown'``.
    """
    enriched: list[FieldSchema] = []
    for schema in schemas:
        try:
            result = await llm.generate_structured(
                prompt=_build_enrichment_prompt(schema),
                json_schema=_ENRICHMENT_SCHEMA,
            )
            enriched.append(
                FieldSchema(
                    name=schema.name,
                    placeholder_token=schema.placeholder_token,
                    kind=schema.kind,
                    field_type=str(result.get("field_type", "unknown")),
                    format_hint=result.get("format_hint"),
                    context_before=schema.context_before,
                    context_after=schema.context_after,
                    required=bool(result.get("required", True)),
                    aliases=schema.aliases,
                )
            )
        except Exception as exc:
            log.warning(
                "schema_inference.llm_enrichment_failed",
                field=schema.name,
                error=str(exc),
            )
            enriched.append(schema)
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
