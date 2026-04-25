from __future__ import annotations
import json
import re
from pathlib import Path
import yaml
from engine.preset_schemas import (
    PresetBundle, PresetManifest, RenderOpsFile, ValidationConfig,
)


class PresetNotFound(Exception):
    pass


class PresetInvalid(Exception):
    pass


_SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _validate_safe_id(value: str, field_name: str) -> None:
    if not _SAFE_ID_RE.match(value):
        raise ValueError(
            f"{field_name} inválido: deve casar com [a-zA-Z0-9_-]{{1,64}}, recebido {value!r}"
        )


def _ensure_within(child: Path, base: Path) -> Path:
    """Resolve and assert child is contained within base. Defends path traversal."""
    child_resolved = child.resolve()
    base_resolved = base.resolve()
    if not child_resolved.is_relative_to(base_resolved):
        raise ValueError(f"path escapa do base: {child} não está dentro de {base}")
    return child_resolved


def load_preset(preset_dir: Path) -> PresetBundle:
    preset_dir = Path(preset_dir).resolve()
    if not preset_dir.exists():
        raise PresetNotFound(str(preset_dir))
    if not preset_dir.is_dir():
        raise PresetInvalid(f"não é diretório: {preset_dir}")

    manifest_path = preset_dir / "manifest.json"
    if not manifest_path.exists():
        raise PresetInvalid("manifest.json ausente")
    manifest = PresetManifest(**json.loads(manifest_path.read_text(encoding="utf-8")))

    template = preset_dir / "template.docx"
    if not template.exists():
        raise PresetInvalid("template.docx ausente")

    gold_dir = preset_dir / "gold"
    golds: list[Path] = []
    if gold_dir.exists():
        golds = sorted(p for p in gold_dir.iterdir() if p.suffix.lower() == ".docx")
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
    """List preset dirs for a user. Validates user_sub against safe regex and prevents path traversal."""
    _validate_safe_id(user_sub, "user_sub")
    data_dir = Path(data_dir).resolve()
    base = (data_dir / "presets" / user_sub).resolve()
    _ensure_within(base, data_dir)
    if not base.exists():
        return []
    return [p for p in base.iterdir() if p.is_dir() and (p / "manifest.json").exists()]


def list_builtin_presets(repo_root: Path) -> list[Path]:
    """List built-in preset dirs at repo_root/presets/."""
    repo_root = Path(repo_root).resolve()
    base = (repo_root / "presets").resolve()
    _ensure_within(base, repo_root)
    if not base.exists():
        return []
    return [p for p in base.iterdir() if p.is_dir() and (p / "manifest.json").exists()]
