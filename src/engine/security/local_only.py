"""Local-only enforcement — refuse to call any LLM when ``local_only=True``.

Used by :func:`engine.batch.normalize_batch` and
:func:`engine.conformity.check_conformity`. When the flag is set:

- LLM provider, if supplied, is ignored (treated as ``None``).
- Any code path that would have triggered an LLM call instead raises
  :class:`RefusedRemoteCallError`.

Justification: regulated deployments (LGPD/HIPAA/internal data sovereignty)
need a hard guarantee that no document content leaves the host. Trusting that
"omitting the provider" is enough is fragile — a future code path could re-add
LLM calls. The explicit flag + exception class makes the policy auditable.
"""

from __future__ import annotations


class RefusedRemoteCallError(Exception):
    """Raised when ``local_only=True`` and a remote LLM call would occur."""

    def __init__(self, what: str):
        super().__init__(
            f"local_only=True: refused {what}. Either omit the LLM call or set local_only=False to opt in."
        )
