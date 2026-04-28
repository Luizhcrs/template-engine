"""Text dimension — wraps :mod:`engine.semantic_diff`.

Calls the existing semantic_diff to surface ``missing_in_output`` /
``value_mismatch`` / ``extra_in_output`` discrepancies, then converts them into
a :class:`DimensionResult` with score derived from severity counts.

Score formula:
    1.0 - (1.0 * critical_count + 0.4 * warning_count) / max_acceptable_failures

Clamped to ``[0, 1]``. ``max_acceptable_failures`` defaults to ``5`` (tunable).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import structlog

from engine.conformity.report import DimensionResult, Failure
from engine.semantic_diff import diff_documents, diff_texts

if TYPE_CHECKING:
    from pathlib import Path

    from engine.llm.base import LLMProvider
    from engine.schema_inference import FieldSchema

log = structlog.get_logger(__name__)

_DEFAULT_MAX_ACCEPTABLE_FAILURES: Final[float] = 5.0


def _score_from_severity(critical: int, warning: int, info: int, max_acceptable: float) -> float:
    weighted = 1.0 * critical + 0.4 * warning + 0.0 * info
    raw = 1.0 - (weighted / max_acceptable)
    return max(0.0, min(1.0, raw))


async def check_text(
    template_path: Path,
    candidate_path: Path,
    *,
    llm: LLMProvider | None = None,
    schemas: list[FieldSchema] | None = None,
    max_acceptable_failures: float = _DEFAULT_MAX_ACCEPTABLE_FAILURES,
) -> DimensionResult:
    """Run text dimension via semantic_diff and emit a :class:`DimensionResult`."""
    if llm is None:
        return DimensionResult(
            dimension="text",
            score=1.0,
            failures=[],
            skipped=True,
            skip_reason="no LLM provider supplied",
        )

    discrepancies = await diff_documents(
        template_path,
        candidate_path,
        llm=llm,
        schemas=schemas,
    )

    critical = sum(1 for d in discrepancies if d.severity == "critical")
    warning = sum(1 for d in discrepancies if d.severity == "warning")
    info = sum(1 for d in discrepancies if d.severity == "info")
    score = _score_from_severity(critical, warning, info, max_acceptable_failures)

    failures = [
        Failure(
            dimension="text",
            field_or_excerpt=d.field_or_excerpt,
            expected=d.source_value,
            actual=d.output_value,
            severity=d.severity,
            note=d.note,
        )
        for d in discrepancies
        if d.severity in {"critical", "warning"}
    ]

    log.info("conformity.text", score=score, critical=critical, warning=warning, info=info)
    return DimensionResult(dimension="text", score=score, failures=failures)


async def check_text_pre_extracted(
    template_text: str,
    candidate_text: str,
    *,
    llm: LLMProvider | None = None,
    schemas: list[FieldSchema] | None = None,
    max_acceptable_failures: float = _DEFAULT_MAX_ACCEPTABLE_FAILURES,
) -> DimensionResult:
    """Same as :func:`check_text` but takes already-extracted texts."""
    if llm is None:
        return DimensionResult(
            dimension="text",
            score=1.0,
            failures=[],
            skipped=True,
            skip_reason="no LLM provider supplied",
        )

    discrepancies = await diff_texts(
        template_text,
        candidate_text,
        llm=llm,
        schemas=schemas,
    )

    critical = sum(1 for d in discrepancies if d.severity == "critical")
    warning = sum(1 for d in discrepancies if d.severity == "warning")
    info = sum(1 for d in discrepancies if d.severity == "info")
    score = _score_from_severity(critical, warning, info, max_acceptable_failures)

    failures = [
        Failure(
            dimension="text",
            field_or_excerpt=d.field_or_excerpt,
            expected=d.source_value,
            actual=d.output_value,
            severity=d.severity,
            note=d.note,
        )
        for d in discrepancies
        if d.severity in {"critical", "warning"}
    ]

    return DimensionResult(dimension="text", score=score, failures=failures)
