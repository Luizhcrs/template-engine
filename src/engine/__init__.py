"""template-engine: document normalization engine.

Pipeline: extractor -> preset_creator -> llm_mapper -> validator -> renderer
"""

from __future__ import annotations

from engine.confidence import ConfidenceLabel, calculate_confidence, confidence_label
from engine.extractor import ExtractedDoc, extract
from engine.llm_mapper import map_content
from engine.preset_creator import create_preset
from engine.preset_loader import (
    PresetInvalid,
    PresetNotFound,
    list_builtin_presets,
    list_presets_for_owner,
    list_user_presets,
    load_preset,
)
from engine.preset_schemas import (
    PresetBundle,
    PresetManifest,
    RenderOp,
    RenderOpsFile,
    ValidationConfig,
)
from engine.renderer import RenderError, render
from engine.validator import ValidationResult, validate
from engine.visual_validator import (
    VisualIssue,
    VisualValidationResult,
    docx_to_png,
    validate_visual,
)

__version__ = "0.3.0a1"

__all__ = [
    "ConfidenceLabel",
    "ExtractedDoc",
    "PresetBundle",
    "PresetInvalid",
    "PresetManifest",
    "PresetNotFound",
    "RenderError",
    "RenderOp",
    "RenderOpsFile",
    "ValidationConfig",
    "ValidationResult",
    "VisualIssue",
    "VisualValidationResult",
    "__version__",
    "calculate_confidence",
    "confidence_label",
    "create_preset",
    "docx_to_png",
    "extract",
    "list_builtin_presets",
    "list_presets_for_owner",
    "list_user_presets",
    "load_preset",
    "map_content",
    "render",
    "validate",
    "validate_visual",
]
