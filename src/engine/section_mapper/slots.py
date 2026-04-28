"""Slot pipeline — unified ``Slot`` abstraction.

The LLM-driven mapper pipeline split fill operations across five fields
(``header_substitutions``, ``section_content``, ``table_data``,
``paragraph_rewrites``, ``cell_fills``). Each had its own renderer
path. Coordinating them was brittle: source content sometimes got
appended next to template instructions instead of replacing them
(UNIFAP), mega-table cells with imperative hints sometimes resisted
overwrite (Corentocantins).

Slot pipeline collapses every fillable place in a docx into one shape: a
:class:`Slot`. The LLM returns ``{slot_id: new_text}``; the renderer
substitutes each slot's text in place. No cloning, no inserting, no
strategy decisions inside the LLM. The template stays sacred —
slots are the only thing that change.

A slot can live in:

- A body paragraph (``location="body_para"``, address points at the
  paragraph index in ``doc.paragraphs``).
- A table cell (``location="table_cell"``, address has
  ``table_index`` + ``row`` + ``col``).
- A header / footer paragraph (``location="header_para"`` /
  ``"footer_para"``, address has the part name + paragraph index
  inside that part).

Every slot has a stable string ID so the LLM and renderer share a
common reference: ``"body_para_42"``, ``"cell_t0_r2_c0"``,
``"header_word_header1_p3"``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class SlotAddress:
    """Where exactly a :class:`Slot` lives in the docx tree."""

    location: str  # body_para | table_cell | header_para | footer_para
    paragraph_idx: int | None = None  # body_para / header_para / footer_para
    table_index: int | None = None  # table_cell only
    row: int | None = None
    col: int | None = None
    part_name: str | None = None  # header_para / footer_para: word/headerN.xml

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Slot:
    """One fillable place in the template.

    Attributes:
        id: stable string identifier; LLM and renderer share it.
        address: structural coordinate inside the docx tree.
        current_text: text the template currently carries at that
            address (template default / placeholder / empty).
        kind: rough classification — ``"empty"``, ``"placeholder"``
            (carries delimited token like ``{{X}}``), ``"label_value"``
            (label-with-leader compound like ``Autor: ____``),
            ``"instruction"`` (imperative help text like ``Descrever
            de forma resumida...``), ``"heading_with_hint"``
            (numbered heading + parenthesised hint, common in
            Corentocantins-style cells), ``"data"`` (already filled
            data — usually NOT fillable).
        context: surrounding text (e.g. nearest heading, neighbouring
            cell) to help the LLM decide what content fits.
        is_fillable: ``True`` when the LLM should attempt to fill
            this slot. ``False`` when the slot is data that must be
            preserved (already-filled tables of the template).
    """

    id: str
    address: SlotAddress
    current_text: str
    kind: str
    context: str = ""
    is_fillable: bool = True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "address": self.address.to_dict(),
            "current_text": self.current_text,
            "kind": self.kind,
            "context": self.context,
            "is_fillable": self.is_fillable,
        }


@dataclass(frozen=True)
class SlotInventory:
    """Complete listing of every slot in a template."""

    template_path: str
    slots: list[Slot] = field(default_factory=list)

    def fillable(self) -> list[Slot]:
        return [s for s in self.slots if s.is_fillable]

    def by_id(self) -> dict[str, Slot]:
        return {s.id: s for s in self.slots}

    def to_dict(self) -> dict:
        return {
            "template_path": self.template_path,
            "slots": [s.to_dict() for s in self.slots],
        }


__all__ = [
    "Slot",
    "SlotAddress",
    "SlotInventory",
]
