"""Tests for engine.schema_inference."""

from __future__ import annotations

from typing import Any

import pytest

from engine.schema_inference import (
    FieldSchema,
    detect_placeholders,
    enrich_with_llm,
)


class _StubLLM:
    """Stub LLMProvider that returns canned responses based on field name."""

    name = "stub"
    model = "stub-1"

    def __init__(self, responses: dict[str, dict]) -> None:
        self._responses = responses
        self.calls: list[str] = []

    async def generate_structured(self, prompt: str, json_schema: dict) -> dict:
        # crude name extraction from prompt
        for name, payload in self._responses.items():
            if f"name: {name}" in prompt.lower() or f"name: {name}" in prompt:
                self.calls.append(name)
                return payload
        # default fallback
        return {"field_type": "freetext", "format_hint": None, "required": True}


# ===== detect_placeholders — syntaxes =====


def test_detect_mustache_placeholder():
    text = "Codigo: {{CODIGO}}\nData: {{DATA}}"
    schemas = detect_placeholders(text)
    names = {s.name for s in schemas}
    assert names == {"CODIGO", "DATA"}
    for s in schemas:
        assert s.kind == "mustache"


def test_detect_bracket_placeholder():
    text = "Nome: [NOME]\nCPF: [CPF]"
    schemas = detect_placeholders(text)
    assert {s.name for s in schemas} == {"NOME", "CPF"}
    assert all(s.kind == "bracket" for s in schemas)


def test_detect_chevron_placeholder():
    text = "Cliente: <<CLIENTE>>"
    schemas = detect_placeholders(text)
    assert len(schemas) == 1
    assert schemas[0].name == "CLIENTE"
    assert schemas[0].kind == "chevron"


def test_detect_named_blank_placeholder():
    text = "Identificador: __DOC_ID__"
    schemas = detect_placeholders(text)
    assert len(schemas) == 1
    assert schemas[0].name == "DOC_ID"
    assert schemas[0].kind == "named_blank"


def test_detect_anonymous_blank_placeholder():
    text = "Linha 1: ___\nLinha 2: ______"
    schemas = detect_placeholders(text)
    assert len(schemas) == 2
    assert {s.name for s in schemas} == {"BLANK_1", "BLANK_2"}
    assert all(s.kind == "anon_blank" for s in schemas)


def test_detect_brace_placeholder_does_not_collide_with_mustache():
    """``{{X}}`` must not also match the inner ``{X}`` brace pattern."""
    text = "Field: {{NAME}}"
    schemas = detect_placeholders(text)
    assert len(schemas) == 1
    assert schemas[0].kind == "mustache"
    assert schemas[0].name == "NAME"


def test_detect_mixed_syntaxes_in_single_template():
    text = "Codigo: {{CODIGO}}\nNome: [NOME]\nData: ___\nCliente: <<CLIENTE>>"
    schemas = detect_placeholders(text)
    by_kind = {s.kind for s in schemas}
    assert by_kind == {"mustache", "bracket", "anon_blank", "chevron"}


def test_detect_dedupes_same_name_kind_combo():
    """Repeated ``{{CODIGO}}`` collapses to a single schema entry."""
    text = "Header {{CODIGO}}\nFooter {{CODIGO}}"
    schemas = detect_placeholders(text)
    assert len(schemas) == 1
    assert schemas[0].name == "CODIGO"


def test_detect_returns_empty_when_no_placeholders():
    text = "Plain text with no markers at all."
    assert detect_placeholders(text) == []


def test_detect_ignores_lowercase_names():
    """Convention: placeholder names are uppercase. Lowercase tokens not matched."""
    text = "Skip: {{lowercase}}\nKeep: {{REAL_FIELD}}"
    schemas = detect_placeholders(text)
    assert len(schemas) == 1
    assert schemas[0].name == "REAL_FIELD"


# ===== context capture =====


def test_context_before_and_after_captured():
    text = "Some preamble text. Codigo do laudo: {{CODIGO}} - referencia interna."
    schemas = detect_placeholders(text)
    assert len(schemas) == 1
    s = schemas[0]
    assert "Codigo do laudo" in s.context_before
    assert "referencia interna" in s.context_after


def test_context_truncated_to_80_chars_each_side():
    long_prefix = "x" * 200
    long_suffix = "y" * 200
    text = f"{long_prefix}{{{{FIELD}}}}{long_suffix}"
    schemas = detect_placeholders(text)
    s = schemas[0]
    assert len(s.context_before) <= 80
    assert len(s.context_after) <= 80


# ===== enrich_with_llm =====


@pytest.mark.asyncio
async def test_enrich_with_llm_populates_field_type():
    schemas = [
        FieldSchema(name="DATA", placeholder_token="{{DATA}}", kind="mustache"),
        FieldSchema(name="CODIGO", placeholder_token="{{CODIGO}}", kind="mustache"),
    ]
    stub = _StubLLM(
        responses={
            "DATA": {"field_type": "iso_date", "format_hint": "YYYY-MM-DD", "required": True},
            "CODIGO": {"field_type": "doc_code", "format_hint": "ABC-123", "required": True},
        }
    )
    enriched = await enrich_with_llm(schemas, stub)  # type: ignore[arg-type]
    by_name = {s.name: s for s in enriched}
    assert by_name["DATA"].field_type == "iso_date"
    assert by_name["DATA"].format_hint == "YYYY-MM-DD"
    assert by_name["CODIGO"].field_type == "doc_code"


@pytest.mark.asyncio
async def test_enrich_with_llm_keeps_unknown_on_failure():
    schemas = [FieldSchema(name="X", placeholder_token="{{X}}", kind="mustache")]

    class _BoomLLM:
        name = "boom"
        model = "boom-1"

        async def generate_structured(self, prompt: str, json_schema: dict) -> dict:
            raise RuntimeError("provider down")

    enriched = await enrich_with_llm(schemas, _BoomLLM())  # type: ignore[arg-type]
    assert len(enriched) == 1
    assert enriched[0].field_type == "unknown"  # unchanged


@pytest.mark.asyncio
async def test_enrich_with_llm_does_not_mutate_input():
    original = FieldSchema(name="X", placeholder_token="{{X}}", kind="mustache")
    schemas = [original]
    stub = _StubLLM(responses={"X": {"field_type": "doc_code", "format_hint": None, "required": False}})
    enriched = await enrich_with_llm(schemas, stub)  # type: ignore[arg-type]
    # frozen dataclass — identity must differ + original.field_type unchanged
    assert enriched[0] is not original
    assert original.field_type == "unknown"
    assert enriched[0].field_type == "doc_code"
    assert enriched[0].required is False


@pytest.mark.asyncio
async def test_enrich_with_llm_empty_input_returns_empty():
    stub = _StubLLM(responses={})
    out = await enrich_with_llm([], stub)  # type: ignore[arg-type]
    assert out == []


# ===== integration: detect → schema list shape =====


def test_full_template_detection_yields_expected_fields():
    template_text = (
        "LAUDO TECNICO\n"
        "Codigo: {{CODIGO}}\n"
        "Data de emissao: {{DATA}}\n"
        "Responsavel: [RESPONSAVEL]\n"
        "Assinatura: ___\n"
        "Identificador interno: __INTERNAL_ID__\n"
        "Cliente: <<CLIENTE>>\n"
    )
    schemas = detect_placeholders(template_text)
    names = {s.name for s in schemas}
    assert names == {
        "CODIGO",
        "DATA",
        "RESPONSAVEL",
        "BLANK_1",
        "INTERNAL_ID",
        "CLIENTE",
    }


def test_field_schema_is_frozen():
    """FieldSchema is immutable to prevent accidental mutation across pipeline."""
    s = FieldSchema(name="X", placeholder_token="{{X}}", kind="mustache")
    with pytest.raises((AttributeError, Exception)):
        s.name = "Y"  # type: ignore[misc]


def test_imports_and_typing_dont_break_when_llm_absent() -> None:
    """``infer_template_schema`` must be importable without LLM extras installed."""
    from engine.schema_inference import infer_template_schema

    assert callable(infer_template_schema)
    # signature accepts llm=None
    import inspect

    sig = inspect.signature(infer_template_schema)
    assert "llm" in sig.parameters
    assert sig.parameters["llm"].default is None


# Suppress linter warning about unused import in stub
_ = Any
