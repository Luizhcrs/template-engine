"""Tests for engine.semantic_diff."""

from __future__ import annotations

import pytest

from engine.semantic_diff import (
    Discrepancy,
    diff_texts,
    filter_by_severity,
)


class _StubLLM:
    name = "stub"
    model = "stub-1"

    def __init__(self, response: dict) -> None:
        self.response = response
        self.last_prompt: str | None = None
        self.call_count = 0

    async def generate_structured(self, prompt: str, json_schema: dict) -> dict:
        self.last_prompt = prompt
        self.call_count += 1
        return self.response


# ===== diff_texts =====


@pytest.mark.asyncio
async def test_diff_texts_returns_discrepancies_from_llm():
    stub = _StubLLM(
        response={
            "discrepancies": [
                {
                    "type": "missing_in_output",
                    "field_or_excerpt": "CNPJ",
                    "source_value": "12.345.678/0001-99",
                    "output_value": None,
                    "severity": "critical",
                    "note": "CNPJ present in source missing from output",
                }
            ]
        }
    )

    out = await diff_texts(
        "Cliente Acme CNPJ 12.345.678/0001-99",
        "Cliente: Acme",
        llm=stub,  # type: ignore[arg-type]
    )

    assert len(out) == 1
    assert out[0].type == "missing_in_output"
    assert out[0].field_or_excerpt == "CNPJ"
    assert out[0].source_value == "12.345.678/0001-99"
    assert out[0].output_value is None
    assert out[0].severity == "critical"


@pytest.mark.asyncio
async def test_diff_texts_returns_empty_when_no_discrepancies():
    stub = _StubLLM(response={"discrepancies": []})
    out = await diff_texts("doc identico", "doc identico", llm=stub)  # type: ignore[arg-type]
    assert out == []


@pytest.mark.asyncio
async def test_diff_texts_handles_llm_failure_emits_warning():
    """Provider error must surface as a synthetic warning discrepancy, not as
    an empty diff. Wave K #8 — silent passes on transient failures hide bugs.
    """

    class _BoomLLM:
        name = "boom"
        model = "boom-1"

        async def generate_structured(self, prompt: str, json_schema: dict) -> dict:
            raise RuntimeError("network down")

    out = await diff_texts("a", "b", llm=_BoomLLM())  # type: ignore[arg-type]
    assert len(out) == 1
    assert out[0].field_or_excerpt == "provider_error"
    assert out[0].severity == "warning"


@pytest.mark.asyncio
async def test_diff_texts_skips_malformed_entries_without_crashing():
    stub = _StubLLM(
        response={
            "discrepancies": [
                {
                    "type": "missing_in_output",
                    "field_or_excerpt": "OK",
                    "source_value": "x",
                    "output_value": None,
                    "severity": "warning",
                    "note": "valid",
                },
                {"type": "missing_in_output"},  # malformed — missing keys
                "garbage_string",  # not a dict
            ]
        }
    )

    out = await diff_texts("a", "b", llm=stub)  # type: ignore[arg-type]
    assert len(out) == 1
    assert out[0].field_or_excerpt == "OK"


@pytest.mark.asyncio
async def test_diff_texts_handles_non_dict_response():
    """Provider that returns a list or string instead of dict — must not crash."""

    class _WeirdLLM:
        name = "weird"
        model = "w-1"

        async def generate_structured(self, prompt: str, json_schema: dict) -> dict:
            return []  # type: ignore[return-value] - intentionally wrong

    out = await diff_texts("a", "b", llm=_WeirdLLM())  # type: ignore[arg-type]
    assert out == []


# ===== prompt construction =====


@pytest.mark.asyncio
async def test_diff_texts_truncates_long_input():
    stub = _StubLLM(response={"discrepancies": []})
    huge_source = "S" * 50000
    huge_output = "O" * 50000
    await diff_texts(huge_source, huge_output, llm=stub, max_doc_chars=200)  # type: ignore[arg-type]

    assert stub.last_prompt is not None
    # Prompt shouldn't blow up — bounded relative to max_doc_chars * 2 + constant overhead
    assert len(stub.last_prompt) < 5000


@pytest.mark.asyncio
async def test_diff_texts_includes_field_focus_when_schemas_provided():
    from engine.schema_inference import FieldSchema

    stub = _StubLLM(response={"discrepancies": []})
    schemas = [
        FieldSchema(name="CPF", placeholder_token="[CPF]", kind="bracket"),
        FieldSchema(name="NOME", placeholder_token="[NOME]", kind="bracket"),
    ]

    await diff_texts("a", "b", llm=stub, schemas=schemas)  # type: ignore[arg-type]

    assert stub.last_prompt is not None
    assert "CPF" in stub.last_prompt
    assert "NOME" in stub.last_prompt
    assert "Focus the comparison" in stub.last_prompt


@pytest.mark.asyncio
async def test_diff_texts_omits_focus_section_when_no_schemas():
    stub = _StubLLM(response={"discrepancies": []})
    await diff_texts("a", "b", llm=stub)  # type: ignore[arg-type]

    assert stub.last_prompt is not None
    assert "Focus the comparison" not in stub.last_prompt


# ===== filter_by_severity =====


def test_filter_by_severity_keeps_critical_only():
    items = [
        Discrepancy(
            type="missing_in_output",
            field_or_excerpt="CPF",
            source_value="x",
            output_value=None,
            severity="critical",
            note="lost",
        ),
        Discrepancy(
            type="value_mismatch",
            field_or_excerpt="DATA",
            source_value="2026",
            output_value="2027",
            severity="warning",
            note="off",
        ),
        Discrepancy(
            type="extra_in_output",
            field_or_excerpt="footer",
            source_value=None,
            output_value="lorem",
            severity="info",
            note="cosmetic",
        ),
    ]

    out = filter_by_severity(items, min_severity="critical")
    assert len(out) == 1
    assert out[0].severity == "critical"


def test_filter_by_severity_warning_threshold():
    items = [
        Discrepancy("missing_in_output", "x", "v", None, "info", ""),
        Discrepancy("missing_in_output", "y", "v", None, "warning", ""),
        Discrepancy("missing_in_output", "z", "v", None, "critical", ""),
    ]
    out = filter_by_severity(items, min_severity="warning")
    assert len(out) == 2
    assert {d.severity for d in out} == {"warning", "critical"}


def test_filter_by_severity_default_is_warning():
    items = [Discrepancy("missing_in_output", "x", "v", None, "info", "")]
    out = filter_by_severity(items)
    assert out == []


def test_discrepancy_is_frozen():
    d = Discrepancy("missing_in_output", "x", "v", None, "info", "")
    with pytest.raises((AttributeError, Exception)):
        d.severity = "critical"  # type: ignore[misc]
