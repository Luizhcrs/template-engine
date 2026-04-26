"""Tests for engine.batch — orchestrator end-to-end."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003 — used at runtime in fixture annotations

import pytest
from docx import Document

from engine.batch import (
    BatchItemResult,
    _classify_tier,
    normalize_batch,
)
from engine.hybrid_mapper import MappingResult
from engine.schema_inference import FieldSchema
from engine.semantic_diff import Discrepancy

# ===== fixtures =====


def _write_template(path: Path, body_lines: list[str]) -> None:
    doc = Document()
    for line in body_lines:
        doc.add_paragraph(line)
    doc.save(str(path))


def _write_source(path: Path, body_lines: list[str]) -> None:
    _write_template(path, body_lines)


@pytest.fixture
def template_and_sources(tmp_path: Path) -> tuple[Path, Path, Path]:
    template = tmp_path / "template.docx"
    _write_template(
        template,
        [
            "LAUDO TECNICO",
            "Codigo: {{CODIGO}}",
            "Data: {{DATA}}",
            "Cliente: {{CLIENTE}}",
        ],
    )

    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    _write_source(
        source_dir / "doc1.docx",
        [
            "LAUDO TECNICO",
            "Codigo: ABC-001",
            "Data: 2026-01-15",
            "Cliente: Empresa Alpha",
        ],
    )
    _write_source(
        source_dir / "doc2.docx",
        [
            "LAUDO TECNICO",
            "Codigo: ABC-002",
            "Data: 2026-02-20",
            "Cliente: Cia Beta",
        ],
    )
    output_dir = tmp_path / "out"
    return template, source_dir, output_dir


# ===== _classify_tier =====


def test_classify_high_when_all_regex_no_discrepancies():
    schemas = [FieldSchema(name="X", placeholder_token="{{X}}", kind="mustache")]
    mapping = {"X": MappingResult("X", "v", "regex", 1.0)}
    tier = _classify_tier(mapping, [], schemas=schemas)
    assert tier == "high"


def test_classify_medium_when_llm_used():
    schemas = [FieldSchema(name="X", placeholder_token="{{X}}", kind="mustache")]
    mapping = {"X": MappingResult("X", "v", "llm", 0.8)}
    tier = _classify_tier(mapping, [], schemas=schemas)
    assert tier == "medium"


def test_classify_medium_when_warning_discrepancy():
    schemas = [FieldSchema(name="X", placeholder_token="{{X}}", kind="mustache")]
    mapping = {"X": MappingResult("X", "v", "regex", 1.0)}
    discrepancies = [Discrepancy("missing_in_output", "extra", "v", None, "warning", "")]
    tier = _classify_tier(mapping, discrepancies, schemas=schemas)
    assert tier == "medium"


def test_classify_low_when_critical_discrepancy():
    schemas = [FieldSchema(name="X", placeholder_token="{{X}}", kind="mustache")]
    mapping = {"X": MappingResult("X", "v", "regex", 1.0)}
    discrepancies = [Discrepancy("missing_in_output", "CPF", "x", None, "critical", "")]
    tier = _classify_tier(mapping, discrepancies, schemas=schemas)
    assert tier == "low"


def test_classify_low_when_required_field_missing():
    schemas = [
        FieldSchema(name="X", placeholder_token="{{X}}", kind="mustache", required=True),
    ]
    mapping = {"X": MappingResult("X", None, "missing", 0.0)}
    tier = _classify_tier(mapping, [], schemas=schemas)
    assert tier == "low"


def test_classify_high_when_optional_field_missing():
    schemas = [
        FieldSchema(name="X", placeholder_token="{{X}}", kind="mustache", required=True),
        FieldSchema(name="Y", placeholder_token="{{Y}}", kind="mustache", required=False),
    ]
    mapping = {
        "X": MappingResult("X", "v", "regex", 1.0),
        "Y": MappingResult("Y", None, "missing", 0.0),
    }
    tier = _classify_tier(mapping, [], schemas=schemas)
    assert tier == "high"


# ===== normalize_batch — regex-only path =====


@pytest.mark.asyncio
async def test_normalize_batch_regex_only_no_llm(template_and_sources, tmp_path):
    template, source_dir, output_dir = template_and_sources

    gold_docs = [
        "Codigo: ABC-001\nData: 2026-01-15\nCliente: Empresa Alpha",
        "Codigo: ABC-002\nData: 2026-02-20\nCliente: Cia Beta",
        "Codigo: ABC-003\nData: 2026-03-30\nCliente: Org Gamma",
    ]
    field_examples = {
        "CODIGO": ["ABC-001", "ABC-002", "ABC-003"],
        "DATA": ["2026-01-15", "2026-02-20", "2026-03-30"],
        "CLIENTE": ["Empresa Alpha", "Cia Beta", "Org Gamma"],
    }

    report = await normalize_batch(
        template,
        source_dir,
        output_dir,
        llm=None,
        gold_docs=gold_docs,
        field_examples=field_examples,
    )

    # All docs went through regex tier alone
    assert report.by_tier["high"] >= 1
    assert report.llm_call_count == 0
    assert len(report.items) == 2

    # Output docx files exist + have substituted values
    for item in report.items:
        assert item.output_path is not None
        assert item.output_path.exists()
        out_doc = Document(str(item.output_path))
        text = "\n".join(p.text for p in out_doc.paragraphs)
        assert "{{CODIGO}}" not in text  # placeholder substituted
        assert "ABC-" in text


@pytest.mark.asyncio
async def test_normalize_batch_writes_outputs_named_after_sources(template_and_sources, tmp_path):
    template, source_dir, output_dir = template_and_sources
    report = await normalize_batch(template, source_dir, output_dir, llm=None)

    output_names = {item.output_path.name for item in report.items if item.output_path}
    assert "doc1.normalized.docx" in output_names
    assert "doc2.normalized.docx" in output_names


@pytest.mark.asyncio
async def test_normalize_batch_handles_empty_source_dir(tmp_path):
    template = tmp_path / "tpl.docx"
    _write_template(template, ["x"])
    src = tmp_path / "src"
    src.mkdir()
    out = tmp_path / "out"
    report = await normalize_batch(template, src, out, llm=None)
    assert report.items == []
    assert report.by_tier == {"high": 0, "medium": 0, "low": 0, "error": 0}


# ===== normalize_batch — LLM fallback path =====


class _StubLLM:
    name = "stub"
    model = "stub-1"

    def __init__(self, *, fallback_response: dict | None = None) -> None:
        self.fallback_response = fallback_response or {}
        self.calls = 0

    async def generate_structured(self, prompt: str, json_schema: dict) -> dict:
        self.calls += 1
        # Schema enrichment: response shape {field_type, format_hint, required}
        if "Placeholder name:" in prompt:
            return {"field_type": "freetext", "format_hint": None, "required": True}
        # Semantic diff response
        if "<<<SOURCE_START>>>" in prompt:
            return {"discrepancies": []}
        # Hybrid fallback response
        return self.fallback_response


@pytest.mark.asyncio
async def test_normalize_batch_uses_llm_for_missing_fields(template_and_sources):
    template, source_dir, output_dir = template_and_sources
    stub = _StubLLM(
        fallback_response={
            "CODIGO": {"value": "FALLBACK-CODE", "confidence": 0.6},
            "DATA": {"value": "2099-01-01", "confidence": 0.6},
            "CLIENTE": {"value": "Fallback Cia", "confidence": 0.6},
        }
    )

    # No gold docs / examples → regex tier skipped → all routes to LLM
    report = await normalize_batch(
        template,
        source_dir,
        output_dir,
        llm=stub,  # type: ignore[arg-type]
    )

    assert report.llm_call_count > 0
    # Each item should have all 3 fields filled by LLM
    for item in report.items:
        assert item.tier in {"medium", "low"}  # never "high" without regex
        assert all(r.source == "llm" for r in item.mapping.values())


# ===== BatchReport.to_dict =====


@pytest.mark.asyncio
async def test_report_to_dict_is_json_serializable(template_and_sources):
    template, source_dir, output_dir = template_and_sources
    report = await normalize_batch(template, source_dir, output_dir, llm=None)
    import json

    data = report.to_dict()
    serialized = json.dumps(data)
    parsed = json.loads(serialized)
    assert "by_tier" in parsed
    assert "items" in parsed
    assert "fields" in parsed


@pytest.mark.asyncio
async def test_report_includes_per_item_mapping_summary(template_and_sources):
    template, source_dir, output_dir = template_and_sources
    report = await normalize_batch(template, source_dir, output_dir, llm=None)

    data = report.to_dict()
    for item_dict in data["items"]:
        assert "mapping_summary" in item_dict
        assert "by_source" in item_dict["mapping_summary"]


# ===== error handling =====


@pytest.mark.asyncio
async def test_failed_doc_marked_as_error_tier_without_killing_batch(tmp_path):
    template = tmp_path / "tpl.docx"
    _write_template(template, ["{{X}}"])
    src = tmp_path / "src"
    src.mkdir()
    # Valid doc
    _write_source(src / "good.docx", ["X: ok"])
    # Invalid doc — write a file with .docx extension but invalid content
    bad = src / "bad.docx"
    bad.write_bytes(b"not a docx at all")

    out = tmp_path / "out"
    report = await normalize_batch(template, src, out, llm=None)

    tiers = [item.tier for item in report.items]
    assert "error" in tiers
    error_item = next(i for i in report.items if i.tier == "error")
    assert error_item.error is not None


# Suppress unused import warning
_ = BatchItemResult
