"""Empty-table filler — populates docx tables that the template ships blank.

Industrial templates commonly leave tables intentionally empty for the
caller to fill: a *Histórico* table (``Rev. | Data | Alteração``), an
*Atividades* table (``Atividades | Responsabilidade | Responsabilidade``),
etc. The Wave D renderer ignored these; this module addresses them.

Strategy: header-driven matching.

1. For every table in the doc, read the first row (header).
2. Build a normalized header signature ``["REV", "DATA", "ALTERACAO"]``.
3. Caller passes a :class:`TableSpec` with the same header keys plus a
   ``rows`` list of dicts.
4. Filler matches by normalized header set, appends one row per dict
   into the existing table (keeping the header row + any prior rows
   intact).

Header normalization is the same routine used in :mod:`parser`: uppercase
+ drop accents + collapse whitespace.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def _normalize(text: str) -> str:
    nkfd = unicodedata.normalize("NFKD", text)
    no_accent = "".join(c for c in nkfd if not unicodedata.combining(c))
    return re.sub(r"[^A-Z0-9 ]+", " ", no_accent.upper()).strip()


@dataclass(frozen=True)
class TableSpec:
    """Caller-supplied data for a single table.

    Attributes:
        headers: list of header strings as they should appear (e.g.
            ``["Rev.", "Data", "Alteração"]``). Order matters.
        rows: list of row dicts keyed by header (any of the variants is
            accepted; matching is normalized).
    """

    headers: list[str]
    rows: list[dict[str, str]]


def _row_is_empty(row) -> bool:  # type: ignore[no-untyped-def]
    return all(not cell.text.strip() for cell in row.cells)


def fill_tables(
    template_path: Path,
    output_path: Path,
    specs: list[TableSpec],
) -> int:
    """Open ``template_path``, fill tables that match a spec by header set,
    save to ``output_path``. Returns the number of tables filled.

    A table matches a spec when its first row contains the same set of
    normalized header strings (order-insensitive). Multiple specs can
    share headers; tables are matched in document order.
    """
    from docx import Document

    doc = Document(str(output_path) if output_path.exists() else str(template_path))
    if not output_path.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)

    spec_queue = list(specs)
    filled = 0

    for table in doc.tables:
        if not table.rows or not spec_queue:
            continue
        header_row = table.rows[0]
        header_set = {_normalize(c.text) for c in header_row.cells if c.text.strip()}
        if not header_set:
            continue

        match_idx = None
        for i, sp in enumerate(spec_queue):
            spec_set = {_normalize(h) for h in sp.headers}
            if spec_set <= header_set:
                match_idx = i
                break
        if match_idx is None:
            continue

        spec = spec_queue.pop(match_idx)

        # Compute the header order of the actual table so cells go to the
        # right columns regardless of spec header ordering.
        actual_header_order = [_normalize(c.text) for c in header_row.cells]

        # First, fill any empty rows already in the table (templates often
        # ship N blank rows under the header).
        rows_to_fill = [r for r in table.rows[1:] if _row_is_empty(r)]
        spec_iter = iter(spec.rows)

        for r in rows_to_fill:
            try:
                row_dict = next(spec_iter)
            except StopIteration:
                break
            normalized = {_normalize(k): v for k, v in row_dict.items()}
            for cell, header_norm in zip(r.cells, actual_header_order, strict=False):
                cell.text = normalized.get(header_norm, "")

        # If the spec has more rows than empty rows in the table, append
        # new rows.
        for row_dict in spec_iter:
            new_row = table.add_row()
            normalized = {_normalize(k): v for k, v in row_dict.items()}
            for cell, header_norm in zip(new_row.cells, actual_header_order, strict=False):
                cell.text = normalized.get(header_norm, "")

        filled += 1

    doc.save(str(output_path))
    return filled
