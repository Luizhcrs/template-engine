from pathlib import Path

import pytest

from engine.preset_loader import PresetInvalid, PresetNotFound, load_preset

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_valid_preset():
    bundle = load_preset(FIXTURES / "sample_preset")
    assert bundle.manifest.slug == "sample"
    assert bundle.template_docx_path.exists()
    assert len(bundle.gold_docs_paths) == 1
    assert "Padrão de teste" in bundle.pattern_md
    assert "codigo" in bundle.schema_json["properties"]
    assert bundle.render_ops.operations[0].op == "set_header_field"


def test_load_missing_dir_raises():
    with pytest.raises(PresetNotFound):
        load_preset(FIXTURES / "does_not_exist")


def test_load_invalid_preset_missing_manifest(tmp_path):
    (tmp_path / "template.docx").touch()
    with pytest.raises(PresetInvalid):
        load_preset(tmp_path)
