"""Conformity validator.

LLM-as-judge multi-dimensional check: does the candidate document conform to
the template's standard? Five dimensions:

- ``text`` — wraps :mod:`engine.semantic_diff` (LLM)
- ``structural`` — python-docx parsing (no LLM)
- ``visual`` — synthetic-render + ascii_layout fingerprint compare (no LLM)
- ``design`` — multimodal LLM compare via :class:`ConformityVisualProvider` (LLM)
- ``technical`` — required fields + format validators + zero-orphan-placeholder (no LLM)

Top-level entry: :func:`check_conformity`.
"""

from __future__ import annotations

from engine.conformity.aggregator import (
    ALL_DIMENSIONS,
    DEFAULT_THRESHOLD,
    DEFAULT_WEIGHTS,
    check_conformity,
)
from engine.conformity.design import ConformityVisualProvider, check_design
from engine.conformity.report import ConformityReport, DimensionResult, Failure
from engine.conformity.structural import (
    StructuralFingerprint,
    check_structural,
    diff_fingerprints,
    fingerprint,
)
from engine.conformity.technical import (
    check_technical,
    find_orphan_placeholders,
    validate_br_date,
    validate_cep,
    validate_cpf,
    validate_email,
    validate_iso_date,
    validate_phone_br,
    validate_uf,
)
from engine.conformity.text import check_text, check_text_pre_extracted
from engine.conformity.visual import check_visual

__all__ = [
    "ALL_DIMENSIONS",
    "DEFAULT_THRESHOLD",
    "DEFAULT_WEIGHTS",
    "ConformityReport",
    "ConformityVisualProvider",
    "DimensionResult",
    "Failure",
    "StructuralFingerprint",
    "check_conformity",
    "check_design",
    "check_structural",
    "check_technical",
    "check_text",
    "check_text_pre_extracted",
    "check_visual",
    "diff_fingerprints",
    "find_orphan_placeholders",
    "fingerprint",
    "validate_br_date",
    "validate_cep",
    "validate_cpf",
    "validate_email",
    "validate_iso_date",
    "validate_phone_br",
    "validate_uf",
]
