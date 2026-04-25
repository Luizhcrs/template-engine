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

__version__ = "0.2.0"

__all__ = [
    "__version__",
    "ExtractedDoc",
    "extract",
    "create_preset",
    "load_preset",
    "list_user_presets",
    "list_builtin_presets",
    "PresetBundle",
    "PresetManifest",
    "PresetNotFound",
    "PresetInvalid",
    "RenderOp",
    "RenderOpsFile",
    "ValidationConfig",
    "map_content",
    "validate",
    "ValidationResult",
    "calculate_confidence",
    "confidence_label",
    "ConfidenceLabel",
    "render",
    "RenderError",
]
