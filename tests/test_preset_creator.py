from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from engine.preset_creator import create_preset
from engine.preset_loader import load_preset

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
async def test_create_preset_generates_all_artifacts(tmp_path):
    mock_llm = AsyncMock()
    mock_llm.generate_structured.return_value = {
        "pattern_md": "# Padrao\nTeste",
        "content_schema": {
            "type": "object",
            "properties": {"titulo": {"type": "string"}},
            "required": ["titulo"],
        },
        "render_ops": [
            {"op": "set_header_field", "params": {"name": "CODIGO", "source_key": "codigo"}},
        ],
        "validation": {"critical_tokens": [], "required_sections": ["titulo"], "min_completeness": 0.7},
    }

    dest = tmp_path / "my-preset"
    await create_preset(
        llm=mock_llm,
        slug="test-preset",
        name="Test",
        template_path=FIXTURES / "template_sample.docx",
        gold_paths=[FIXTURES / "gold_sample_01.docx"],
        dest_dir=dest,
        owner="user-123",
    )

    assert (dest / "manifest.json").exists()
    assert (dest / "pattern.md").exists()
    assert (dest / "schema.json").exists()
    assert (dest / "render_ops.yaml").exists()
    assert (dest / "validation.yaml").exists()
    assert (dest / "template.docx").exists()
    assert (dest / "gold" / "gold-01.docx").exists()


@pytest.mark.asyncio
async def test_created_preset_loads_via_loader(tmp_path):
    mock_llm = AsyncMock()
    mock_llm.generate_structured.return_value = {
        "pattern_md": "# Padrao detectado\nSimples",
        "content_schema": {"type": "object", "properties": {"titulo": {"type": "string"}}},
        "render_ops": [
            {"op": "write_section", "params": {"heading": "OBJETIVO", "source_key": "objetivo"}},
        ],
        "validation": {"critical_tokens": [], "required_sections": [], "min_completeness": 0.7},
    }

    dest = tmp_path / "round-trip"
    await create_preset(
        llm=mock_llm,
        slug="round-trip",
        name="Round Trip",
        template_path=FIXTURES / "template_sample.docx",
        gold_paths=[FIXTURES / "gold_sample_01.docx", FIXTURES / "gold_sample_02.docx"],
        dest_dir=dest,
        owner="user-1",
    )

    bundle = load_preset(dest)
    assert bundle.manifest.slug == "round-trip"
    assert bundle.manifest.owner_sub == "user-1"
    assert bundle.manifest.locked is False
    assert len(bundle.gold_docs_paths) == 2
    assert bundle.render_ops.operations[0].op == "write_section"
