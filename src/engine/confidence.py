from __future__ import annotations
from enum import Enum
from engine.validator import ValidationResult


class ConfidenceLabel(str, Enum):
    """Confidence tier derived from a 0-1 score."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


def calculate_confidence(result: ValidationResult, min_completeness: float = 0.7) -> float:
    """Score 0.0-1.0 derived from tokens + section completeness.

    Weights: 60% critical tokens, 40% required sections.
    """
    if result.critical_tokens_total == 0:
        tok_score = 1.0
    else:
        tok_score = result.critical_tokens_found / result.critical_tokens_total

    if result.sections_required == 0:
        sec_score = 1.0
    else:
        sec_score = result.sections_present / result.sections_required

    score = 0.6 * tok_score + 0.4 * sec_score
    return round(score, 3)


def confidence_label(score: float) -> ConfidenceLabel:
    """Categorize a confidence score 0-1 into a tier (HIGH/MEDIUM/LOW).

    Returns enum so callers control display strings/i18n.
    """
    if score >= 0.9:
        return ConfidenceLabel.HIGH
    if score >= 0.7:
        return ConfidenceLabel.MEDIUM
    return ConfidenceLabel.LOW
