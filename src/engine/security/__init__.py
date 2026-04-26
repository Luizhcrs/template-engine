"""Security primitives for regulated deployments (Wave G).

- :mod:`engine.security.pii` — reversible PII masking before LLM calls.
- :mod:`engine.security.injection` — prompt-injection regex detector.
- :mod:`engine.security.audit` — append-only structured audit log.
- :mod:`engine.security.local_only` — :class:`RefusedRemoteCallError` for
  enforcing "no LLM" mode.

See ``SECURITY-MODEL.md`` for the threat model + provider data residency table.
"""

from __future__ import annotations

from engine.security.audit import AuditLog, sha256_hex
from engine.security.injection import (
    InjectionMatch,
    PromptInjectionDetected,
    detect_prompt_injection,
)
from engine.security.local_only import RefusedRemoteCallError
from engine.security.pii import PIIMask, mask_pii, unmask

__all__ = [
    "AuditLog",
    "InjectionMatch",
    "PIIMask",
    "PromptInjectionDetected",
    "RefusedRemoteCallError",
    "detect_prompt_injection",
    "mask_pii",
    "sha256_hex",
    "unmask",
]
