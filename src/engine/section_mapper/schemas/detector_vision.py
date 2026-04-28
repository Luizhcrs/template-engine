"""LLM-driven schema detector for tables that no builtin schema covers.

The builtin detector
(:func:`engine.section_mapper.schemas.detector.detect_table_schema`)
is a strict header-name matcher. When it returns ``None`` the
orchestrator can fall back to this module: ask the LLM, given the
header row plus a sample body row, to produce a :class:`TableSchema`
on the fly.

Result is cached on disk by sha256(headers + sample row) so the same
template doesn't re-pay the LLM call across runs.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

from engine.section_mapper.schemas.types import ColumnSpec, ColumnType, TableSchema

if TYPE_CHECKING:
    from engine.llm.base import LLMProvider


log = structlog.get_logger(__name__)


_DEFAULT_CACHE_DIR = Path(".template_engine_cache") / "schemas_vision"


_PROMPT = """\
You receive the header row and a sample body row of a docx table.
Produce a JSON ``TableSchema`` description that captures the meaning
of each column.

Rules:

- Output ONE entry per column, in the same order as the headers.
- ``type`` MUST be one of:
  ``phone``, ``email``, ``date``, ``name``, ``sector``, ``role``,
  ``version``, ``number``, ``free``.
- Pick ``free`` only when the content is genuinely unstructured
  prose (descriptions, observations).
- ``required=true`` for columns that should never be empty in a
  filled row (e.g. a row index, a primary identifier).
- ``schema_name`` is a short snake_case label describing the table
  (``vendor_table``, ``risk_register``, ``shift_schedule``, etc).

HEADERS: {headers_json}
SAMPLE_BODY_ROW: {sample_json}

Output JSON only. No prose. No markdown.
"""


_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "schema_name": {"type": "string"},
        "columns": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "type": {
                        "type": "string",
                        "enum": [ct.value for ct in ColumnType],
                    },
                    "required": {"type": "boolean"},
                },
                "required": ["name", "type"],
            },
        },
    },
    "required": ["schema_name", "columns"],
}


def _cache_key(headers: list[str], sample_row_texts: list[str]) -> str:
    payload = json.dumps(
        {"headers": headers, "sample": sample_row_texts},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_cached(cache_dir: Path, key: str) -> TableSchema | None:
    path = cache_dir / f"{key}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return _materialise(data)


def _save_cached(cache_dir: Path, key: str, data: dict) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{key}.json"
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        log.info("section_mapper.detector_vision.cache_write_failed", error=str(exc))


def _materialise(data: object) -> TableSchema | None:
    if not isinstance(data, dict):
        return None
    name = data.get("schema_name")
    raw_cols = data.get("columns")
    if not isinstance(name, str) or not isinstance(raw_cols, list) or not raw_cols:
        return None
    cols: list[ColumnSpec] = []
    for raw in raw_cols:
        if not isinstance(raw, dict):
            continue
        col_name = raw.get("name")
        col_type_str = raw.get("type")
        if not (isinstance(col_name, str) and isinstance(col_type_str, str)):
            continue
        try:
            col_type = ColumnType(col_type_str)
        except ValueError:
            continue
        required = bool(raw.get("required", False))
        cols.append(ColumnSpec(name=col_name, type=col_type, required=required))
    if not cols:
        return None
    return TableSchema(name=name, columns=cols)


async def detect_schema_from_table_async(
    *,
    headers: list[str],
    sample_row_texts: list[str],
    llm: LLMProvider,
    cache_dir: Path | None = None,
) -> TableSchema | None:
    """Ask the LLM to produce a :class:`TableSchema` for a table whose
    headers and first-body-row sample are given.

    Returns ``None`` on transport error, malformed response, or when
    the LLM declines to produce any columns. Callers fall back to the
    legacy slot pipeline in those cases.
    """
    cache_dir = cache_dir or _DEFAULT_CACHE_DIR
    key = _cache_key(headers, sample_row_texts)

    cached = _load_cached(cache_dir, key)
    if cached is not None:
        log.info(
            "section_mapper.detector_vision.cache_hit",
            schema=cached.name,
            columns=len(cached.columns),
        )
        return cached

    prompt = _PROMPT.format(
        headers_json=json.dumps(headers, ensure_ascii=False),
        sample_json=json.dumps(sample_row_texts, ensure_ascii=False),
    )

    try:
        response = await llm.generate_structured(prompt, _RESPONSE_SCHEMA)
    except Exception as exc:
        log.warning("section_mapper.detector_vision.llm_failed", error=str(exc))
        return None

    schema = _materialise(response)
    if schema is None:
        log.info("section_mapper.detector_vision.empty_or_malformed_response")
        return None

    if isinstance(response, dict):
        _save_cached(cache_dir, key, response)

    log.info(
        "section_mapper.detector_vision.detected",
        schema=schema.name,
        columns=len(schema.columns),
    )
    return schema


__all__ = [
    "detect_schema_from_table_async",
]
