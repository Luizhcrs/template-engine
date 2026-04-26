from __future__ import annotations

from pathlib import Path  # noqa: TC003 — runtime needed by Pydantic
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class PresetManifest(BaseModel):
    """Preset metadata. ``owner`` is free-form (any string identifying the preset's owner).

    For backwards compatibility (≤ v0.2.0 used ``owner_sub``), reading a manifest with
    ``owner_sub`` populates ``owner`` automatically. New manifests should write ``owner``.
    The ``owner_sub`` alias will be removed in v0.4.
    """

    slug: str
    name: str
    version: int = 1
    owner: str | None = None
    locked: bool = False
    created_at: str
    pattern_last_edited_at: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _accept_owner_sub_alias(cls, data: Any) -> Any:
        """Accept legacy ``owner_sub`` field; promote to ``owner``."""
        if isinstance(data, dict) and "owner" not in data and "owner_sub" in data:
            data = {**data, "owner": data["owner_sub"]}
        return data


class RenderOp(BaseModel):
    op: Literal[
        "set_header_field",
        "write_section",
        "write_list",
        "write_table",
        "write_steps",
        "write_auto_migration",
    ]
    params: dict = Field(default_factory=dict)


class RenderOpsFile(BaseModel):
    operations: list[RenderOp]


class ValidationConfig(BaseModel):
    critical_tokens: list[dict] = Field(default_factory=list)
    required_sections: list[str] = Field(default_factory=list)
    min_completeness: float = 0.7


class PresetBundle(BaseModel):
    """Loaded preset. All paths are absolute; pattern_md and schema_json already parsed."""

    manifest: PresetManifest
    template_docx_path: Path
    gold_docs_paths: list[Path]
    pattern_md: str
    schema_json: dict[str, Any] = Field(  # type: ignore[assignment]
        ...,
        description="Parsed JSON Schema for content extraction (shadows deprecated BaseModel.schema_json)",
    )
    render_ops: RenderOpsFile
    validation: ValidationConfig

    model_config = {"arbitrary_types_allowed": True}
