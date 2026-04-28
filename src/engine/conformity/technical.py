"""Technical dimension — required fields + format validators + zero-orphan-placeholder.

Pure deterministic checks, **zero LLM**. Inputs:

- ``schemas`` — list of :class:`engine.schema_inference.FieldSchema` from the template
- ``mapping`` — output of :func:`engine.hybrid_mapper.map_hybrid` (or empty dict)
- ``candidate_text`` — raw text of the rendered candidate document

Failures emitted:

- ``required_field_missing`` — schema marked required, mapping returned ``missing``
  or absent → ``critical``
- ``invalid_format`` — value present but format validator (CPF/CEP/...) rejects it
  → ``critical`` for typed fields
- ``orphan_placeholder`` — candidate text still contains a ``{{X}}`` / ``[X]`` /
  ``__X__`` token → ``critical``

Format validators implemented:

- ``cpf`` — 11-digit + check digits
- ``cep`` — 8 digits, optional ``-`` separator
- ``iso_date`` — ``YYYY-MM-DD`` parseable as ``date.fromisoformat``
- ``br_date`` — ``DD/MM/YYYY``
- ``email`` — RFC-ish basic check
- ``phone_br`` — 10 or 11 digits, optional formatting
- ``uf`` — 2 uppercase letters of valid Brazilian state
"""

from __future__ import annotations

import re
from datetime import date
from typing import TYPE_CHECKING, Final

import structlog

from engine.conformity.report import DimensionResult, Failure

if TYPE_CHECKING:
    from collections.abc import Callable

    from engine.hybrid_mapper import MappingResult
    from engine.schema_inference import FieldSchema

log = structlog.get_logger(__name__)


_VALID_UFS: Final[frozenset[str]] = frozenset(
    [
        "AC",
        "AL",
        "AM",
        "AP",
        "BA",
        "CE",
        "DF",
        "ES",
        "GO",
        "MA",
        "MG",
        "MS",
        "MT",
        "PA",
        "PB",
        "PE",
        "PI",
        "PR",
        "RJ",
        "RN",
        "RO",
        "RR",
        "RS",
        "SC",
        "SE",
        "SP",
        "TO",
    ]
)


def validate_cpf(value: str) -> bool:
    """Validate Brazilian CPF including check digits."""
    digits = re.sub(r"\D", "", value)
    if len(digits) != 11 or len(set(digits)) == 1:
        return False
    nums = [int(d) for d in digits]
    for k in (9, 10):
        s = sum(nums[i] * (k + 1 - i) for i in range(k))
        check = (s * 10) % 11
        if check == 10:
            check = 0
        if check != nums[k]:
            return False
    return True


def validate_cep(value: str) -> bool:
    digits = re.sub(r"\D", "", value)
    return len(digits) == 8


def validate_iso_date(value: str) -> bool:
    try:
        date.fromisoformat(value.strip())
    except (ValueError, TypeError):
        return False
    return True


def validate_br_date(value: str) -> bool:
    m = re.fullmatch(r"\s*(\d{2})/(\d{2})/(\d{4})\s*", value or "")
    if not m:
        return False
    d, mo, y = (int(x) for x in m.groups())
    try:
        date(y, mo, d)
    except ValueError:
        return False
    return True


def validate_email(value: str) -> bool:
    return re.fullmatch(r"\s*[\w.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\s*", value or "") is not None


def validate_phone_br(value: str) -> bool:
    digits = re.sub(r"\D", "", value or "")
    return len(digits) in (10, 11)


def validate_uf(value: str) -> bool:
    return (value or "").strip().upper() in _VALID_UFS


_VALIDATORS: Final[dict[str, Callable[[str], bool]]] = {
    "cpf": validate_cpf,
    "cep": validate_cep,
    "iso_date": validate_iso_date,
    "br_date": validate_br_date,
    "email": validate_email,
    "phone_br": validate_phone_br,
    "uf": validate_uf,
}


_PLACEHOLDER_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:\{\{\s*[A-Za-z_][A-Za-z0-9_.\-]*\s*\}\}"
    r"|<<\s*[A-Za-z_][A-Za-z0-9_.\-]*\s*>>"
    r"|__[A-Za-z][A-Za-z0-9_.\-]*__"
    r"|\{\s*[A-Za-z_][A-Za-z0-9_.\-]*\s*\}"
    r"|\[\s*[A-Za-z_][A-Za-z0-9_.\-]*\s*\]"
    r"|_{3,})"
)


def find_orphan_placeholders(text: str) -> list[str]:
    """Return the list of tokens that survived rendering."""
    return _PLACEHOLDER_RE.findall(text)


def check_technical(
    schemas: list[FieldSchema],
    mapping: dict[str, MappingResult],
    candidate_text: str,
    *,
    max_acceptable_failures: float = 4.0,
) -> DimensionResult:
    """Run technical dimension. Zero LLM."""
    failures: list[Failure] = []

    # Required fields filled
    for s in schemas:
        if not s.required:
            continue
        result = mapping.get(s.name)
        if result is None or result.source == "missing" or not result.value:
            failures.append(
                Failure(
                    dimension="technical",
                    field_or_excerpt=s.name,
                    expected="filled",
                    actual="missing",
                    severity="critical",
                    note="required field not extracted",
                )
            )

    # Format validators
    for s in schemas:
        validator = _VALIDATORS.get(s.field_type)
        if validator is None:
            continue
        result = mapping.get(s.name)
        if result is None or not result.value:
            continue
        if not validator(result.value):
            failures.append(
                Failure(
                    dimension="technical",
                    field_or_excerpt=s.name,
                    expected=f"valid {s.field_type}",
                    actual=result.value,
                    severity="critical",
                    note="format validator rejected value",
                )
            )

    # Orphan placeholders
    orphans = find_orphan_placeholders(candidate_text)
    if orphans:
        unique_orphans = sorted(set(orphans))
        failures.append(
            Failure(
                dimension="technical",
                field_or_excerpt="orphan_placeholders",
                expected="0",
                actual=str(len(orphans)),
                severity="critical",
                note=f"unsubstituted tokens: {', '.join(unique_orphans[:5])}",
            )
        )

    # Score
    weight = sum(1.0 if f.severity == "critical" else 0.4 for f in failures)
    raw = 1.0 - (weight / max_acceptable_failures)
    score = max(0.0, min(1.0, raw))

    log.info("conformity.technical", score=score, failures=len(failures))
    return DimensionResult(dimension="technical", score=score, failures=failures)
