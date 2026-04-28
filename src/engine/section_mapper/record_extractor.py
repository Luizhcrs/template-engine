"""Schema-driven record extraction.

Given a free-text source and a :class:`TableSchema`, ask the LLM to
produce a list of typed records that match the schema. The LLM call
is constrained by a JSON Schema derived from the ``TableSchema``, so
the model returns one well-shaped object per row.

This is the ONE focused thing the LLM does in the schema-driven
pipeline: pull structured records out of unstructured text. Alignment
and per-cell fill happen deterministically downstream.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, NewType

import structlog

from engine.section_mapper.schemas.types import ColumnType

if TYPE_CHECKING:
    from engine.llm.base import LLMProvider
    from engine.section_mapper.schemas.types import TableSchema


log = structlog.get_logger(__name__)


# A Record is just a plain dict keyed by column name. Wrapping it in
# NewType keeps the type-hint surface honest (this is a record, not
# any old dict) without forcing a class wrapper that adds nothing.
Record = NewType("Record", dict)


_TYPE_TO_JSON: dict[ColumnType, dict[str, Any]] = {
    ColumnType.PHONE: {
        "type": "string",
        "pattern": r"^\(?\d{2}\)?\s*\d{4,5}-?\d{4}$",
    },
    ColumnType.EMAIL: {"type": "string", "format": "email"},
    ColumnType.DATE: {
        "type": "string",
        "pattern": r"^\d{2}/\d{2}/\d{4}$",
    },
    ColumnType.NAME: {"type": "string", "minLength": 1},
    ColumnType.SECTOR: {"type": "string", "minLength": 1},
    ColumnType.ROLE: {"type": "string", "minLength": 1},
    ColumnType.VERSION: {
        "type": "string",
        "pattern": r"^\d+\.\d+(?:\.\d+)?$",
    },
    ColumnType.NUMBER: {"type": "integer", "minimum": 0},
    ColumnType.FREE: {"type": "string"},
}


def schema_to_json_schema(schema: TableSchema) -> dict[str, Any]:
    """Convert a :class:`TableSchema` to the JSON Schema we feed the
    LLM provider. Returns the wire-format object passed straight to
    ``llm.generate_structured(prompt, schema)``."""
    item_props: dict[str, Any] = {}
    required: list[str] = []
    for col in schema.columns:
        item_props[col.name] = _TYPE_TO_JSON[col.type]
        if col.required:
            required.append(col.name)
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "records": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": item_props,
                    "required": required,
                },
            }
        },
        "required": ["records"],
    }


_PROMPT = """\
Extract typed records from the SOURCE that match the table schema below.

SCHEMA: {schema_name}
COLUMNS: {columns_summary}

Each record must include EVERY required column. Optional columns may
be omitted when the source doesn't carry the value.

Return JSON only:
{{
  "records": [
    {{ "<column_name>": "<value>", ... }}
  ]
}}

SOURCE:
{source_text}

Output JSON only. No prose. No markdown.
"""


async def extract_records(
    source_text: str,
    schema: TableSchema,
    *,
    llm: LLMProvider,
) -> list[Record]:
    """Single LLM call. Returns a list of :class:`Record` objects with
    every schema column present (None for missing optional values).

    Records that fail required-column validation are dropped silently
    + logged. Returns ``[]`` on transport failure or malformed
    response — caller can fall through to the legacy slot pipeline.
    """
    columns_summary = ", ".join(f"{c.name}({c.type.value})" for c in schema.columns)
    prompt = _PROMPT.format(
        schema_name=schema.name,
        columns_summary=columns_summary,
        source_text=source_text[:60000],
    )
    json_schema = schema_to_json_schema(schema)

    try:
        response = await llm.generate_structured(prompt, json_schema)
    except Exception as exc:
        log.warning("section_mapper.record_extractor.llm_failed", error=str(exc))
        return []

    return _parse_response(response, schema)


def _parse_response(response: object, schema: TableSchema) -> list[Record]:
    if not isinstance(response, dict):
        return []
    raw = response.get("records")
    if not isinstance(raw, list):
        return []

    required = {c.name for c in schema.columns if c.required}
    column_names = [c.name for c in schema.columns]

    out: list[Record] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        if not required.issubset(entry.keys()):
            log.info(
                "section_mapper.record_extractor.record_missing_required",
                got=sorted(entry.keys()),
                required=sorted(required),
            )
            continue
        # Normalise: every schema column present, missing optionals
        # become None so downstream code can address them uniformly.
        normalised = {col: entry.get(col) for col in column_names}
        out.append(Record(normalised))

    log.info(
        "section_mapper.record_extractor.records_extracted",
        schema=schema.name,
        count=len(out),
    )
    return out


__all__ = [
    "Record",
    "extract_records",
    "schema_to_json_schema",
]


# Pretty json export for debugging — keeps the module-level json
# import in use even when the public surface doesn't need it directly.
def _dump_for_debug(records: list[Record]) -> str:
    return json.dumps(records, ensure_ascii=False, indent=2)
