"""Unit tests for engine.section_mapper.schemas."""

from __future__ import annotations

from engine.section_mapper.schemas.types import (
    ColumnSpec,
    ColumnType,
    TableSchema,
)


def test_column_type_has_all_expected_kinds() -> None:
    """The schema layer needs typed columns to validate fills before
    writing them to disk."""
    expected = {
        "phone",
        "email",
        "date",
        "name",
        "sector",
        "role",
        "version",
        "number",
        "free",
    }
    assert {ct.value for ct in ColumnType} == expected


def test_column_spec_carries_name_type_and_required_flag() -> None:
    spec = ColumnSpec(name="Telefone", type=ColumnType.PHONE, required=True)
    assert spec.name == "Telefone"
    assert spec.type == ColumnType.PHONE
    assert spec.required is True


def test_column_spec_required_defaults_to_false() -> None:
    spec = ColumnSpec(name="Observação", type=ColumnType.FREE)
    assert spec.required is False


def test_table_schema_holds_name_and_ordered_columns() -> None:
    schema = TableSchema(
        name="contact_list",
        columns=[
            ColumnSpec(name="Nº", type=ColumnType.NUMBER, required=True),
            ColumnSpec(name="Nome", type=ColumnType.NAME, required=True),
            ColumnSpec(name="Telefone", type=ColumnType.PHONE),
            ColumnSpec(name="e-mail", type=ColumnType.EMAIL),
        ],
    )
    assert schema.name == "contact_list"
    assert [c.name for c in schema.columns] == ["Nº", "Nome", "Telefone", "e-mail"]
    assert schema.column_names() == ["Nº", "Nome", "Telefone", "e-mail"]


# --- builtin schemas ---------------------------------------------------------


def test_contact_list_schema_has_expected_columns() -> None:
    """The CONTACT_LIST schema models the UNIFAP LISTA DE CONTATOS
    layout: Nº | Nome | Telefone | e-mail."""
    from engine.section_mapper.schemas.builtins import CONTACT_LIST_SCHEMA

    assert CONTACT_LIST_SCHEMA.name == "contact_list"
    assert CONTACT_LIST_SCHEMA.column_names() == ["Nº", "Nome", "Telefone", "e-mail"]
    types_by_name = {c.name: c.type for c in CONTACT_LIST_SCHEMA.columns}
    assert types_by_name["Nº"] == ColumnType.NUMBER
    assert types_by_name["Nome"] == ColumnType.NAME
    assert types_by_name["Telefone"] == ColumnType.PHONE
    assert types_by_name["e-mail"] == ColumnType.EMAIL


def test_revision_table_schema_has_expected_columns() -> None:
    from engine.section_mapper.schemas.builtins import REVISION_TABLE_SCHEMA

    assert REVISION_TABLE_SCHEMA.name == "revision_table"
    assert REVISION_TABLE_SCHEMA.column_names() == [
        "Versão",
        "Data",
        "Descrição das mudanças",
        "Requisitado por:",
    ]


def test_participant_table_schema_has_expected_columns() -> None:
    from engine.section_mapper.schemas.builtins import PARTICIPANT_TABLE_SCHEMA

    assert PARTICIPANT_TABLE_SCHEMA.name == "participant_table"
    assert PARTICIPANT_TABLE_SCHEMA.column_names() == ["Nome", "Setor", "Função"]


def test_signature_box_schema_has_expected_columns() -> None:
    from engine.section_mapper.schemas.builtins import SIGNATURE_BOX_SCHEMA

    assert SIGNATURE_BOX_SCHEMA.name == "signature_box"
    assert SIGNATURE_BOX_SCHEMA.column_names() == ["Atividade", "Data", "Nome", "Função"]


# --- detector ---------------------------------------------------------------


def test_detect_table_schema_matches_contact_list_headers() -> None:
    from engine.section_mapper.schemas.builtins import CONTACT_LIST_SCHEMA
    from engine.section_mapper.schemas.detector import detect_table_schema

    assert detect_table_schema(["Nº", "Nome", "Telefone", "e-mail"]) is CONTACT_LIST_SCHEMA


def test_detect_table_schema_matches_with_minor_variations() -> None:
    """Real templates spell ``e-mail`` as ``E-mail`` / ``Email``,
    ``Nº`` as ``N°`` / ``Num`` / ``#``. Detector tolerates lowercase
    + accent + punctuation drift."""
    from engine.section_mapper.schemas.builtins import CONTACT_LIST_SCHEMA
    from engine.section_mapper.schemas.detector import detect_table_schema

    assert detect_table_schema(["No", "nome", "telefone", "Email"]) is CONTACT_LIST_SCHEMA


def test_detect_table_schema_matches_revision_table() -> None:
    from engine.section_mapper.schemas.builtins import REVISION_TABLE_SCHEMA
    from engine.section_mapper.schemas.detector import detect_table_schema

    assert (
        detect_table_schema(["Versão", "Data", "Descrição das mudanças", "Requisitado por:"])
        is REVISION_TABLE_SCHEMA
    )


def test_detect_table_schema_matches_participant_table() -> None:
    from engine.section_mapper.schemas.builtins import PARTICIPANT_TABLE_SCHEMA
    from engine.section_mapper.schemas.detector import detect_table_schema

    assert detect_table_schema(["Nome", "Setor", "Função"]) is PARTICIPANT_TABLE_SCHEMA


def test_detect_table_schema_matches_signature_box() -> None:
    from engine.section_mapper.schemas.builtins import SIGNATURE_BOX_SCHEMA
    from engine.section_mapper.schemas.detector import detect_table_schema

    assert detect_table_schema(["Atividade", "Data", "Nome", "Função"]) is SIGNATURE_BOX_SCHEMA


def test_detect_table_schema_returns_none_for_unknown_headers() -> None:
    from engine.section_mapper.schemas.detector import detect_table_schema

    assert detect_table_schema(["Foo", "Bar", "Baz"]) is None


def test_detect_table_schema_returns_none_for_empty_headers() -> None:
    from engine.section_mapper.schemas.detector import detect_table_schema

    assert detect_table_schema([]) is None
    assert detect_table_schema(["", "", ""]) is None


def test_detect_table_schema_requires_column_count_match() -> None:
    """A 2-column table can't match a 4-column schema even if 2 names
    are similar."""
    from engine.section_mapper.schemas.detector import detect_table_schema

    assert detect_table_schema(["Nome", "Telefone"]) is None
