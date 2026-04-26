"""Tests for engine.pattern_inference."""

from __future__ import annotations

import pytest

from engine.pattern_inference import (
    _aggregate_labels,
    _detect_value_shape,
    _extract_label_before,
    _grex_available,
    _grex_learn,
    apply_inferred,
    infer_field_patterns,
)

# ===== _detect_value_shape =====


def test_detect_iso_date():
    name, _ = _detect_value_shape(["2026-04-26", "2025-12-31"])
    assert name == "iso_date"


def test_detect_doc_code():
    name, _ = _detect_value_shape(["DOC-042", "LAUDO-2026-099", "REL-04"])
    assert name == "doc_code"


def test_detect_cpf():
    name, _ = _detect_value_shape(["123.456.789-00", "987.654.321-99"])
    assert name == "cpf"


def test_detect_fullname():
    name, _ = _detect_value_shape(["Joao Silva", "Maria da Silva", "Hiroshi Tanaka"])
    assert name == "fullname"


def test_detect_integer():
    name, _ = _detect_value_shape(["42", "100", "0042"])
    assert name == "integer"


def test_detect_falls_back_to_freetext():
    name, _ = _detect_value_shape(["any text here", "outro texto"])
    assert name == "freetext"


def test_detect_mixed_examples_falls_back_to_grex_or_freetext():
    """One example fits ISO date, other is fullname → no Tier 1 match.

    With grex (Tier 2) installed, learns a union pattern; without it, lands on freetext.
    """
    name, _ = _detect_value_shape(["2026-04-26", "Joao Silva"])
    assert name in {"freetext", "grex_learned"}


# ===== _extract_label_before =====


def test_extract_label_simple():
    text = "Nome: Joao Silva"
    label = _extract_label_before(text, text.index("Joao"))
    assert label == "Nome"


def test_extract_label_multiline():
    text = "Header line\nCodigo: ABC-123"
    label = _extract_label_before(text, text.index("ABC"))
    assert label == "Codigo"


def test_extract_label_returns_none_no_colon():
    text = "Just a sentence with no label"
    label = _extract_label_before(text, len(text) - 5)
    assert label is None


def test_extract_label_returns_none_too_long():
    """Label > 50 chars rejected (probably not a label)."""
    long_text = "this is way too long to be a real label heading description block"
    text = f"{long_text}: VALUE"
    label = _extract_label_before(text, text.index("VALUE"))
    assert label is None


# ===== _aggregate_labels =====


def test_aggregate_labels_orders_by_frequency():
    labels = ["Nome", "Codigo", "Nome", "Nome", "Codigo"]
    out = _aggregate_labels(labels)
    assert out == ["Nome", "Codigo"]


def test_aggregate_labels_empty():
    assert _aggregate_labels([]) == []


# ===== infer_field_patterns end-to-end =====


def test_infer_pattern_for_iso_date():
    gold = [
        "Cabecalho\nData de emissao: 2026-04-26\nfooter",
        "Outro doc\nData de emissao: 2025-12-31\noutro",
    ]
    inferred = infer_field_patterns(
        gold_docs=gold,
        field_examples={"DATA": ["2026-04-26", "2025-12-31"]},
    )
    assert "DATA" in inferred
    ip = inferred["DATA"]
    assert ip.value_shape_name == "iso_date"
    assert "Data de emissao" in ip.label_variants
    assert ip.coverage == 1.0
    # Apply on new text
    extracted = ip.regex.search("Data de emissao: 2027-01-15")
    assert extracted
    assert extracted.group(1) == "2027-01-15"


def test_infer_pattern_with_label_variants():
    """Same field appears under different labels in golds."""
    gold = [
        "Codigo: LAUDO-001",
        "Identificador: LAUDO-002",
        "Codigo: LAUDO-003",
    ]
    inferred = infer_field_patterns(
        gold_docs=gold,
        field_examples={"CODE": ["LAUDO-001", "LAUDO-002", "LAUDO-003"]},
    )
    ip = inferred["CODE"]
    assert "Codigo" in ip.label_variants
    assert "Identificador" in ip.label_variants
    # Regex should match either label
    assert ip.regex.search("Codigo: LAUDO-999")
    assert ip.regex.search("Identificador: LAUDO-888")


def test_infer_pattern_skips_field_with_no_examples():
    inferred = infer_field_patterns(
        gold_docs=["Nome: Joao"],
        field_examples={"NOME": [], "OTHER": ["value"]},
    )
    assert "NOME" not in inferred


def test_infer_pattern_coverage_zero_when_no_match():
    """Examples don't appear in golds → coverage 0."""
    inferred = infer_field_patterns(
        gold_docs=["doc sem nada"],
        field_examples={"NOME": ["Joao Silva", "Maria Souza"]},
    )
    ip = inferred["NOME"]
    # No label found, fallback to value-shape only regex
    assert ip.coverage == 0.0


# ===== Tier 2: grex-learned shapes =====


_grex_skip = pytest.mark.skipif(not _grex_available(), reason="grex optional dep not installed")


@_grex_skip
def test_grex_learns_single_char_class():
    """grex generalizes ['A','A','B'] -> [AB]."""
    learned = _grex_learn(["A", "A", "B"])
    assert learned is not None
    assert "[AB]" in learned or "[BA]" in learned


@_grex_skip
def test_grex_learns_digit_pattern():
    """ISSN-like ['2026-0042-CR','2026-0099-XR','2026-0001-AR'] gets digit conversion."""
    learned = _grex_learn(["2026-0042-CR", "2026-0099-XR", "2026-0001-AR"])
    assert learned is not None
    assert r"\d" in learned


@_grex_skip
def test_grex_rejects_pure_literal_alternations():
    """grex shouldn't return ``(?:foo|bar)`` alone — too literal to generalize."""
    # 3 unrelated short words — grex would emit (?:cat|dog|fox) — rejected.
    result = _grex_learn(["cat", "dog", "fox"])
    assert result is None


@_grex_skip
def test_detect_shape_uses_grex_when_no_predefined_match():
    """Shape ['A','A','B'] doesn't match any predefined shape — grex tier kicks in."""
    name, fragment = _detect_value_shape(["A", "A", "B"])
    assert name == "grex_learned"
    assert "[AB]" in fragment or "[BA]" in fragment


@_grex_skip
def test_detect_shape_predefined_takes_priority_over_grex():
    """ISO date hits Tier 1 — grex never invoked."""
    name, _ = _detect_value_shape(["2026-04-26", "2025-12-31"])
    assert name == "iso_date"  # NOT "grex_learned"


@_grex_skip
def test_grex_skipped_when_examples_too_long():
    """Long free-text examples skip grex (would produce noise)."""
    long_examples = [
        "Avaliar conformidade do equipamento ABC-9 conforme ISO 9001",
        "Avaliar conformidade do equipamento DEF-2 conforme ISO 14001",
    ]
    name, fragment = _detect_value_shape(long_examples)
    assert name == "freetext"
    assert fragment == r"[^\n]+"


# ===== full inference end-to-end =====


def test_apply_inferred_extracts_multiple_fields():
    gold = [
        "Codigo: REL-001\nData: 2026-01-15\nResponsavel: Ana Costa",
        "Codigo: REL-002\nData: 2026-02-20\nResponsavel: Bruno Lima",
    ]
    inferred = infer_field_patterns(
        gold_docs=gold,
        field_examples={
            "CODIGO": ["REL-001", "REL-002"],
            "DATA": ["2026-01-15", "2026-02-20"],
            "RESP": ["Ana Costa", "Bruno Lima"],
        },
    )

    new_text = "Codigo: REL-099\nData: 2027-12-31\nResponsavel: Carla Mendes"
    extracted = apply_inferred(inferred, new_text)

    assert extracted["CODIGO"] == "REL-099"
    assert extracted["DATA"] == "2027-12-31"
    assert extracted["RESP"] == "Carla Mendes"
