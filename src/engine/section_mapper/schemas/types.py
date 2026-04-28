"""Schema types — :class:`ColumnType` enum, :class:`ColumnSpec`, and
:class:`TableSchema`. These are the wire-format the schema-driven
table fill pipeline talks in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ColumnType(str, Enum):
    """Semantic type for a column. Used to validate fills before
    writing them and to constrain the LLM-driven record extraction.

    Values are stable strings so they can flow through JSON Schema and
    structlog without translation.
    """

    PHONE = "phone"
    EMAIL = "email"
    DATE = "date"
    NAME = "name"
    SECTOR = "sector"
    ROLE = "role"
    VERSION = "version"
    NUMBER = "number"
    FREE = "free"


@dataclass(frozen=True)
class ColumnSpec:
    """One column of a :class:`TableSchema`.

    Attributes:
        name: human-readable header text used to match this column to
            a docx table's row 0.
        type: semantic :class:`ColumnType`. Validators in
            :mod:`engine.section_mapper.typed_fill` check fills
            against this type before writing.
        required: when True, a record missing this field is rejected.
    """

    name: str
    type: ColumnType
    required: bool = False


@dataclass(frozen=True)
class TableSchema:
    """A named, ordered list of :class:`ColumnSpec`.

    Schemas are matched against template table headers by
    :func:`engine.section_mapper.schemas.detector.detect_table_schema`.
    """

    name: str
    columns: list[ColumnSpec] = field(default_factory=list)

    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]
