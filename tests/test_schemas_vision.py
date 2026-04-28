"""Unit tests for engine.section_mapper.schemas.detector_vision.

The vision detector runs ONLY when no builtin schema matches a
template's table. It asks the LLM to produce a TableSchema given the
header row + a sample body row. Result is cached on disk so the same
template doesn't re-pay the LLM call.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from engine.section_mapper.schemas.detector_vision import (
    detect_schema_from_table_async,
)
from engine.section_mapper.schemas.types import ColumnType

if TYPE_CHECKING:
    from pathlib import Path


class _MockLLM:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def generate_structured(self, prompt: str, schema: dict) -> dict:
        self.calls.append({"prompt": prompt, "schema": schema})
        return self.response


@pytest.mark.asyncio
async def test_detector_vision_returns_table_schema_from_llm_response() -> None:
    """Happy path: LLM returns a list of column specs; detector
    materialises a TableSchema."""
    llm = _MockLLM(
        response={
            "schema_name": "vendor_table",
            "columns": [
                {"name": "Item", "type": "number", "required": True},
                {"name": "Descrição", "type": "free", "required": True},
                {"name": "Qtde", "type": "number", "required": False},
            ],
        }
    )

    schema = await detect_schema_from_table_async(
        headers=["Item", "Descrição", "Qtde"],
        sample_row_texts=["1", "Caneta esferográfica", "10"],
        llm=llm,
    )

    assert schema is not None
    assert schema.name == "vendor_table"
    assert schema.column_names() == ["Item", "Descrição", "Qtde"]
    types_by_name = {c.name: c.type for c in schema.columns}
    assert types_by_name["Item"] == ColumnType.NUMBER
    assert types_by_name["Qtde"] == ColumnType.NUMBER
    assert types_by_name["Descrição"] == ColumnType.FREE


@pytest.mark.asyncio
async def test_detector_vision_passes_headers_and_sample_to_llm() -> None:
    """The prompt sent to the LLM must include both the header row
    and the first-body-row sample so the model can disambiguate
    columns whose names alone are ambiguous (``Atividade`` could mean
    a verb or a label)."""
    llm = _MockLLM(response={"schema_name": "x", "columns": []})

    await detect_schema_from_table_async(
        headers=["Atividade", "Data"],
        sample_row_texts=["Versão inicial", "15/03/2023"],
        llm=llm,
    )

    assert len(llm.calls) == 1
    prompt = llm.calls[0]["prompt"]
    assert "Atividade" in prompt
    assert "Data" in prompt
    assert "Versão inicial" in prompt
    assert "15/03/2023" in prompt


@pytest.mark.asyncio
async def test_detector_vision_returns_none_on_empty_columns() -> None:
    """If the LLM returns no columns (the table genuinely has no
    structure), the detector returns None so the caller falls through
    to the legacy slot pipeline rather than producing a 0-column
    schema that crashes downstream."""
    llm = _MockLLM(response={"schema_name": "x", "columns": []})

    schema = await detect_schema_from_table_async(
        headers=["foo"],
        sample_row_texts=["bar"],
        llm=llm,
    )
    assert schema is None


@pytest.mark.asyncio
async def test_detector_vision_handles_llm_exception() -> None:
    class _ExplodingLLM:
        async def generate_structured(self, *args: Any, **kwargs: Any) -> dict:
            raise RuntimeError("upstream timeout")

    schema = await detect_schema_from_table_async(
        headers=["A"],
        sample_row_texts=["x"],
        llm=_ExplodingLLM(),
    )
    assert schema is None


@pytest.mark.asyncio
async def test_detector_vision_handles_malformed_response() -> None:
    """LLM returns garbage shape — detector returns None gracefully."""
    llm = _MockLLM(response={"oops": "nope"})

    schema = await detect_schema_from_table_async(
        headers=["A"],
        sample_row_texts=["x"],
        llm=llm,
    )
    assert schema is None


@pytest.mark.asyncio
async def test_detector_vision_caches_result_to_disk(tmp_path: Path) -> None:
    """Same headers + sample produce one LLM call; second call returns
    the cached schema without consulting the LLM. Cache is sha256-keyed
    on the joined headers + sample so a template renamed but otherwise
    identical hits the same entry."""
    llm = _MockLLM(
        response={
            "schema_name": "cached",
            "columns": [{"name": "A", "type": "free", "required": True}],
        }
    )

    s1 = await detect_schema_from_table_async(
        headers=["A"],
        sample_row_texts=["v1"],
        llm=llm,
        cache_dir=tmp_path,
    )
    s2 = await detect_schema_from_table_async(
        headers=["A"],
        sample_row_texts=["v1"],
        llm=llm,
        cache_dir=tmp_path,
    )

    assert s1 is not None
    assert s2 is not None
    assert s1.name == s2.name == "cached"
    assert len(llm.calls) == 1  # second call hit the cache


@pytest.mark.asyncio
async def test_detector_vision_cache_misses_when_headers_differ(tmp_path: Path) -> None:
    """Different headers must NOT collide in the cache — same sample
    text but different header set should re-issue the LLM call."""
    llm = _MockLLM(
        response={
            "schema_name": "x",
            "columns": [{"name": "A", "type": "free", "required": True}],
        }
    )

    await detect_schema_from_table_async(
        headers=["A"],
        sample_row_texts=["v1"],
        llm=llm,
        cache_dir=tmp_path,
    )
    await detect_schema_from_table_async(
        headers=["B"],
        sample_row_texts=["v1"],
        llm=llm,
        cache_dir=tmp_path,
    )

    assert len(llm.calls) == 2
