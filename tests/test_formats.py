"""Tests for engine.formats (Wave H)."""

from __future__ import annotations

import pytest

from engine.formats import (
    Format,
    FormatNotFound,
    describe_formats,
    list_formats,
    load_format,
)
from engine.hybrid_mapper import map_hybrid
from engine.pattern_inference import infer_field_patterns

# ===== registry =====


def test_list_formats_returns_all_5():
    names = list_formats()
    assert set(names) == {
        "abnt_artigo",
        "abnt_tcc",
        "abnt_referencia",
        "laudo_nr12",
        "contrato_simples",
    }


def test_load_format_returns_format_object():
    fmt = load_format("abnt_tcc")
    assert isinstance(fmt, Format)
    assert fmt.name == "abnt_tcc"
    assert fmt.spec == "ABNT NBR 14724:2024"


def test_load_format_unknown_raises():
    with pytest.raises(FormatNotFound):
        load_format("nope_does_not_exist")


def test_describe_formats_returns_serializable_list():
    import json

    desc = describe_formats()
    serialized = json.dumps(desc)
    parsed = json.loads(serialized)
    assert len(parsed) == 5
    for entry in parsed:
        assert "name" in entry
        assert "title" in entry
        assert "fields" in entry


# ===== shape sanity =====


@pytest.mark.parametrize(
    "name",
    ["abnt_artigo", "abnt_tcc", "abnt_referencia", "laudo_nr12", "contrato_simples"],
)
def test_format_has_3_gold_docs(name):
    fmt = load_format(name)
    assert len(fmt.gold_docs) == 3


@pytest.mark.parametrize(
    "name",
    ["abnt_artigo", "abnt_tcc", "abnt_referencia", "laudo_nr12", "contrato_simples"],
)
def test_format_has_at_least_4_schemas(name):
    fmt = load_format(name)
    assert len(fmt.schemas) >= 4


@pytest.mark.parametrize(
    "name",
    ["abnt_artigo", "abnt_tcc", "abnt_referencia", "laudo_nr12", "contrato_simples"],
)
def test_format_field_examples_have_3_each(name):
    fmt = load_format(name)
    for field_name, examples in fmt.field_examples.items():
        assert len(examples) == 3, f"{name}: {field_name} should have 3 examples"


@pytest.mark.parametrize(
    "name",
    ["abnt_artigo", "abnt_tcc", "abnt_referencia", "laudo_nr12", "contrato_simples"],
)
def test_format_examples_appear_in_gold_docs(name):
    """Each example value must be findable in at least one gold doc.

    Otherwise pattern_inference would never collect a label for that field.
    """
    fmt = load_format(name)
    for field_name, examples in fmt.field_examples.items():
        for ex in examples:
            assert any(ex in doc for doc in fmt.gold_docs), (
                f"{name}: example {ex!r} of field {field_name!r} must appear in at least one gold doc"
            )


@pytest.mark.parametrize(
    "name",
    ["abnt_artigo", "abnt_tcc", "abnt_referencia", "laudo_nr12", "contrato_simples"],
)
def test_format_conformity_weights_sum_close_to_one(name):
    fmt = load_format(name)
    total = sum(fmt.conformity_weights.values())
    assert 0.95 <= total <= 1.05, f"{name}: weights sum to {total}"


# ===== integration: pattern_inference + hybrid_mapper =====


@pytest.mark.parametrize(
    "name",
    ["abnt_artigo", "abnt_tcc", "abnt_referencia", "laudo_nr12", "contrato_simples"],
)
def test_format_pattern_inference_produces_regexes(name):
    fmt = load_format(name)
    inferred = infer_field_patterns(
        gold_docs=fmt.gold_docs,
        field_examples=fmt.field_examples,
    )
    # Every requested field must appear in the inferred output
    for field_name in fmt.field_examples:
        assert field_name in inferred, f"{name}: {field_name} missing from inferred"


@pytest.mark.parametrize(
    "name",
    ["abnt_tcc", "laudo_nr12", "contrato_simples"],
)
@pytest.mark.asyncio
async def test_format_hybrid_mapper_extracts_from_gold_doc(name):
    """Run hybrid_mapper (regex-only) against a gold doc; expect non-trivial
    coverage (>50% of required fields filled by regex tier).
    """
    fmt = load_format(name)
    inferred = infer_field_patterns(
        gold_docs=fmt.gold_docs,
        field_examples=fmt.field_examples,
    )
    sample_doc = fmt.gold_docs[0]
    mapping = await map_hybrid(fmt.schemas, inferred, sample_doc, llm=None)

    required_filled = sum(
        1 for s in fmt.schemas if s.required and s.name in mapping and mapping[s.name].source == "regex"
    )
    required_total = sum(1 for s in fmt.schemas if s.required)
    coverage = required_filled / required_total
    assert coverage >= 0.5, f"{name}: regex-only coverage {coverage:.2f} below 50% on the gold doc itself"


# ===== specific format checks =====


def test_laudo_nr12_has_industrial_required_headings():
    fmt = load_format("laudo_nr12")
    expected = {"IDENTIFICACAO", "EQUIPAMENTO", "INSPECAO", "CONCLUSAO"}
    assert expected.issubset(set(fmt.required_headings))


def test_abnt_tcc_has_academic_required_headings():
    fmt = load_format("abnt_tcc")
    for h in ("RESUMO", "ABSTRACT", "REFERENCIAS"):
        assert h in fmt.required_headings


def test_laudo_nr12_weights_emphasize_technical():
    """For an industrial laudo, technical (CNPJ + CREA + dates valid) must
    weigh more than text/visual/design.
    """
    fmt = load_format("laudo_nr12")
    assert fmt.conformity_weights["technical"] >= 0.30
    assert fmt.conformity_weights["technical"] > fmt.conformity_weights["text"]


def test_abnt_tcc_weights_emphasize_structural():
    """ABNT TCC has prescribed sections; structural matters more than design."""
    fmt = load_format("abnt_tcc")
    assert fmt.conformity_weights["structural"] >= fmt.conformity_weights["text"] * 0.8


def test_abnt_referencia_threshold_is_strict():
    """References should be near-perfect or rejected; threshold > 0.85."""
    fmt = load_format("abnt_referencia")
    assert fmt.recommended_threshold >= 0.88


# ===== Format dataclass =====


def test_format_is_frozen():
    fmt = load_format("abnt_tcc")
    with pytest.raises((AttributeError, Exception)):
        fmt.name = "changed"  # type: ignore[misc]


def test_all_format_modules_export_FORMAT():
    """Every module under engine.formats/ exposing a format must export FORMAT."""
    from engine.formats import abnt_artigo, abnt_referencia, abnt_tcc, contrato_simples, laudo_nr12

    for module in (abnt_artigo, abnt_tcc, abnt_referencia, laudo_nr12, contrato_simples):
        assert hasattr(module, "FORMAT")
        assert isinstance(module.FORMAT, Format)
