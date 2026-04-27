"""Tests for engine.hybrid_mapper."""

from __future__ import annotations

import pytest

from engine.hybrid_mapper import MappingResult, map_hybrid, summarize
from engine.pattern_inference import infer_field_patterns
from engine.schema_inference import FieldSchema

# ----- helpers -----


def _gold_docs_and_examples():
    """3 gold docs + field examples — regex layer can resolve CODIGO+DATA but not CLIENTE."""
    gold = [
        "Codigo: ABC-001\nData: 2026-01-15\nCliente: Empresa Alpha",
        "Codigo: ABC-002\nData: 2026-02-20\nCliente: Cia Beta",
        "Codigo: ABC-003\nData: 2026-03-30\nCliente: Org Gamma",
    ]
    examples = {
        "CODIGO": ["ABC-001", "ABC-002", "ABC-003"],
        "DATA": ["2026-01-15", "2026-02-20", "2026-03-30"],
        # NOTE: CLIENTE intentionally omitted from inferred_patterns to force LLM fallback
    }
    return gold, examples


def _schemas() -> list[FieldSchema]:
    return [
        FieldSchema(name="CODIGO", placeholder_token="{{CODIGO}}", kind="mustache"),
        FieldSchema(name="DATA", placeholder_token="{{DATA}}", kind="mustache"),
        FieldSchema(
            name="CLIENTE",
            placeholder_token="{{CLIENTE}}",
            kind="mustache",
            field_type="freetext",
            context_before="Cliente:",
        ),
    ]


class _StubLLM:
    name = "stub"
    model = "stub-1"

    def __init__(self, response: dict) -> None:
        self.response = response
        self.call_count = 0
        self.last_prompt: str | None = None

    async def generate_structured(self, prompt: str, json_schema: dict) -> dict:
        self.call_count += 1
        self.last_prompt = prompt
        return self.response


# ===== Tier 1 only (no LLM, no missing) =====


@pytest.mark.asyncio
async def test_regex_only_resolves_all_fields_when_patterns_cover_everything():
    gold, examples = _gold_docs_and_examples()
    examples["CLIENTE"] = ["Empresa Alpha", "Cia Beta", "Org Gamma"]
    inferred = infer_field_patterns(gold_docs=gold, field_examples=examples)
    schemas = _schemas()

    new_doc = "Codigo: ABC-999\nData: 2027-12-31\nCliente: Empresa Delta"
    results = await map_hybrid(schemas, inferred, new_doc)

    assert results["CODIGO"].source == "regex"
    assert results["CODIGO"].value == "ABC-999"
    assert results["DATA"].source == "regex"
    assert results["CLIENTE"].source == "regex"
    assert all(r.confidence == 1.0 for r in results.values())


@pytest.mark.asyncio
async def test_regex_only_marks_missing_when_no_llm_and_field_uncovered():
    gold, examples = _gold_docs_and_examples()
    inferred = infer_field_patterns(gold_docs=gold, field_examples=examples)
    schemas = _schemas()

    new_doc = "Codigo: ABC-999\nData: 2027-12-31\nCliente: Empresa Delta"
    results = await map_hybrid(schemas, inferred, new_doc, llm=None)

    assert results["CODIGO"].source == "regex"
    assert results["CLIENTE"].source == "missing"
    assert results["CLIENTE"].value is None
    assert results["CLIENTE"].confidence == 0.0
    assert results["CLIENTE"].notes is not None


# ===== Tier 2: LLM fallback =====


@pytest.mark.asyncio
async def test_llm_fills_missing_field_when_regex_cant_resolve():
    gold, examples = _gold_docs_and_examples()
    inferred = infer_field_patterns(gold_docs=gold, field_examples=examples)
    schemas = _schemas()
    stub = _StubLLM(response={"CLIENTE": {"value": "Empresa Delta", "confidence": 0.85}})

    new_doc = "Codigo: ABC-999\nData: 2027-12-31\nCliente: Empresa Delta"
    results = await map_hybrid(schemas, inferred, new_doc, llm=stub)  # type: ignore[arg-type]

    assert results["CODIGO"].source == "regex"
    assert results["CLIENTE"].source == "llm"
    assert results["CLIENTE"].value == "Empresa Delta"
    assert results["CLIENTE"].confidence == 0.85
    # LLM called exactly once, batched
    assert stub.call_count == 1


@pytest.mark.asyncio
async def test_llm_not_called_when_regex_already_resolved_everything():
    gold, examples = _gold_docs_and_examples()
    examples["CLIENTE"] = ["Empresa Alpha", "Cia Beta", "Org Gamma"]
    inferred = infer_field_patterns(gold_docs=gold, field_examples=examples)
    schemas = _schemas()
    stub = _StubLLM(response={})

    new_doc = "Codigo: ABC-999\nData: 2027-12-31\nCliente: Empresa Delta"
    results = await map_hybrid(schemas, inferred, new_doc, llm=stub)  # type: ignore[arg-type]

    assert all(r.source == "regex" for r in results.values())
    assert stub.call_count == 0  # zero LLM calls — cost saving


@pytest.mark.asyncio
async def test_llm_returning_null_marks_field_as_missing():
    gold, examples = _gold_docs_and_examples()
    inferred = infer_field_patterns(gold_docs=gold, field_examples=examples)
    schemas = _schemas()
    stub = _StubLLM(response={"CLIENTE": {"value": None, "confidence": 0.0}})

    new_doc = "Codigo: ABC-999\nData: 2027-12-31\n(no client info)"
    results = await map_hybrid(schemas, inferred, new_doc, llm=stub)  # type: ignore[arg-type]

    assert results["CLIENTE"].source == "missing"
    assert results["CLIENTE"].value is None


@pytest.mark.asyncio
async def test_llm_failure_marks_missing_fields_gracefully():
    gold, examples = _gold_docs_and_examples()
    inferred = infer_field_patterns(gold_docs=gold, field_examples=examples)
    schemas = _schemas()

    from engine.llm.base import LLMError

    class _BoomLLM:
        name = "boom"
        model = "boom-1"

        async def generate_structured(self, prompt: str, json_schema: dict) -> dict:
            raise LLMError("provider down")

    new_doc = "Codigo: ABC-999\nData: 2027-12-31\nCliente: anything"
    results = await map_hybrid(schemas, inferred, new_doc, llm=_BoomLLM())  # type: ignore[arg-type]

    # Regex-resolved fields still ok
    assert results["CODIGO"].source == "regex"
    # Missing field falls through to "missing"
    assert results["CLIENTE"].source == "missing"


# ===== prompt construction sanity =====


@pytest.mark.asyncio
async def test_llm_prompt_contains_only_missing_field_names():
    gold, examples = _gold_docs_and_examples()
    inferred = infer_field_patterns(gold_docs=gold, field_examples=examples)
    schemas = _schemas()
    stub = _StubLLM(response={"CLIENTE": {"value": "X", "confidence": 0.5}})

    new_doc = "Codigo: ABC-999\nData: 2027-12-31\nCliente: X"
    await map_hybrid(schemas, inferred, new_doc, llm=stub)  # type: ignore[arg-type]

    assert stub.last_prompt is not None
    assert "name=CLIENTE" in stub.last_prompt
    assert "name=CODIGO" not in stub.last_prompt  # already resolved
    assert "name=DATA" not in stub.last_prompt


@pytest.mark.asyncio
async def test_max_source_chars_truncation():
    gold, examples = _gold_docs_and_examples()
    inferred = infer_field_patterns(gold_docs=gold, field_examples=examples)
    schemas = _schemas()
    stub = _StubLLM(response={"CLIENTE": {"value": "Y", "confidence": 0.5}})

    huge_doc = "Codigo: ABC-999\n" + ("X" * 50000) + "\nCliente: Y"
    await map_hybrid(schemas, inferred, huge_doc, llm=stub, max_source_chars=500)  # type: ignore[arg-type]

    assert stub.last_prompt is not None
    # source section should be truncated, prompt total under reasonable bound
    assert len(stub.last_prompt) < 5000


# ===== summarize =====


def test_summarize_counts_by_source():
    results = {
        "A": MappingResult(field="A", value="x", source="regex", confidence=1.0),
        "B": MappingResult(field="B", value="y", source="regex", confidence=1.0),
        "C": MappingResult(field="C", value="z", source="llm", confidence=0.8),
        "D": MappingResult(field="D", value=None, source="missing", confidence=0.0),
    }
    s = summarize(results)
    assert s["total_fields"] == 4
    assert s["by_source"] == {"regex": 2, "llm": 1, "missing": 1}
    assert 0.6 < s["average_confidence"] < 0.8


def test_summarize_empty():
    assert summarize({}) == {
        "total_fields": 0,
        "by_source": {"regex": 0, "llm": 0, "missing": 0},
        "average_confidence": 0.0,
    }


# ===== robustness =====


@pytest.mark.asyncio
async def test_no_inferred_patterns_routes_everything_to_llm():
    schemas = _schemas()
    stub = _StubLLM(
        response={
            "CODIGO": {"value": "ABC-X", "confidence": 0.9},
            "DATA": {"value": "2026-01-01", "confidence": 0.95},
            "CLIENTE": {"value": "Empresa", "confidence": 0.7},
        }
    )

    results = await map_hybrid(schemas, {}, "any text", llm=stub)  # type: ignore[arg-type]
    assert all(r.source == "llm" for r in results.values())
    assert stub.call_count == 1


@pytest.mark.asyncio
async def test_empty_schemas_returns_empty_results():
    results = await map_hybrid([], {}, "anything", llm=None)
    assert results == {}
