"""Deterministic record-to-row alignment.

Given an :class:`TableInventory` (the structural shape of a docx
table) and a list of :class:`Record`, produce a dict mapping
``(row_index, col_index)`` to the cell text that should be written
there.

This stage is pure code — no LLM. The schema-driven pipeline keeps
LLM calls focused on extraction; the cost of a wrong alignment
cascades, so we make alignment auditable and testable instead of
asking the LLM to do it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from engine.section_mapper.record_extractor import Record
    from engine.section_mapper.schemas.types import TableSchema


log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class TableRow:
    """One row of an :class:`TableInventory`.

    Attributes:
        vmerge_with_above: True for rows whose first cell is part of
            a vertical merge that started in the row above
            (``<w:vMerge/>`` with no ``w:val="restart"``). Such rows
            are treated as continuations of the previous logical row
            and DO NOT consume a new record from the queue.
        cell_fillable: per-column flag indicating whether each cell
            position is fillable (matches the slot profiler's
            ``is_fillable`` flag for the corresponding tc).
    """

    vmerge_with_above: bool = False
    cell_fillable: list[bool] = field(default_factory=list)


@dataclass(frozen=True)
class TableInventory:
    """Structural shape of one docx table, sufficient to drive
    record-row alignment without re-parsing the docx.
    """

    schema: TableSchema
    rows: list[TableRow] = field(default_factory=list)


def align_records_to_rows(
    inventory: TableInventory,
    records: list[Record],
) -> dict[tuple[int, int], str]:
    """Walk *inventory.rows* in document order. For each row that
    carries at least one fillable cell, consume the next available
    record and emit ``(row, col) -> value`` for each fillable cell
    that the record carries a value for.

    Continuation rows (``vmerge_with_above=True``) ARE assigned a new
    record — they're typically the substituto half of a
    titular/substituto pair in the LISTA DE CONTATOS pattern, and the
    source's record list orders titulars and substitutos as adjacent
    entries.
    """
    fills: dict[tuple[int, int], str] = {}
    column_names = inventory.schema.column_names()
    record_iter = iter(records)

    for ri, row in enumerate(inventory.rows):
        if not any(row.cell_fillable):
            continue
        try:
            record = next(record_iter)
        except StopIteration:
            log.info(
                "section_mapper.record_aligner.records_exhausted_at_row",
                row=ri,
                rows_remaining=len(inventory.rows) - ri,
            )
            break
        for ci, fillable in enumerate(row.cell_fillable):
            if not fillable:
                continue
            if ci >= len(column_names):
                continue
            value = record.get(column_names[ci])
            if value is None or value == "":
                continue
            fills[(ri, ci)] = str(value)

    log.info(
        "section_mapper.record_aligner.aligned",
        schema=inventory.schema.name,
        rows=len(inventory.rows),
        records_in=len(records),
        cells_out=len(fills),
    )
    return fills


__all__ = [
    "TableInventory",
    "TableRow",
    "align_records_to_rows",
]
