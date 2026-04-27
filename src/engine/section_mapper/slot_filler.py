"""Wave N — vision-driven slot fill via LLM.

Single LLM call (multimodal when ``docx2pdf`` + ``pymupdf`` available)
that takes:

- Complete slot inventory from :func:`profile_slots`.
- Source document structure (sections + tables + body paragraphs +
  header text).
- PNG renders of the template (multipage).

Returns:

- ``dict[slot_id, new_text]`` — only the slots the LLM decides to
  fill. Slots the LLM omits OR returns empty for keep their current
  text untouched.

The renderer (:mod:`engine.section_mapper.slot_renderer`) takes this
dict and substitutes each slot's text in place. No cloning, no
inserting, no strategy decisions.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from engine.llm.base import LLMProvider
    from engine.section_mapper.slots import SlotInventory
    from engine.section_mapper.source_profiler import SourceStructure


log = structlog.get_logger(__name__)


_PROMPT = """\
You fill a docx template by replacing the text inside specific slots.
The template is sacred — its layout, headings, and structure must NOT
change. Only the slot texts change.

You receive:

1. SLOTS — a flat list of every fillable place in the template, each
   with a stable ``id``, an ``address``, the ``current_text`` it
   carries, a ``kind`` classification, and a ``context`` snippet
   (e.g. nearest heading or sibling cell). Kinds are:

   - ``empty`` — paragraph or cell is literally blank.
   - ``placeholder`` — carries a delimited token like ``{{X}}`` /
     ``[FOO]`` / ``<<X>>`` / ``(LABEL)`` / underscore run / ``XX``
     mask. Replace ENTIRELY with the value.
   - ``label_value`` — label-with-leader compound like ``Author:
     ____`` or ``Data: __/__/____``. Replace the WHOLE slot text
     with ``label: filled_value`` (keep the label).
   - ``instruction`` — imperative help text like ``Descrever de
     forma resumida...``. Replace ENTIRELY with the source content
     that fits this slot. The current text is the template's hint —
     not real content.
   - ``heading_with_hint`` — numbered heading + parenthesised hint
     in the same cell, like ``1. OBJETIVO: (Descrição clara…)``.
     Replace the slot text with the heading prefix preserved
     followed by the filled content: ``1. OBJETIVO: <real
     objective>``.
   - ``heading`` / ``data`` — NOT fillable. Skip these.

2. SOURCE — the source document profile (sections, tables, header
   text, body paragraphs, polymorphic input) that carries the actual
   content you should redistribute into the slots.

3. TODAY — today's date for migration markers / footer dates.

4. (Optional) Rendered PNG pages of the template so you can SEE the
   visual layout (merged cells, geometry, embedded logos).

Your job: for each fillable slot, decide what new text replaces
``current_text``. Output a JSON object whose ONLY key is
``slot_fills``: an array of ``{"slot_id": "<id>", "new_text":
"<full replacement text>"}``.

Rules:

- If the source has no relevant content for a slot, OMIT it from
  ``slot_fills``. Skipping is fine.
- If a slot's kind is ``heading`` or ``data``, do not include it.
- Headings (slot kind ``heading_with_hint``) keep their numbering /
  prefix in the new_text — only the parenthesised hint becomes real
  content.
- Labels (``label_value``) keep the label text — only the leader
  underscores / dots become the filled value (e.g. ``Autor: Maria
  Silva`` not just ``Maria Silva``).
- Empty slots can be filled with any source content that semantically
  belongs there based on the ``context`` snippet.
- Never repeat the slot's own context or surrounding template text in
  the new_text — write only the replacement value.

SLOTS (JSON array of fillable slots):
{slots_json}

SOURCE structure:
{source_json}

TODAY: {today}

{visual_hint}

Output JSON only. No prose. No markdown.
"""


def _build_schema(inventory: SlotInventory) -> dict:
    fillable_ids = sorted({s.id for s in inventory.fillable()}) or ["__none__"]
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "slot_fills": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "slot_id": {"type": "string", "enum": fillable_ids},
                        "new_text": {"type": "string"},
                    },
                    "required": ["slot_id", "new_text"],
                },
            }
        },
        "required": ["slot_fills"],
    }


_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _clean(s: str) -> str:
    return _CONTROL_CHAR_RE.sub("", s)


async def fill_slots(
    inventory: SlotInventory,
    source: SourceStructure,
    *,
    llm: LLMProvider,
    template_images: list[str] | None = None,
) -> dict[str, str]:
    """Issue ONE LLM call and return ``{slot_id: new_text}`` for every
    slot the LLM decides to fill. Empty new_text values are dropped.
    """
    fillable = inventory.fillable()
    if not fillable:
        return {}

    slots_payload = [s.to_dict() for s in fillable]
    slots_json = json.dumps(slots_payload, ensure_ascii=False)
    source_json = json.dumps(source.to_dict(), ensure_ascii=False)
    today = datetime.now(UTC).date().isoformat()

    visual_hint = (
        "The TEMPLATE has been rendered to PNG image(s) attached below."
        " Use the visual layout to disambiguate merged cells, table"
        " geometry, and embedded logos when deciding what to fill."
        if template_images
        else ""
    )

    prompt = (
        _PROMPT.replace("{slots_json}", slots_json[:80000])
        .replace("{source_json}", source_json[:80000])
        .replace("{today}", today)
        .replace("{visual_hint}", visual_hint)
    )

    schema = _build_schema(inventory)

    try:
        if template_images:
            response = await llm.generate_structured(  # type: ignore[call-arg]
                prompt, schema, image_urls=template_images
            )
        else:
            response = await llm.generate_structured(prompt, schema)
    except Exception as exc:
        log.warning("section_mapper.slot_filler.llm_failed", error=str(exc))
        return {}

    return _parse_response(response)


def _parse_response(response: object) -> dict[str, str]:
    if not isinstance(response, dict):
        log.warning("section_mapper.slot_filler.bad_response_type")
        return {}
    raw = response.get("slot_fills") or []
    if not isinstance(raw, list):
        return {}
    out: dict[str, str] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        sid = entry.get("slot_id")
        text = entry.get("new_text")
        if not (isinstance(sid, str) and isinstance(text, str)):
            continue
        cleaned = _clean(text).strip()
        if not cleaned:
            continue
        out[sid] = cleaned
    return out


__all__ = ["fill_slots"]
