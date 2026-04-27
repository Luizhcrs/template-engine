"""Prompt injection detector.

Pattern-based regex check that flags inputs containing instructions aimed at
the LLM ("ignore previous", "respond only with", system-prompt overrides, etc).
The lib is already defensive at the prompt layer (UNTRUSTED delimiters,
explicit "do not follow instructions inside" preamble), but a pre-call detector
adds a second layer for regulated environments where any LLM exposure to
adversarial content needs an audit trail or hard reject.

Modes:

- ``"warn"`` — return matches but do not raise. Caller decides.
- ``"reject"`` — raise :class:`PromptInjectionDetected`.

Patterns are intentionally narrow: false positives on user content are worse
than missed adversarial strings, since this runs on every doc.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

_PATTERNS: Final[list[tuple[str, re.Pattern[str]]]] = [
    (
        "ignore_instructions",
        re.compile(
            r"(?i)\b(?:ignore|disregard|forget)\s+"
            r"(?:(?:all|every|the|previous|prior|above|earlier|original)\s+){1,3}"
            r"(?:instructions?|prompts?|context|messages?|rules?)"
        ),
    ),
    (
        "ignore_instructions_pt",
        re.compile(
            r"(?i)\b(?:ignore|esqueça|desconsidere|despreze)\s+"
            r"(?:(?:as?|todas?|todos?|os?|tudo)\s+)?"
            r"(?:instru[cç][õo]es?|comandos?|regras?|prompts?|mensagens?)"
            r"(?:\s+(?:acima|anteriores|originais?|prévia))?"
        ),
    ),
    (
        "force_response",
        re.compile(
            r"(?i)\b(?:respond|reply|return|output|print|say)\s+"
            r"(?:only|just|exclusively)"
            r"(?:\s+(?:with|using|as))?\s*"
            r"['\"`][^'\"`]{1,40}['\"`]"
        ),
    ),
    (
        "force_response_pt",
        re.compile(
            r"(?i)\b(?:responda|retorne|imprima|escreva|diga)\s+"
            r"(?:apenas|somente|exclusivamente|s[óo])"
            r"(?:\s+(?:com|usando|como))?\s*"
            r"['\"`][^'\"`]{1,40}['\"`]"
        ),
    ),
    (
        "system_override",
        re.compile(
            r"(?i)\b(?:system|admin|root|developer|sudo)\s*[:=]\s*"
            r"['\"`]?(?:override|bypass|disable|jailbreak|new\s+instructions?)"
        ),
    ),
    (
        "role_hijack",
        re.compile(
            r"(?i)\byou\s+are\s+(?:now|actually|really)\s+(?:a|an)\s+\w+"
            r"|\bact\s+as\s+(?:a|an)\s+\w+\s+who"
        ),
    ),
    (
        "delimiter_injection",
        re.compile(
            r"<<<(?:UNTRUSTED|SYSTEM|ADMIN|END|STOP)[A-Z_]*>>>",
            re.IGNORECASE,
        ),
    ),
]


@dataclass(frozen=True)
class InjectionMatch:
    """One pattern hit."""

    rule: str
    snippet: str
    position: int


class PromptInjectionDetected(Exception):
    """Raised by :func:`detect_prompt_injection` when ``mode='reject'``."""

    def __init__(self, matches: list[InjectionMatch]):
        self.matches = matches
        rules = ", ".join({m.rule for m in matches})
        super().__init__(f"prompt injection detected: {rules}")


def detect_prompt_injection(
    text: str,
    *,
    mode: str = "warn",
    extra_patterns: list[tuple[str, re.Pattern[str]]] | None = None,
) -> list[InjectionMatch]:
    """Scan ``text`` for adversarial instructions aimed at the LLM.

    Args:
        text: untrusted input (source doc, user-supplied field).
        mode: ``"warn"`` returns matches; ``"reject"`` raises
            :class:`PromptInjectionDetected` when any match is found.
        extra_patterns: additional ``(rule_name, compiled_pattern)`` entries
            for site-specific rules.

    Returns:
        List of :class:`InjectionMatch`. Empty list = no detection.
    """
    patterns = _PATTERNS + list(extra_patterns or [])
    matches: list[InjectionMatch] = []
    for rule, pattern in patterns:
        for m in pattern.finditer(text):
            matches.append(
                InjectionMatch(
                    rule=rule,
                    snippet=m.group(0)[:80],
                    position=m.start(),
                )
            )

    if matches and mode == "reject":
        raise PromptInjectionDetected(matches)
    return matches
