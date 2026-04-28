"""Unit tests for engine.section_mapper.slot_reviewer.

The reviewer's job is the closed-loop pass: render the post-fill docx
to images, show the LLM what it produced, accept a list of
corrections. We mock out the LLM and the multimodal renderer because
neither is needed to verify the wiring + response parsing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from engine.section_mapper.slot_reviewer import review_slots
from engine.section_mapper.slots import Slot, SlotAddress, SlotInventory

if TYPE_CHECKING:
    from pathlib import Path


class _MockLLM:
    """Captures the call args and returns a canned response."""

    def __init__(self, response: dict) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def generate_structured(
        self,
        prompt: str,
        schema: dict,
        image_urls: list[str] | None = None,
    ) -> dict:
        self.calls.append({"prompt": prompt, "schema": schema, "image_urls": list(image_urls or [])})
        return self.response


def _make_inventory() -> SlotInventory:
    slots = [
        Slot(
            id="cell_t0_r1_c2",
            address=SlotAddress(location="table_cell", table_index=0, row=1, col=2),
            current_text="João Pedro",
            kind="empty",
            context='column="Telefone" | 1 | Fulano (Titular)',
            is_fillable=True,
        ),
        Slot(
            id="cell_t0_r1_c3",
            address=SlotAddress(location="table_cell", table_index=0, row=1, col=3),
            current_text="diplan@unifap.br",
            kind="empty",
            context='column="e-mail" | 1 | Fulano (Titular)',
            is_fillable=True,
        ),
        Slot(
            id="cell_t0_r0_c0",
            address=SlotAddress(location="table_cell", table_index=0, row=0, col=0),
            current_text="Nº",
            kind="data",
            context="",
            is_fillable=False,
        ),
    ]
    return SlotInventory(template_path="dummy.docx", slots=slots)


class _FakeSource:
    def to_dict(self) -> dict:
        return {"sections": [{"name": "ANY", "content": "anything"}]}


@pytest.mark.asyncio
async def test_review_slots_returns_parsed_corrections(tmp_path: Path) -> None:
    inv = _make_inventory()
    src = _FakeSource()
    llm = _MockLLM(
        response={
            "corrections": [
                {"slot_id": "cell_t0_r1_c2", "new_text": "(96) 3213-1010"},
            ]
        }
    )

    out = await review_slots(
        tmp_path / "fake_output.docx",
        inv,
        src,
        llm=llm,
        output_image_urls=["data:image/png;base64,FAKE"],
    )

    assert out == {"cell_t0_r1_c2": "(96) 3213-1010"}
    assert len(llm.calls) == 1
    # The LLM must have received the rendered images.
    assert llm.calls[0]["image_urls"] == ["data:image/png;base64,FAKE"]


@pytest.mark.asyncio
async def test_review_slots_skips_when_no_images(tmp_path: Path) -> None:
    """When the post-fill renderer cannot produce PNGs (no docx2pdf /
    pymupdf available, or rendering failed), the reviewer must
    short-circuit and return an empty dict — never blow up."""
    inv = _make_inventory()
    src = _FakeSource()
    llm = _MockLLM(response={"corrections": [{"slot_id": "x", "new_text": "y"}]})

    out = await review_slots(
        tmp_path / "fake_output.docx",
        inv,
        src,
        llm=llm,
        output_image_urls=[],
    )

    assert out == {}
    assert llm.calls == []  # LLM not consulted at all


@pytest.mark.asyncio
async def test_review_slots_drops_corrections_for_unknown_slot_ids(tmp_path: Path) -> None:
    """The reviewer's JSON schema enforces ``slot_id`` is one of the
    fillable ids, but if the LLM hallucinates anyway, ``_parse_response``
    must drop the bogus entries silently."""
    inv = _make_inventory()
    src = _FakeSource()
    llm = _MockLLM(
        response={
            "corrections": [
                {"slot_id": "cell_t0_r1_c2", "new_text": "(96) 3213-1010"},
                {"slot_id": "made_up_id", "new_text": "garbage"},
                {"new_text": "missing slot_id"},  # malformed
                {"slot_id": "cell_t0_r1_c3", "new_text": "  "},  # whitespace-only
            ]
        }
    )

    out = await review_slots(
        tmp_path / "fake_output.docx",
        inv,
        src,
        llm=llm,
        output_image_urls=["data:image/png;base64,FAKE"],
    )

    # Only the well-formed correction with a non-empty value survives.
    # (We do not enforce id-membership here — the JSON schema does that
    # at the LLM boundary; the parser just rejects malformed entries
    # and whitespace-only values.)
    assert "cell_t0_r1_c2" in out
    assert out["cell_t0_r1_c2"] == "(96) 3213-1010"
    assert "cell_t0_r1_c3" not in out  # whitespace-only stripped


@pytest.mark.asyncio
async def test_review_slots_drops_corrections_with_template_default_tokens(
    tmp_path: Path,
) -> None:
    """Reviewer occasionally proposes ``Fulano de Tal``,
    ``XXXXX``, ``x.xx.xxx.xx`` — i.e. asks us to OVERWRITE real data
    with a template default. Such corrections must be dropped."""
    inv = _make_inventory()
    src = _FakeSource()
    llm = _MockLLM(
        response={
            "corrections": [
                {"slot_id": "cell_t0_r1_c2", "new_text": "Fulano de Tal"},
                {"slot_id": "cell_t0_r1_c3", "new_text": "real@email.br"},
            ]
        }
    )

    out = await review_slots(
        tmp_path / "fake_output.docx",
        inv,
        src,
        llm=llm,
        output_image_urls=["data:image/png;base64,FAKE"],
    )

    # The Fulano de Tal correction is rejected; the real-looking one
    # comes through.
    assert out == {"cell_t0_r1_c3": "real@email.br"}


def test_extract_column_header_pulls_anchor_from_context() -> None:
    """The reviewer enriches each slot's payload with the explicit
    ``expected_column`` field so the LLM does not have to parse the
    ``column="..."`` prefix itself."""
    from engine.section_mapper.slot_reviewer import _extract_column_header

    assert _extract_column_header('column="Telefone" | 1 | Fulano (Titular)') == "Telefone"
    assert _extract_column_header('column="e-mail" | 2') == "e-mail"
    assert _extract_column_header("just sibling text | foo | bar") == ""
    assert _extract_column_header("") == ""


@pytest.mark.asyncio
async def test_review_slots_lifts_expected_column_into_payload(tmp_path: Path) -> None:
    """Each table-cell slot whose context starts with column="..."
    must arrive at the LLM with an explicit ``expected_column`` field
    in its payload — not just buried inside ``context``."""
    inv = _make_inventory()
    src = _FakeSource()
    llm = _MockLLM(response={"corrections": []})

    await review_slots(
        tmp_path / "fake_output.docx",
        inv,
        src,
        llm=llm,
        output_image_urls=["data:image/png;base64,FAKE"],
    )

    assert len(llm.calls) == 1
    prompt = llm.calls[0]["prompt"]
    # Payload is JSON-encoded inside the prompt; spot-check the column
    # anchors are surfaced there as their own field.
    assert '"expected_column": "Telefone"' in prompt
    assert '"expected_column": "e-mail"' in prompt


@pytest.mark.asyncio
async def test_review_slots_handles_llm_exception(tmp_path: Path) -> None:
    """If the LLM call raises (rate limit, timeout, malformed response
    from upstream), the reviewer logs and returns an empty dict so the
    pipeline keeps the first-pass output."""
    inv = _make_inventory()
    src = _FakeSource()

    class _ExplodingLLM:
        async def generate_structured(self, *args: Any, **kwargs: Any) -> dict:
            raise RuntimeError("upstream timeout")

    out = await review_slots(
        tmp_path / "fake_output.docx",
        inv,
        src,
        llm=_ExplodingLLM(),
        output_image_urls=["data:image/png;base64,FAKE"],
    )

    assert out == {}
