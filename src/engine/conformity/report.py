"""Conformity report dataclasses.

A :class:`ConformityReport` aggregates :class:`DimensionResult` outcomes from up
to 5 dimensions (text / structural / visual / design / technical) into a single
weighted score and pass/fail verdict.

Each dimension reports its own ``score`` (0-1) and a list of :class:`Failure`
items pinpointing the specific issues. Aggregator computes a weighted average
and compares against ``threshold`` to set ``is_conformant``.

JSON serialization preserves all fields so downstream batch reports can embed
conformity output verbatim.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Failure:
    """One specific non-conformity within a dimension.

    Attributes:
        dimension: which check raised the failure (``text``, ``structural``,
            ``visual``, ``design``, ``technical``).
        field_or_excerpt: schema field name or short excerpt identifying the
            location in the document.
        expected: what the template prescribed.
        actual: what was found in the candidate.
        severity: ``critical`` | ``warning`` | ``info``.
        note: human-readable rationale.
    """

    dimension: str
    field_or_excerpt: str
    expected: str | None
    actual: str | None
    severity: str
    note: str


@dataclass(frozen=True)
class DimensionResult:
    """Per-dimension outcome.

    Attributes:
        dimension: dimension name.
        score: 0-1 (1.0 = perfect conformity).
        failures: list of :class:`Failure` for this dimension.
        skipped: ``True`` if the dimension was opted out or required input
            (e.g. LLM provider) was missing. Skipped dimensions get
            ``score=1.0`` and an empty failure list to avoid penalizing the
            overall report.
        skip_reason: free-text explanation when ``skipped=True``.
    """

    dimension: str
    score: float
    failures: list[Failure] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str | None = None

    @property
    def passed(self) -> bool:
        """True when score is exactly 1.0 (no failures)."""
        return self.score >= 1.0


@dataclass(frozen=True)
class ConformityReport:
    """Aggregate report over multiple dimensions.

    Attributes:
        score: weighted average of per-dimension scores (0-1).
        threshold: cutoff used to set :attr:`is_conformant`.
        is_conformant: ``score >= threshold``.
        by_dimension: mapping from dimension name to :class:`DimensionResult`.
        weights: weights used in the aggregation.
        failures: flattened list across all dimensions (convenience).
    """

    score: float
    threshold: float
    is_conformant: bool
    by_dimension: dict[str, DimensionResult]
    weights: dict[str, float]
    failures: list[Failure] = field(default_factory=list)

    @property
    def critical_failures(self) -> list[Failure]:
        return [f for f in self.failures if f.severity == "critical"]

    @property
    def summary_line(self) -> str:
        """One-line human-readable verdict."""
        verdict = "CONFORMANT" if self.is_conformant else "NON_CONFORMANT"
        return (
            f"{verdict} score={self.score:.2f} threshold={self.threshold:.2f} "
            f"failures={len(self.failures)} "
            f"(critical={len(self.critical_failures)})"
        )

    def to_dict(self) -> dict:
        """JSON-serializable view."""
        return {
            "score": self.score,
            "threshold": self.threshold,
            "is_conformant": self.is_conformant,
            "summary": self.summary_line,
            "weights": self.weights,
            "by_dimension": {
                name: {
                    "dimension": dr.dimension,
                    "score": dr.score,
                    "passed": dr.passed,
                    "skipped": dr.skipped,
                    "skip_reason": dr.skip_reason,
                    "failures": [asdict(f) for f in dr.failures],
                }
                for name, dr in self.by_dimension.items()
            },
            "failures": [asdict(f) for f in self.failures],
        }
