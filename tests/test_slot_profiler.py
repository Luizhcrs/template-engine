"""Unit tests for engine.section_mapper.slot_profiler.

Focus on the empty-paragraph fillability rule, which is what regulates
how aggressively the profiler floods the LLM with bogus body slots.

The Corentocantins POP regression (2026-04-27): 19 consecutive empty
paragraphs sit between two all-caps title lines (page padding before
a mega-table). The previous rule "any empty after a heading is a
slot" flagged all 19 as fillable, causing the LLM to either fill them
with arbitrary header text or skip them — blowing up false-positive
slot count from ~16 to 86.
"""

from __future__ import annotations

from engine.section_mapper.slot_profiler import (
    _empty_idxs_under_headings,
    _looks_like_heading,
)


class _FakePara:
    """Minimal stand-in for ``docx.text.paragraph.Paragraph`` — only
    needs a ``.text`` attribute for these tests."""

    def __init__(self, text: str) -> None:
        self.text = text


def _build(paragraphs: list[str]) -> list[_FakePara]:
    return [_FakePara(t) for t in paragraphs]


# --- _looks_like_heading ------------------------------------------------------


def test_looks_like_heading_uppercase_multiword() -> None:
    assert _looks_like_heading("LISTA DE CONTATOS:")
    assert _looks_like_heading("LOGOMARCA DA INSTITUICAO")


def test_looks_like_heading_rejects_sentence_with_period() -> None:
    assert not _looks_like_heading("This is a normal sentence.")


def test_looks_like_heading_rejects_long_uppercase() -> None:
    long_caps = "A" * 100
    assert not _looks_like_heading(long_caps)


# --- _empty_idxs_under_headings: short runs are slots ------------------------


def test_one_empty_between_two_headings_is_fillable() -> None:
    """UNIFAP-style: heading -> empty -> heading. Single empty stays
    fillable so the LLM can drop content under the first heading."""
    paras = _build(["LISTA DE CONTATOS:", "", "LEGENDA"])
    assert _empty_idxs_under_headings(paras) == {1}


def test_two_empties_between_headings_are_fillable() -> None:
    """Cap-2 rule: a run of exactly 2 empties is still treated as a
    legitimate body slot (some templates leave a paragraph + spacer)."""
    paras = _build(["OBJETIVO", "", "", "ESCOPO"])
    assert _empty_idxs_under_headings(paras) == {1, 2}


def test_empty_between_heading_and_body_is_fillable() -> None:
    paras = _build(["OBJETIVO", "", "Conteudo do objetivo aqui"])
    assert _empty_idxs_under_headings(paras) == {1}


# --- _empty_idxs_under_headings: long runs are PADDING, not slots ------------


def test_three_empties_between_headings_are_padding() -> None:
    """A run of 3 empties between two headings is page padding, not a
    fillable slot — drop the lot."""
    paras = _build(["LOGOMARCA", "", "", "", "PROCEDIMENTO"])
    assert _empty_idxs_under_headings(paras) == set()


def test_corentocantins_19_empties_between_titles_are_padding() -> None:
    """Regression for the Corentocantins POP: between the two title
    lines there are 19 empty paragraphs of page-layout padding. None
    of them should be fillable."""
    paras = _build(["LOGOMARCA DA INSTITUICAO", *([""] * 19), "PROCEDIMENTO OPERACIONAL PADRAO"])
    assert _empty_idxs_under_headings(paras) == set()


def test_long_run_of_empties_at_end_of_doc_are_padding() -> None:
    """Empties trailing the last heading with no content after them are
    padding before the next table or end-of-doc, not slots."""
    paras = _build(["OBJETIVO GERAL", "", "", "", "", "", ""])
    assert _empty_idxs_under_headings(paras) == set()


# --- _empty_idxs_under_headings: heading must precede the empty -------------


def test_empty_after_body_is_not_fillable() -> None:
    paras = _build(["Texto qualquer", "", "Mais texto"])
    assert _empty_idxs_under_headings(paras) == set()


def test_empty_at_top_of_doc_is_not_fillable() -> None:
    paras = _build(["", "", "OBJETIVO GERAL"])
    assert _empty_idxs_under_headings(paras) == set()
