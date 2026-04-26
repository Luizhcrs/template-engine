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
from engine.batch import BatchItemResult, BatchReport, normalize_batch
from engine.confidence import ConfidenceLabel, calculate_confidence, confidence_label
from engine.extractor import ExtractedDoc, extract
from engine.hybrid_mapper import MappingResult, map_hybrid
from engine.hybrid_mapper import summarize as summarize_mapping
from engine.llm_mapper import map_content
from engine.pattern_inference import (
    InferredPattern,
    apply_inferred,
    infer_field_patterns,
)
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
from engine.schema_inference import (
    FieldSchema,
    detect_placeholders,
    enrich_with_llm,
    infer_template_schema,
)
from engine.semantic_diff import (
    Discrepancy,
    diff_documents,
    diff_texts,
    filter_by_severity,
)
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
    "BatchItemResult",
    "BatchReport",
    "ConfidenceLabel",
    "Discrepancy",
    "ExtractedDoc",
    "FieldSchema",
    "HeadingHint",
    "InferredPattern",
    "LayoutFeatures",
    "MappingResult",
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
    "apply_inferred",
    "calculate_confidence",
    "confidence_label",
    "create_preset",
    "detect_layout_features",
    "detect_layout_features_multipage",
    "detect_placeholders",
    "diff_documents",
    "diff_texts",
    "docx_to_png",
    "docx_to_pngs",
    "enrich_with_llm",
    "extract",
    "filter_by_severity",
    "image_to_ascii",
    "infer_field_patterns",
    "infer_template_schema",
    "list_builtin_presets",
    "list_presets_for_owner",
    "list_user_presets",
    "load_preset",
    "map_content",
    "map_hybrid",
    "normalize_batch",
    "render",
    "summarize_layout",
    "summarize_mapping",
    "summarize_multipage",
    "validate",
    "validate_visual",
]
