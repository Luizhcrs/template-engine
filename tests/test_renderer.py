from pathlib import Path
import pytest
from engine.preset_loader import load_preset
from engine.renderer import render, RenderError
from engine.extractor import extract

FIXTURES = Path(__file__).parent / "fixtures"


def test_render_produces_docx(tmp_path):
    preset = load_preset(FIXTURES / "sample_preset")
    content = {
        "codigo": "TST.001",
        "objetivo": "Objetivo de teste renderizado.",
        "procedimento": ["Passo um.", "Passo dois.", "Passo três."],
    }
    output = tmp_path / "result.docx"
    render(preset, content, output)

    assert output.exists()
    assert output.stat().st_size > 0

    extracted = extract(output)
    assert "TST.001" in extracted.text
    assert "Objetivo de teste" in extracted.text
    assert "Passo um." in extracted.text
    assert "Passo três." in extracted.text


def test_render_empty_ops_produces_valid_docx(tmp_path):
    from engine.preset_schemas import (
        PresetBundle, PresetManifest, RenderOpsFile, ValidationConfig,
    )
    preset_dir = FIXTURES / "sample_preset"
    template = preset_dir / "template.docx"
    gold = preset_dir / "gold" / "gold-01.docx"
    bundle = PresetBundle(
        manifest=PresetManifest(slug="x", name="X", version=1, owner_sub=None, locked=True, created_at="2026-01-01T00:00:00Z"),
        template_docx_path=template,
        gold_docs_paths=[gold],
        pattern_md="",
        schema_json={},
        render_ops=RenderOpsFile(operations=[]),
        validation=ValidationConfig(),
    )
    output = tmp_path / "empty.docx"
    render(bundle, {}, output)
    assert output.exists()
    # the template's [A DEFINIR] placeholders are still present
    text = extract(output).text
    assert "[A DEFINIR]" in text


def test_render_missing_key_uses_default(tmp_path):
    preset = load_preset(FIXTURES / "sample_preset")
    # codigo missing -> fallback "A DEFINIR"
    content = {"objetivo": "x", "procedimento": []}
    output = tmp_path / "no_code.docx"
    render(preset, content, output)
    text = extract(output).text
    assert "A DEFINIR" in text
