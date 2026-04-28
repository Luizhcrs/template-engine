"""Format dataclass — common shape for every pre-defined format."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.schema_inference import FieldSchema


@dataclass(frozen=True)
class Format:
    """A pre-defined document format ready to feed the pipeline.

    Attributes:
        name: short id (``"abnt_tcc"``).
        title: human-readable name (``"ABNT NBR 14724 - TCC"``).
        description: one-paragraph summary.
        spec: identifier of the standard (``"ABNT NBR 14724"``).
        schemas: :class:`FieldSchema` list with the fields this format expects.
        field_examples: ``{field_name: [example_values]}`` for
            :func:`engine.pattern_inference.infer_field_patterns`.
        gold_docs: 3 text variants used by pattern inference. Same structure,
            different values per variant.
        conformity_weights: per-dimension weight overrides for
            :func:`engine.conformity.check_conformity`. Defaults are biased
            toward the dimensions that matter for the format (e.g. structural
            and technical for laudo_nr12; structural and text for ABNT TCC).
        required_headings: list of canonical headings the candidate must
            contain. Used by the ``structural`` dimension as a sanity check.
        recommended_threshold: per-format conformity threshold (default 0.85).
    """

    name: str
    title: str
    description: str
    spec: str
    schemas: list[FieldSchema]
    field_examples: dict[str, list[str]]
    gold_docs: list[str]
    conformity_weights: dict[str, float] = field(default_factory=dict)
    required_headings: list[str] = field(default_factory=list)
    recommended_threshold: float = 0.85
