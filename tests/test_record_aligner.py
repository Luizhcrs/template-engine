"""Unit tests for engine.section_mapper.record_aligner."""

from __future__ import annotations

from engine.section_mapper.record_aligner import (
    TableInventory,
    TableRow,
    align_records_to_rows,
)
from engine.section_mapper.record_extractor import Record
from engine.section_mapper.schemas.builtins import (
    CONTACT_LIST_SCHEMA,
    PARTICIPANT_TABLE_SCHEMA,
)


def _row(*, vmerge_with_above: bool = False, fillable: tuple[bool, ...] = ()) -> TableRow:
    return TableRow(
        vmerge_with_above=vmerge_with_above,
        cell_fillable=list(fillable),
    )


def test_aligns_records_to_rows_one_to_one() -> None:
    """Three records, three fillable rows. The aligner walks rows in
    order and assigns one record per row, mapping column-by-column."""
    inventory = TableInventory(
        schema=PARTICIPANT_TABLE_SCHEMA,
        rows=[
            _row(fillable=(False, False, False)),  # header row
            _row(fillable=(True, True, True)),
            _row(fillable=(True, True, True)),
            _row(fillable=(True, True, True)),
        ],
    )
    records = [
        Record({"Nome": "Maria Lopes", "Setor": "DIPLAN", "Função": "Chefe"}),
        Record({"Nome": "João Pedro", "Setor": "DIMAT", "Função": "Diretor"}),
        Record({"Nome": "Beatriz Rocha", "Setor": "Procuradoria", "Função": "Procuradora"}),
    ]

    fills = align_records_to_rows(inventory, records)

    assert fills[(1, 0)] == "Maria Lopes"
    assert fills[(1, 1)] == "DIPLAN"
    assert fills[(1, 2)] == "Chefe"
    assert fills[(2, 0)] == "João Pedro"
    assert fills[(3, 0)] == "Beatriz Rocha"


def test_aligns_handles_titular_substituto_pairs() -> None:
    """UNIFAP LISTA DE CONTATOS pattern: ``Nº=1`` spans two rows
    (titular + substituto vMerge group), ``Nº=2`` spans two rows. The
    aligner must put the titular in row 0 of the pair and the
    substituto in the merged-continuation row, NOT increment Nº."""
    inventory = TableInventory(
        schema=CONTACT_LIST_SCHEMA,
        rows=[
            _row(fillable=(False, False, False, False)),  # header
            _row(fillable=(False, False, True, True)),  # Nº=1 titular (Nº prefilled)
            _row(vmerge_with_above=True, fillable=(False, True, True, True)),  # Nº=1 substituto
            _row(fillable=(False, True, True, True)),  # Nº=2 titular
            _row(vmerge_with_above=True, fillable=(False, True, True, True)),  # Nº=2 substituto
        ],
    )
    records = [
        Record(
            {
                "Nº": 1,
                "Nome": "Maria Lopes",
                "Telefone": "(96) 3213-1010",
                "e-mail": "maria@unifap.br",
            }
        ),
        Record(
            {
                "Nº": 1,  # substituto shares the titular's Nº
                "Nome": "Substituta da Maria",
                "Telefone": "(96) 3213-1011",
                "e-mail": "subst1@unifap.br",
            }
        ),
        Record(
            {
                "Nº": 2,
                "Nome": "João Pedro",
                "Telefone": "(96) 3213-1020",
                "e-mail": "joao@unifap.br",
            }
        ),
        Record(
            {
                "Nº": 2,
                "Nome": "Substituto do João",
                "Telefone": "(96) 3213-1021",
                "e-mail": "subst2@unifap.br",
            }
        ),
    ]

    fills = align_records_to_rows(inventory, records)

    # Row 1 (titular Nº=1)
    assert fills[(1, 2)] == "(96) 3213-1010"
    assert fills[(1, 3)] == "maria@unifap.br"
    # Row 2 (substituto continuation)
    assert fills[(2, 1)] == "Substituta da Maria"
    assert fills[(2, 2)] == "(96) 3213-1011"
    # Row 3 (titular Nº=2)
    assert fills[(3, 1)] == "João Pedro"
    # Row 4 (substituto continuation)
    assert fills[(4, 1)] == "Substituto do João"


def test_aligns_drops_extra_records_when_more_records_than_rows() -> None:
    inventory = TableInventory(
        schema=PARTICIPANT_TABLE_SCHEMA,
        rows=[
            _row(fillable=(False, False, False)),
            _row(fillable=(True, True, True)),
        ],
    )
    records = [
        Record({"Nome": "A", "Setor": "X", "Função": "x"}),
        Record({"Nome": "B", "Setor": "Y", "Função": "y"}),  # extra
        Record({"Nome": "C", "Setor": "Z", "Função": "z"}),  # extra
    ]

    fills = align_records_to_rows(inventory, records)
    assert fills == {(1, 0): "A", (1, 1): "X", (1, 2): "x"}


def test_aligns_skips_non_fillable_cells() -> None:
    """Cells whose ``cell_fillable`` flag is False (template default
    text the slot profiler classified as ``data``) are not written
    even if the record carries a value for that column."""
    inventory = TableInventory(
        schema=PARTICIPANT_TABLE_SCHEMA,
        rows=[
            _row(fillable=(False, False, False)),
            _row(fillable=(True, False, True)),  # Setor not fillable
        ],
    )
    records = [Record({"Nome": "Maria", "Setor": "DIPLAN", "Função": "Chefe"})]

    fills = align_records_to_rows(inventory, records)
    assert (1, 0) in fills
    assert (1, 2) in fills
    assert (1, 1) not in fills  # Setor was not fillable


def test_aligns_returns_empty_when_no_fillable_rows() -> None:
    """Header-only table with no body rows: nothing to fill."""
    inventory = TableInventory(
        schema=PARTICIPANT_TABLE_SCHEMA,
        rows=[_row(fillable=(False, False, False))],
    )
    records = [Record({"Nome": "X", "Setor": "Y", "Função": "Z"})]

    assert align_records_to_rows(inventory, records) == {}
