from __future__ import annotations
import json
from pathlib import Path
import yaml
from engine.preset_schemas import (
    PresetBundle, PresetManifest, RenderOpsFile, ValidationConfig,
)


class PresetNotFound(Exception):
    pass


class PresetInvalid(Exception):
    pass


def load_preset(preset_dir: Path) -> PresetBundle:
    if not preset_dir.exists():
        raise PresetNotFound(str(preset_dir))

    manifest_path = preset_dir / "manifest.json"
    if not manifest_path.exists():
        raise PresetInvalid("manifest.json ausente")
    manifest = PresetManifest(**json.loads(manifest_path.read_text(encoding="utf-8")))

    template = preset_dir / "template.docx"
    if not template.exists():
        raise PresetInvalid("template.docx ausente")

    gold_dir = preset_dir / "gold"
    golds = sorted(gold_dir.glob("*.docx")) if gold_dir.exists() else []
    if not golds:
        raise PresetInvalid("preset precisa de pelo menos 1 gold doc")

    pattern_path = preset_dir / "pattern.md"
    pattern_md = pattern_path.read_text(encoding="utf-8") if pattern_path.exists() else ""

    schema_path = preset_dir / "schema.json"
    if not schema_path.exists():
        raise PresetInvalid("schema.json ausente")
    schema_json = json.loads(schema_path.read_text(encoding="utf-8"))

    ops_path = preset_dir / "render_ops.yaml"
    if not ops_path.exists():
        raise PresetInvalid("render_ops.yaml ausente")
    render_ops = RenderOpsFile(**yaml.safe_load(ops_path.read_text(encoding="utf-8")))

    validation_path = preset_dir / "validation.yaml"
    validation = ValidationConfig()
    if validation_path.exists():
        validation = ValidationConfig(**yaml.safe_load(validation_path.read_text(encoding="utf-8")))

    return PresetBundle(
        manifest=manifest,
        template_docx_path=template,
        gold_docs_paths=golds,
        pattern_md=pattern_md,
        schema_json=schema_json,
        render_ops=render_ops,
        validation=validation,
    )


def list_user_presets(data_dir: Path, user_sub: str) -> list[Path]:
    base = data_dir / "presets" / user_sub
    if not base.exists():
        return []
    return [p for p in base.iterdir() if p.is_dir() and (p / "manifest.json").exists()]


def list_builtin_presets(repo_root: Path) -> list[Path]:
    base = repo_root / "presets"
    if not base.exists():
        return []
    return [p for p in base.iterdir() if p.is_dir() and (p / "manifest.json").exists()]
