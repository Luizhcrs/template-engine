"""Pattern inference — synthesize regex automatically from gold docs + field examples.

Replaces hardcoded ``_FIELD_PATTERNS`` dicts in POCs with mechanical inference.

Algorithm (3-tier shape detection):

1. **Locate examples** in gold docs (substring match, anchored by ``: <example>``).
2. **Extract label context**: text immediately before each match. Looks for "Label:" pattern.
3. **Aggregate label variants** across docs (e.g. "Nome:", "Nome completo:", "Responsavel:").
4. **Infer value shape** — three tiers, first match wins:

   a. **Pre-defined shapes**: ISO date, doc code, CPF, CEP, UF, fullname, etc.
      Fast, well-tested, gives readable regex.
   b. **grex-learned shape** (optional, grex Tier 2): when no pre-defined shape fits,
      ``grex.RegExpBuilder`` learns a regex from the examples (digits→\\d, alternations).
      Much better than ``[^\\n]+`` for structured but unrecognized values.
   c. **Free-text fallback**: ``[^\\n]+`` when neither tier produces a valid match.

5. **Compose regex**: ``(?:label_alt_1|label_alt_2|...):\\s*(value_shape)``.

Limitations:

- Only works when label uses ``Label:`` syntax (or close variants).
- ``grex`` is optional — install with ``pip install template-engine[inference]``.
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
        re.compile(r"[A-Z][a-z]+(?:[ \t]+(?:da|de|do|dos|das|e|von|van)?[ \t]*[A-Z][a-z]+)+"),
        r"[A-Z][a-z]+(?:[ \t]+(?:da|de|do|dos|das|e|von|van)?[ \t]*[A-Z][a-z]+)+",
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


def _grex_available() -> bool:
    """Lazy probe for the optional ``grex`` dependency."""
    try:
        import grex  # noqa: F401

        return True
    except ImportError:
        return False


def _grex_learn(examples: list[str]) -> str | None:
    """Use grex to learn a regex from examples.

    Returns a regex fragment (no anchors, no capture group) suitable for embedding
    in the final composed regex. Returns ``None`` if grex is not installed or the
    learned pattern is overly literal (just an alternation of full strings).
    """
    if not _grex_available():
        return None

    import grex

    try:
        # Try two builds:
        #   1. digits-only conversion → preserves literal letters
        #   2. digits + words conversion → also generalizes letter alternations
        # Pick #2 only when it still has STRUCTURAL ANCHORS (literal hyphen,
        # space, or ``\d``). Otherwise it collapses to a permissive ``\w+``
        # which matches arbitrary text and ruins extraction precision.
        b_digits = grex.RegExpBuilder.from_test_cases(examples).without_anchors().with_conversion_of_digits()
        digits_only = b_digits.build()

        b_words = (
            grex.RegExpBuilder.from_test_cases(examples)
            .without_anchors()
            .with_conversion_of_digits()
            .with_conversion_of_words()
        )
        with_words = b_words.build()

        learned = with_words if _has_structural_anchors(with_words) else digits_only
    except Exception as exc:
        log.warning("pattern_inference.grex_failed", examples=examples, error=str(exc))
        return None

    # Reject pure literal alternations like ``(?:foo|bar|baz)`` — they don't
    # generalize and ``[^\n]+`` is more useful in that case.
    if learned and not _has_meta_class(learned):
        return None

    return learned


def _has_meta_class(regex: str) -> bool:
    """True iff regex contains any generalizing meta class (\\d, \\w, [AB], etc)."""
    if r"\d" in regex or r"\w" in regex or r"\s" in regex:
        return True
    # Bracket char class like [AB], [a-z]
    return bool(re.search(r"(?<!\\)\[[^\]]+\]", regex))


def _has_structural_anchors(regex: str) -> bool:
    """True iff regex still has literal punctuation or digit-class anchors.

    Used to decide whether grex's ``with_conversion_of_words()`` over-generalized.
    A regex like ``\\w\\w-\\d\\d-\\w`` has anchors (``-`` separators, ``\\d``);
    ``\\w\\w\\w`` does not — it would match any 3-letter token.

    Whitespace alone is NOT considered a structural anchor: ``\\w\\w\\w \\w\\w``
    matches any two-word phrase and is too permissive for labeled extraction.
    """
    has_punctuation = bool(re.search(r"\\[\-./()_:;,]", regex))
    has_digits = r"\d" in regex
    return has_punctuation or has_digits


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
    """Find first known shape that matches ALL examples.

    Tier 1: Pre-defined shapes (iso_date, doc_code, cpf, ...).
    Tier 2: grex-learned shape (optional dep, generalizes via digit conversion).
    Tier 3: ``[^\\n]+`` free-text fallback.

    Returns (shape_name, regex_fragment).
    """
    # Tier 1
    for name, pattern, fragment in _VALUE_SHAPES:
        if all(pattern.fullmatch(ex) for ex in examples):
            return name, fragment

    # Tier 2 — only attempt grex when examples look structured (no spaces or
    # short enough to suggest a code-like value). Free-text fields skip grex.
    if all(len(ex) <= 30 and "\n" not in ex for ex in examples):
        learned = _grex_learn(examples)
        if learned:
            # Validate the learned regex actually matches every example.
            try:
                compiled = re.compile(learned)
                if all(compiled.fullmatch(ex) for ex in examples):
                    return "grex_learned", learned
            except re.error as exc:
                log.warning(
                    "pattern_inference.grex_invalid_regex",
                    pattern=learned,
                    error=str(exc),
                )

    # Tier 3
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

        # 1. Find each example in gold docs, collect label contexts.
        # Require the example to be preceded by ": " (colon + whitespace) and
        # followed by a word/line boundary — avoids spurious matches when the
        # example is a short substring of unrelated content (e.g. "A" inside
        # "LAUDO").
        # Map example[i] -> gold_docs[i] when possible. This 1-1 alignment
        # blocks cross-field label leakage: if example 2 of field PMTA happens
        # to also appear in gold doc 0 under a different label
        # (e.g. PRESSAO), we never look at doc 0 when processing example 2.
        labels: list[str] = []
        for i, ex in enumerate(examples):
            ex_pattern = re.compile(rf":\s*{re.escape(ex)}(?=\s|$|[.,;)])")
            docs_to_search = [gold_docs[i]] if i < len(gold_docs) else gold_docs
            for doc in docs_to_search:
                for m in ex_pattern.finditer(doc):
                    # value start = where the example actually begins in the doc
                    value_start = m.end() - len(ex)
                    label = _extract_label_before(doc, value_start)
                    if label:
                        labels.append(label)
                    break  # one label per (example, doc) pair is enough

        unique_labels = _aggregate_labels(labels)

        # 2. Infer value shape
        shape_name, shape_regex = _detect_value_shape(examples)

        # 3. Compose regex
        # Distinctive shapes can be searched by shape alone because their
        # syntax is unique enough to avoid collisions (CPF won't match a
        # phone number once the bare-digit alternative is gone, ISO dates
        # don't match anything else, CEP is dash-tagged, etc).
        # Permissive shapes (fullname, doc_code, integer, version,
        # decimal_br, br_date, freetext, grex_learned) MUST have a label
        # anchor — otherwise they would happily match the institution name
        # when looking for an author, the document title when looking for a
        # conclusion, etc.
        _DISTINCTIVE_SHAPES = {"cpf", "cnpj", "iso_date", "cep", "uf"}
        if unique_labels:
            label_alt = "|".join(re.escape(label) for label in unique_labels)
            pattern_str = rf"(?:{label_alt}):\s*({shape_regex})"
        elif shape_name in _DISTINCTIVE_SHAPES:
            pattern_str = rf"({shape_regex})"
        else:
            # Refuse to compile a pattern that would silently match the wrong
            # value. Caller sees coverage=0 and source="missing" downstream
            # so the LLM tier or a manual review can take over.
            log.warning(
                "pattern_inference.no_label_freetext_refused",
                field=field,
                shape=shape_name,
            )
            inferred[field] = InferredPattern(
                field=field,
                label_variants=[],
                value_shape_name=shape_name,
                regex=re.compile(r"(?!.*)"),  # never matches
                coverage=0.0,
            )
            continue

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
