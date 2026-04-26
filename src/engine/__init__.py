"""template-engine: document normalization engine.

Pipeline: extractor -> preset_creator -> llm_mapper -> validator -> renderer
"""

from __future__ import annotations

from engine.ascii_layout import (
    HeadingHint,
    LayoutFeatures,
    MultiPageLayoutFeatures,
    PlaceholderHint,
    SectionBreak,
    TableHint,
    detect_layout_features,
    detect_layout_features_multipage,
    image_to_ascii,
    summarize_layout,
    summarize_multipage,
)
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
    docx_to_pngs,
    validate_visual,
)

__version__ = "0.3.0a1"

__all__ = [
    "ConfidenceLabel",
    "ExtractedDoc",
    "HeadingHint",
    "LayoutFeatures",
    "MultiPageLayoutFeatures",
    "PlaceholderHint",
    "PresetBundle",
    "PresetInvalid",
    "PresetManifest",
    "PresetNotFound",
    "RenderError",
    "RenderOp",
    "RenderOpsFile",
    "SectionBreak",
    "TableHint",
    "ValidationConfig",
    "ValidationResult",
    "VisualIssue",
    "VisualValidationResult",
    "__version__",
    "calculate_confidence",
    "confidence_label",
    "create_preset",
    "detect_layout_features",
    "detect_layout_features_multipage",
    "docx_to_png",
    "docx_to_pngs",
    "extract",
    "image_to_ascii",
    "list_builtin_presets",
    "list_presets_for_owner",
    "list_user_presets",
    "load_preset",
    "map_content",
    "render",
    "summarize_layout",
    "summarize_multipage",
    "validate",
    "validate_visual",
]
