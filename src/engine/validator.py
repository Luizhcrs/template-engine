from __future__ import annotations
import re
from dataclasses import dataclass
from engine.preset_schemas import ValidationConfig


@dataclass
class ValidationResult:
    ok: bool
    critical_tokens_total: int
    critical_tokens_found: int
    sections_required: int
    sections_present: int
    critical_tokens_missing: list[str]
    sections_missing: list[str]


def _extract_tokens(text: str, regex: str) -> list[str]:
    try:
        return re.findall(regex, text)
    except re.error:
        return []


def _content_to_text(content: dict) -> str:
    parts: list[str] = []

    def walk(v):
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, list):
            for item in v:
                walk(item)
        elif isinstance(v, dict):
            for val in v.values():
                walk(val)

    walk(content)
    return " ".join(parts)


def validate(source_text: str, content: dict, config: ValidationConfig) -> ValidationResult:
    """Verify that all critical tokens from source appear in content,
    and all required sections are populated."""
    content_text = _content_to_text(content)
    critical_missing: list[str] = []
    total_crit = 0
    found_crit = 0

    for token_cfg in config.critical_tokens:
        regex = token_cfg.get("regex")
        if not regex:
            continue
        matches = set(_extract_tokens(source_text, regex))
        for m in matches:
            total_crit += 1
            if m in content_text:
                found_crit += 1
            else:
                critical_missing.append(m)

    sec_missing = [k for k in config.required_sections if k not in content or not content[k]]

    ok = (found_crit == total_crit) and (len(sec_missing) == 0)

    return ValidationResult(
        ok=ok,
        critical_tokens_total=total_crit,
        critical_tokens_found=found_crit,
        sections_required=len(config.required_sections),
        sections_present=len(config.required_sections) - len(sec_missing),
        critical_tokens_missing=critical_missing,
        sections_missing=sec_missing,
    )
