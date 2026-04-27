"""template-engine: document normalization engine.

Pipeline: extractor -> schema_inference -> hybrid_mapper -> batch -> semantic_diff
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
from engine.conformity import (
    ConformityReport,
    ConformityVisualProvider,
    DimensionResult,
    Failure,
    StructuralFingerprint,
    check_conformity,
    check_design,
    check_structural,
    check_technical,
    check_text,
    check_visual,
    find_orphan_placeholders,
    validate_br_date,
    validate_cep,
    validate_cpf,
    validate_email,
    validate_iso_date,
    validate_phone_br,
    validate_uf,
)
from engine.extractor import ExtractedDoc, extract
from engine.formats import (
    Format,
    FormatNotFound,
    describe_formats,
    list_formats,
    load_format,
)
from engine.hybrid_mapper import MappingResult, map_hybrid
from engine.hybrid_mapper import summarize as summarize_mapping
from engine.pattern_inference import (
    InferredPattern,
    apply_inferred,
    infer_field_patterns,
)
from engine.schema_inference import (
    FieldSchema,
    detect_placeholders,
    enrich_with_llm,
    infer_template_schema,
)
from engine.security import (
    AuditLog,
    InjectionMatch,
    PIIMask,
    PromptInjectionDetected,
    RefusedRemoteCallError,
    detect_prompt_injection,
    mask_pii,
    sha256_hex,
    unmask,
)
from engine.semantic_diff import (
    Discrepancy,
    diff_documents,
    diff_texts,
    filter_by_severity,
)

__version__ = "0.7.0"

__all__ = [
    "AuditLog",
    "BatchItemResult",
    "BatchReport",
    "ConfidenceLabel",
    "ConformityReport",
    "ConformityVisualProvider",
    "DimensionResult",
    "Discrepancy",
    "ExtractedDoc",
    "Failure",
    "FieldSchema",
    "Format",
    "FormatNotFound",
    "HeadingHint",
    "InferredPattern",
    "InjectionMatch",
    "LayoutFeatures",
    "MappingResult",
    "MultiPageLayoutFeatures",
    "PIIMask",
    "PlaceholderHint",
    "PromptInjectionDetected",
    "RefusedRemoteCallError",
    "SectionBreak",
    "StructuralFingerprint",
    "TableHint",
    "__version__",
    "apply_inferred",
    "calculate_confidence",
    "check_conformity",
    "check_design",
    "check_structural",
    "check_technical",
    "check_text",
    "check_visual",
    "confidence_label",
    "describe_formats",
    "detect_layout_features",
    "detect_layout_features_multipage",
    "detect_placeholders",
    "detect_prompt_injection",
    "diff_documents",
    "diff_texts",
    "enrich_with_llm",
    "extract",
    "filter_by_severity",
    "find_orphan_placeholders",
    "image_to_ascii",
    "infer_field_patterns",
    "infer_template_schema",
    "list_formats",
    "load_format",
    "map_hybrid",
    "mask_pii",
    "normalize_batch",
    "sha256_hex",
    "summarize_layout",
    "summarize_mapping",
    "summarize_multipage",
    "unmask",
    "validate_br_date",
    "validate_cep",
    "validate_cpf",
    "validate_email",
    "validate_iso_date",
    "validate_phone_br",
    "validate_uf",
]
