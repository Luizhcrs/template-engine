"""Schema-driven table fill — typed schemas for common BR-PT POP
tables. Pipeline detects which template tables match a known schema,
extracts typed records from the source, aligns records to rows, and
writes deterministic per-cell fills.

This package replaces the flat slot pipeline for table-shaped content
with a layered approach: schema detection (heuristic + LLM), record
extraction (LLM, JSON-Schema validated), alignment + fill (pure code).
"""

from __future__ import annotations

from engine.section_mapper.schemas.types import (
    ColumnSpec,
    ColumnType,
    TableSchema,
)

__all__ = [
    "ColumnSpec",
    "ColumnType",
    "TableSchema",
]
