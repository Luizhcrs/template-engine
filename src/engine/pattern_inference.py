"""Pattern inference — synthesize regex automatically from gold docs + field examples.

Replaces hardcoded ``_FIELD_PATTERNS`` dicts in POCs with mechanical inference.

Algorithm (deliberately simple, no grex/LearnLib dependency):

1. **Locate examples** in gold docs (substring match).
2. **Extract label context**: text immediately before each match. Looks for "Label:" pattern.
3. **Aggregate label variants** across docs (e.g. "Nome:", "Nome completo:", "Responsavel:").
4. **Infer value shape** by checking shared structural patterns across all examples
   (date YYYY-MM-DD, code A-9, fullname, integer, etc).
5. **Compose regex**: ``(?:label_alt_1|label_alt_2|...):\\s*(value_shape)``.

Limitations:

- Only works when label uses ``Label:`` syntax (or close variants).
- Free-text fields fall back to ``[^\\n]+`` (greedy single-line).
- No probabilistic generalization (grex would do better).

Future work: integrate ``grex`` lib for learned-from-strings regex (Wave A v2).
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Final

import structlog

log = structlog.get_logger(__name__)

# How many chars before a match to consider as "label context"
_LABEL_CONTEXT_CHARS: Final[int] = 60

# Max distinct labels to alternate in the inferred regex (avoid bloat)
_MAX_LABEL_ALTERNATES: Final[int] = 6

# Pre-known value shapes — checked in order; first match wins.
# Each entry: (name, full-match regex used to test, regex fragment to embed)
_VALUE_SHAPES: list[tuple[str, re.Pattern, str]] = [
    ("iso_date", re.compile(r"\d{4}-\d{2}-\d{2}"), r"\d{4}-\d{2}-\d{2}"),
    ("br_date", re.compile(r"\d{2}/\d{2}/\d{4}"), r"\d{2}/\d{2}/\d{4}"),
    ("doc_code", re.compile(r"[A-Z]+-\d+(?:-\d+)*"), r"[A-Z]+-\d+(?:-\d+)*"),
    ("cpf", re.compile(r"\d{3}\.\d{3}\.\d{3}-\d{2}"), r"\d{3}\.\d{3}\.\d{3}-\d{2}"),
    ("cep", re.compile(r"\d{5}-\d{3}"), r"\d{5}-\d{3}"),
    ("uf", re.compile(r"[A-Z]{2}"), r"[A-Z]{2}"),
    ("decimal_br", re.compile(r"\d{1,3}(?:\.\d{3})*,\d{2}"), r"\d{1,3}(?:\.\d{3})*,\d{2}"),
    ("integer", re.compile(r"\d+"), r"\d+"),
    ("version", re.compile(r"\d+\.\d+(?:\.\d+)?"), r"\d+\.\d+(?:\.\d+)?"),
    (
        "fullname",
        re.compile(r"[A-Z][a-z]+(?:\s+(?:da|de|do|dos|das|e|von|van)?\s*[A-Z][a-z]+)+"),
        r"[A-Z][a-z]+(?:\s+(?:da|de|do|dos|das|e|von|van)?\s*[A-Z][a-z]+)+",
    ),
    (
        "month_year_pt",
        re.compile(
            r"(?:janeiro|fevereiro|marco|abril|maio|junho|julho|agosto|"
            r"setembro|outubro|novembro|dezembro)/\d{4}",
            re.I,
        ),
        r"(?:janeiro|fevereiro|marco|abril|maio|junho|julho|agosto|"
        r"setembro|outubro|novembro|dezembro)/\d{4}",
    ),
]

# Ultimate fallback when nothing else fits
_FALLBACK_SHAPE: Final[str] = r"[^\n]+"


@dataclass(frozen=True)
class InferredPattern:
    """Result of inferring a regex for one field."""

    field: str
    label_variants: list[str]
    value_shape_name: str
    regex: re.Pattern
    coverage: float  # 0-1: fraction of examples the inferred regex actually matches


def _extract_label_before(text: str, match_start: int) -> str | None:
    """Look at the chars before match_start, find last 'Label:' before it.

    Returns the cleaned label text (without trailing colon) or None.
    """
    start = max(0, match_start - _LABEL_CONTEXT_CHARS)
    prefix = text[start:match_start]
    # Find last colon
    if ":" not in prefix:
        return None
    before_colon, _ = prefix.rsplit(":", 1)
    # Take last line of before_colon
    label_line = before_colon.rsplit("\n", 1)[-1].strip()
    if not label_line or len(label_line) > 50:
        return None
    return label_line


def _detect_value_shape(examples: list[str]) -> tuple[str, str]:
    """Find first known shape that matches ALL examples. Returns (shape_name, regex_fragment)."""
    for name, pattern, fragment in _VALUE_SHAPES:
        if all(pattern.fullmatch(ex) for ex in examples):
            return name, fragment
    return "freetext", _FALLBACK_SHAPE


def _aggregate_labels(labels: list[str]) -> list[str]:
    """Dedupe + rank labels by frequency. Returns top N most common."""
    if not labels:
        return []
    counter = Counter(labels)
    return [label for label, _ in counter.most_common(_MAX_LABEL_ALTERNATES)]


def infer_field_patterns(
    gold_docs: list[str],
    field_examples: dict[str, list[str]],
) -> dict[str, InferredPattern]:
    """Synthesize a regex per field from gold doc texts and known field examples.

    Args:
        gold_docs: list of text content extracted from gold-standard documents.
        field_examples: mapping of ``field_name -> [example_value_1, example_value_2, ...]``.
            Examples must appear literally in at least one gold doc.

    Returns:
        Mapping ``field_name -> InferredPattern`` with compiled regex + diagnostics.
    """
    inferred: dict[str, InferredPattern] = {}

    for field, examples in field_examples.items():
        if not examples:
            log.warning("pattern_inference.no_examples", field=field)
            continue

        # 1. Find each example in gold docs, collect label contexts
        labels: list[str] = []
        for ex in examples:
            for doc in gold_docs:
                idx = 0
                while True:
                    pos = doc.find(ex, idx)
                    if pos == -1:
                        break
                    label = _extract_label_before(doc, pos)
                    if label:
                        labels.append(label)
                    idx = pos + len(ex)

        unique_labels = _aggregate_labels(labels)

        # 2. Infer value shape
        shape_name, shape_regex = _detect_value_shape(examples)

        # 3. Compose regex
        if unique_labels:
            label_alt = "|".join(re.escape(label) for label in unique_labels)
            pattern_str = rf"(?:{label_alt}):\s*({shape_regex})"
        else:
            # No label context found — search for value-shape only (less reliable)
            pattern_str = rf"({shape_regex})"

        compiled = re.compile(pattern_str, re.IGNORECASE)

        # 4. Coverage check: fraction of examples actually matched by the regex
        # 4. Coverage check: re-run inferred regex on golds, count how many examples appear
        coverage_count = 0
        for ex in examples:
            found = False
            for doc in gold_docs:
                for m in compiled.finditer(doc):
                    if m.group(1).strip() == ex.strip():
                        found = True
                        break
                if found:
                    break
            if found:
                coverage_count += 1
        coverage = coverage_count / len(examples) if examples else 0.0

        inferred[field] = InferredPattern(
            field=field,
            label_variants=unique_labels,
            value_shape_name=shape_name,
            regex=compiled,
            coverage=round(coverage, 3),
        )

        log.info(
            "pattern_inference.done",
            field=field,
            labels=unique_labels,
            shape=shape_name,
            coverage=coverage,
            pattern=pattern_str,
        )

    return inferred


def apply_inferred(
    inferred: dict[str, InferredPattern],
    text: str,
) -> dict[str, str]:
    """Apply inferred patterns to a new text. Returns ``{field: extracted_value}``."""
    result: dict[str, str] = {}
    for field, ip in inferred.items():
        m = ip.regex.search(text)
        if m:
            result[field] = m.group(1).strip()
    return result
