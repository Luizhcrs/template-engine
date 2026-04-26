"""Conformity aggregator — top-level :func:`check_conformity` (Wave F).

Drives all 5 dimensions, collects per-dimension scores, computes a weighted
overall score, and returns a :class:`ConformityReport` with the pass/fail
verdict.

Dimensions can be opted in/out via the ``dimensions`` list. Skipped dimensions
contribute ``score=1.0`` (no penalty) and are noted in the report.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

import structlog

from engine.conformity.design import check_design
from engine.conformity.report import ConformityReport, DimensionResult
from engine.conformity.structural import check_structural
from engine.conformity.technical import check_technical
from engine.conformity.text import check_text
from engine.conformity.visual import check_visual

if TYPE_CHECKING:
    from pathlib import Path

    from engine.conformity.design import ConformityVisualProvider
    from engine.hybrid_mapper import MappingResult
    from engine.llm.base import LLMProvider
    from engine.schema_inference import FieldSchema

log = structlog.get_logger(__name__)


ALL_DIMENSIONS: Final[tuple[str, ...]] = (
    "text",
    "structural",
    "visual",
    "design",
    "technical",
)

DEFAULT_WEIGHTS: Final[dict[str, float]] = {
    "text": 0.30,
    "structural": 0.20,
    "visual": 0.15,
    "design": 0.15,
    "technical": 0.20,
}

DEFAULT_THRESHOLD: Final[float] = 0.85


def _aggregate_score(by_dim: dict[str, DimensionResult], weights: dict[str, float]) -> float:
    total_weight = sum(weights.get(name, 0.0) for name in by_dim)
    if total_weight == 0:
        return 0.0
    weighted = sum(by_dim[name].score * weights.get(name, 0.0) for name in by_dim)
    return round(weighted / total_weight, 4)


async def check_conformity(
    template_path: Path,
    candidate_path: Path,
    *,
    llm: LLMProvider | None = None,
    visual_llm: ConformityVisualProvider | None = None,
    schemas: list[FieldSchema] | None = None,
    mapping: dict[str, MappingResult] | None = None,
    candidate_text: str | None = None,
    dimensions: list[str] | None = None,
    weights: dict[str, float] | None = None,
    threshold: float = DEFAULT_THRESHOLD,
) -> ConformityReport:
    """Compute a multi-dimensional conformity report.

    Args:
        template_path: ``.docx`` template (gold standard).
        candidate_path: ``.docx`` candidate to evaluate.
        llm: text LLM provider for the ``text`` dimension.
        visual_llm: multimodal provider for the ``design`` dimension.
        schemas: list of :class:`FieldSchema` used by ``text`` + ``technical``.
        mapping: pre-computed :class:`MappingResult` dict (from
            :func:`engine.hybrid_mapper.map_hybrid`). Required for ``technical``.
        candidate_text: pre-extracted candidate text (used for orphan placeholder
            check in ``technical``). Falls back to extractor if omitted.
        dimensions: subset of :data:`ALL_DIMENSIONS` to evaluate (default: all).
        weights: per-dimension weight (default: :data:`DEFAULT_WEIGHTS`).
        threshold: pass/fail cutoff (default: 0.85).
    """
    dims = list(dimensions) if dimensions else list(ALL_DIMENSIONS)
    w = {**DEFAULT_WEIGHTS, **(weights or {})}

    by_dim: dict[str, DimensionResult] = {}

    if "text" in dims:
        by_dim["text"] = await check_text(template_path, candidate_path, llm=llm, schemas=schemas)

    if "structural" in dims:
        by_dim["structural"] = check_structural(template_path, candidate_path)

    if "visual" in dims:
        by_dim["visual"] = check_visual(template_path, candidate_path)

    if "design" in dims:
        by_dim["design"] = await check_design(template_path, candidate_path, visual_llm=visual_llm)

    if "technical" in dims:
        if schemas is None or mapping is None:
            by_dim["technical"] = DimensionResult(
                dimension="technical",
                score=1.0,
                skipped=True,
                skip_reason="schemas + mapping required (pass them or skip dimension)",
            )
        else:
            if candidate_text is None:
                from engine.extractor import extract

                candidate_text = extract(candidate_path).text
            by_dim["technical"] = check_technical(
                schemas=schemas,
                mapping=mapping,
                candidate_text=candidate_text,
            )

    score = _aggregate_score(by_dim, w)
    flat_failures = [f for dr in by_dim.values() for f in dr.failures]
    has_critical = any(f.severity == "critical" for f in flat_failures)

    # Conformidade exige score acima do threshold E zero failures críticos.
    # Um único critical (CPF inválido, orphan placeholder, info perdida)
    # invalida o doc independente da média ponderada.
    is_conformant = (score >= threshold) and not has_critical

    report = ConformityReport(
        score=score,
        threshold=threshold,
        is_conformant=is_conformant,
        by_dimension=by_dim,
        weights={name: w[name] for name in by_dim if name in w},
        failures=flat_failures,
    )
    log.info(
        "conformity.aggregate",
        score=score,
        threshold=threshold,
        is_conformant=report.is_conformant,
        failures=len(flat_failures),
        dimensions=list(by_dim.keys()),
    )
    return report
