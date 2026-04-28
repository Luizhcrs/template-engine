"""Unit tests for engine.section_mapper.record_extractor."""

from __future__ import annotations

from typing import Any

import pytest

from engine.section_mapper.record_extractor import (
    Record,
    extract_records,
    schema_to_json_schema,
)
from engine.section_mapper.schemas.builtins import (
    CONTACT_LIST_SCHEMA,
    PARTICIPANT_TABLE_SCHEMA,
)
from engine.section_mapper.schemas.types import ColumnSpec, ColumnType, TableSchema


class _MockLLM:
    """Returns a canned response and captures the call args."""

    def __init__(self, response: dict) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def generate_structured(self, prompt: str, schema: dict) -> dict:
        self.calls.append({"prompt": prompt, "schema": schema})
        return self.response


# --- schema_to_json_schema ---------------------------------------------------


def test_schema_to_json_schema_emits_phone_pattern() -> None:
    js = schema_to_json_schema(CONTACT_LIST_SCHEMA)
    item_props = js["properties"]["records"]["items"]["properties"]
    assert "Telefone" in item_props
    assert "pattern" in item_props["Telefone"]


def test_schema_to_json_schema_marks_required_columns() -> None:
    js = schema_to_json_schema(CONTACT_LIST_SCHEMA)
    required = js["properties"]["records"]["items"]["required"]
    assert "Nº" in required
    assert "Nome" in required


def test_schema_to_json_schema_uses_email_format_for_email_columns() -> None:
    js = schema_to_json_schema(CONTACT_LIST_SCHEMA)
    item_props = js["properties"]["records"]["items"]["properties"]
    assert item_props["e-mail"].get("format") == "email"


# --- extract_records ---------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_records_returns_typed_records() -> None:
    """Happy path: LLM returns three contacts; extractor parses them
    into :class:`Record` instances keyed by column name."""
    llm = _MockLLM(
        response={
            "records": [
                {
                    "Nº": 1,
                    "Nome": "Maria Lopes",
                    "Telefone": "(96) 3213-1010",
                    "e-mail": "diplan@unifap.br",
                },
                {
                    "Nº": 2,
                    "Nome": "João Pedro",
                    "Telefone": "(96) 3213-1020",
                    "e-mail": "dimat@unifap.br",
                },
            ]
        }
    )

    records = await extract_records(
        source_text="Maria Lopes ... João Pedro ...",
        schema=CONTACT_LIST_SCHEMA,
        llm=llm,
    )

    assert len(records) == 2
    assert records[0]["Nome"] == "Maria Lopes"
    assert records[0]["Telefone"] == "(96) 3213-1010"
    assert records[1]["e-mail"] == "dimat@unifap.br"


@pytest.mark.asyncio
async def test_extract_records_drops_records_missing_required_columns() -> None:
    """A record without a required field is rejected silently — we do
    not want partial rows landing in the output."""
    llm = _MockLLM(
        response={
            "records": [
                {"Nº": 1, "Nome": "Maria", "Telefone": "(96) 3213-1010"},
                {"Nome": "no number"},  # missing required Nº
                {"Nº": 3, "Telefone": "x"},  # missing required Nome
            ]
        }
    )

    records = await extract_records(
        source_text="anything",
        schema=CONTACT_LIST_SCHEMA,
        llm=llm,
    )

    assert len(records) == 1
    assert records[0]["Nome"] == "Maria"


@pytest.mark.asyncio
async def test_extract_records_handles_llm_failure() -> None:
    class _ExplodingLLM:
        async def generate_structured(self, *args: Any, **kwargs: Any) -> dict:
            raise RuntimeError("upstream timeout")

    records = await extract_records(
        source_text="anything",
        schema=CONTACT_LIST_SCHEMA,
        llm=_ExplodingLLM(),
    )
    assert records == []


@pytest.mark.asyncio
async def test_extract_records_handles_malformed_response() -> None:
    """LLM returns a top-level non-dict (or wrong shape) — extractor
    must return [] without crashing."""
    llm = _MockLLM(response={"oops": "no records key here"})

    records = await extract_records(
        source_text="anything",
        schema=CONTACT_LIST_SCHEMA,
        llm=llm,
    )
    assert records == []


@pytest.mark.asyncio
async def test_extract_records_passes_schema_payload_to_llm() -> None:
    """The LLM call must include the JSON Schema derived from the
    TableSchema so the model can be coerced into the right output
    shape."""
    llm = _MockLLM(response={"records": []})

    await extract_records(
        source_text="x",
        schema=PARTICIPANT_TABLE_SCHEMA,
        llm=llm,
    )

    assert len(llm.calls) == 1
    schema_arg = llm.calls[0]["schema"]
    item_props = schema_arg["properties"]["records"]["items"]["properties"]
    assert set(item_props.keys()) == {"Nome", "Setor", "Função"}


@pytest.mark.asyncio
async def test_extract_records_record_dict_has_all_schema_columns() -> None:
    """Even when the LLM omits an optional column, the resulting
    Record carries every schema column key (with None for missing
    values) so downstream code can address columns uniformly."""
    schema = TableSchema(
        name="t",
        columns=[
            ColumnSpec(name="A", type=ColumnType.NAME, required=True),
            ColumnSpec(name="B", type=ColumnType.FREE),
        ],
    )
    llm = _MockLLM(response={"records": [{"A": "alpha"}]})

    records = await extract_records(source_text="x", schema=schema, llm=llm)
    assert records == [Record({"A": "alpha", "B": None})]
