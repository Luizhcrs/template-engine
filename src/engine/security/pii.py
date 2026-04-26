"""PII masking — replace personal identifiers with reversible tokens before LLM calls.

Detects Brazilian CPF / CNPJ / email / phone / RG / CEP and substitutes each
unique occurrence with a token like ``<CPF_001>``. The mapping is preserved so
the caller can restore real values into the LLM response.

Why reversible (not just redaction): downstream code may need the original
value back (e.g., the LLM extracted ``<CPF_001>`` as the doc's main field —
caller wants the actual CPF in the final output, not the placeholder).

Usage::

    masked, mask = mask_pii(source_text)
    llm_response = await llm.generate_structured(prompt(masked), schema)
    final = unmask(llm_response_str, mask)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Final


@dataclass(frozen=True)
class _Detector:
    name: str
    pattern: re.Pattern[str]


_PATTERNS: Final[list[_Detector]] = [
    _Detector(
        name="CPF",
        pattern=re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b|\b\d{11}\b"),
    ),
    _Detector(
        name="CNPJ",
        pattern=re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b|\b\d{14}\b"),
    ),
    _Detector(
        name="EMAIL",
        pattern=re.compile(r"\b[\w.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    ),
    _Detector(
        name="PHONE",
        # Brazilian: (DD) 9XXXX-XXXX or 10/11 plain digits. Avoid clobbering CPF/CNPJ
        # by requiring formatting cues (parentheses or +55) when not in a 10/11 raw block.
        pattern=re.compile(r"\(\d{2}\)\s?9?\d{4,5}-\d{4}|\+55\s?\d{2}\s?9?\d{4,5}-?\d{4}"),
    ),
    _Detector(
        name="RG",
        # Common Brazilian RG formats: 12.345.678-9, 12.345.678-X, 12345678 (8-9 digits + opt check digit).
        pattern=re.compile(r"\b\d{1,2}\.\d{3}\.\d{3}-[\dXx]\b"),
    ),
    _Detector(
        name="CEP",
        pattern=re.compile(r"\b\d{5}-\d{3}\b"),
    ),
]


@dataclass(frozen=True)
class PIIMask:
    """Reversible mapping ``{token -> original_value}``.

    Use :meth:`unmask` to substitute tokens back in any text (typically an LLM
    response).
    """

    mapping: dict[str, str] = field(default_factory=dict)

    def unmask(self, text: str) -> str:
        """Replace every ``<TYPE_NNN>`` token in *text* with the original value."""
        if not self.mapping:
            return text
        out = text
        # Sort by token length desc to avoid prefix collisions.
        for token in sorted(self.mapping, key=len, reverse=True):
            out = out.replace(token, self.mapping[token])
        return out

    def types_seen(self) -> dict[str, int]:
        """Counts of masked items per detector name (debug)."""
        counts: dict[str, int] = {}
        for token in self.mapping:
            kind = token.strip("<>").rsplit("_", 1)[0]
            counts[kind] = counts.get(kind, 0) + 1
        return counts


def mask_pii(text: str) -> tuple[str, PIIMask]:
    """Return ``(masked_text, PIIMask)``.

    Each unique original value gets a single token (``<CPF_001>``). Repeated
    occurrences of the same value reuse the same token. Detection order matters
    — longer/more-specific patterns (CNPJ before CPF, etc) run first.
    """
    counters: dict[str, int] = {}
    seen: dict[str, str] = {}  # original -> token
    masked = text

    for det in _PATTERNS:

        def repl(m: re.Match[str], _name: str = det.name) -> str:
            original = m.group(0)
            if original in seen:
                return seen[original]
            counters[_name] = counters.get(_name, 0) + 1
            token = f"<{_name}_{counters[_name]:03d}>"
            seen[original] = token
            return token

        masked = det.pattern.sub(repl, masked)

    mask = PIIMask(mapping={tok: orig for orig, tok in seen.items()})
    return masked, mask


def unmask(text: str, mask: PIIMask) -> str:
    """Convenience wrapper around :meth:`PIIMask.unmask`."""
    return mask.unmask(text)
