"""Builtin :class:`TableSchema` instances covering the table types
that show up repeatedly across BR-PT POP templates.

Adding a new schema is a one-tuple change: list the columns in the
order they appear in the template's row 0 and pick the right
:class:`ColumnType` for each.
"""

from __future__ import annotations

from engine.section_mapper.schemas.types import ColumnSpec, ColumnType, TableSchema

CONTACT_LIST_SCHEMA = TableSchema(
    name="contact_list",
    columns=[
        ColumnSpec(name="Nº", type=ColumnType.NUMBER, required=True),
        ColumnSpec(name="Nome", type=ColumnType.NAME, required=True),
        ColumnSpec(name="Telefone", type=ColumnType.PHONE),
        ColumnSpec(name="e-mail", type=ColumnType.EMAIL),
    ],
)

REVISION_TABLE_SCHEMA = TableSchema(
    name="revision_table",
    columns=[
        ColumnSpec(name="Versão", type=ColumnType.VERSION, required=True),
        ColumnSpec(name="Data", type=ColumnType.DATE, required=True),
        ColumnSpec(name="Descrição das mudanças", type=ColumnType.FREE),
        ColumnSpec(name="Requisitado por:", type=ColumnType.NAME),
    ],
)

PARTICIPANT_TABLE_SCHEMA = TableSchema(
    name="participant_table",
    columns=[
        ColumnSpec(name="Nome", type=ColumnType.NAME, required=True),
        ColumnSpec(name="Setor", type=ColumnType.SECTOR),
        ColumnSpec(name="Função", type=ColumnType.ROLE),
    ],
)

SIGNATURE_BOX_SCHEMA = TableSchema(
    name="signature_box",
    columns=[
        ColumnSpec(name="Atividade", type=ColumnType.FREE, required=True),
        ColumnSpec(name="Data", type=ColumnType.DATE),
        ColumnSpec(name="Nome", type=ColumnType.NAME),
        ColumnSpec(name="Função", type=ColumnType.ROLE),
    ],
)


BUILTIN_SCHEMAS: list[TableSchema] = [
    CONTACT_LIST_SCHEMA,
    REVISION_TABLE_SCHEMA,
    PARTICIPANT_TABLE_SCHEMA,
    SIGNATURE_BOX_SCHEMA,
]


__all__ = [
    "BUILTIN_SCHEMAS",
    "CONTACT_LIST_SCHEMA",
    "PARTICIPANT_TABLE_SCHEMA",
    "REVISION_TABLE_SCHEMA",
    "SIGNATURE_BOX_SCHEMA",
]
