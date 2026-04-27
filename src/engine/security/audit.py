"""Audit log — append-only structured log for regulated environments.

Each entry is a JSON object with a fixed schema. Hashes (sha256) are recorded
for inputs / outputs so reviewers can prove a document was processed without
the log carrying the raw content (privacy-preserving).

Append-only semantics: ``log_event()`` opens the file in append mode and writes
one JSON line per event (JSON Lines format). No update / delete primitives
exposed — operators rotate or sign the file externally.

Schema fields:

- ``ts`` — ISO 8601 UTC timestamp
- ``event`` — short event name (``hybrid_mapper.llm_call``, ``conformity.text``, etc)
- ``doc_hash`` — sha256 of the source/candidate document text (hex)
- ``dimension`` — conformity dimension or pipeline stage (optional)
- ``source`` — ``regex`` / ``llm`` / ``missing`` for hybrid_mapper events
- ``llm_provider`` — provider name when LLM was invoked
- ``llm_model`` — model id
- ``fields_touched`` — list of schema field names processed
- ``llm_input_hash`` — sha256 of the prompt (when LLM was called)
- ``llm_output_hash`` — sha256 of the LLM response (when LLM was called)
- ``extra`` — caller-defined dict of extra metadata (no PII)
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import IO, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path


def sha256_hex(text: str | bytes) -> str:
    """Return the sha256 hex digest of *text*."""
    if isinstance(text, str):
        text = text.encode("utf-8")
    return hashlib.sha256(text).hexdigest()


@dataclass
class AuditLog:
    """Append-only JSON-Lines audit log.

    Thread-safe: a per-instance lock serializes writes. Not multi-process safe;
    use one log file per process or wrap in OS-level file locking.

    Pass ``path=None`` to keep the log in memory (useful for tests).
    """

    path: Path | None = None
    _events: list[dict] = field(default_factory=list, compare=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, compare=False, repr=False)
    _fp: IO[str] | None = field(default=None, compare=False, repr=False, init=False)

    def __post_init__(self) -> None:
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._fp = self.path.open("a", encoding="utf-8")

    def __del__(self) -> None:
        # Defensive close — long-running servers that forget `with` would leak
        # the file descriptor otherwise. Swallow any error during shutdown.
        with contextlib.suppress(Exception):
            self.close()

    def log_event(
        self,
        event: str,
        *,
        doc_hash: str | None = None,
        dimension: str | None = None,
        source: str | None = None,
        llm_provider: str | None = None,
        llm_model: str | None = None,
        fields_touched: list[str] | None = None,
        llm_input_hash: str | None = None,
        llm_output_hash: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict:
        """Append one event. Returns the recorded dict (for tests / chaining)."""
        record: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "event": event,
        }
        for key, value in (
            ("doc_hash", doc_hash),
            ("dimension", dimension),
            ("source", source),
            ("llm_provider", llm_provider),
            ("llm_model", llm_model),
            ("fields_touched", fields_touched),
            ("llm_input_hash", llm_input_hash),
            ("llm_output_hash", llm_output_hash),
        ):
            if value is not None:
                record[key] = value
        if extra:
            record["extra"] = extra

        with self._lock:
            self._events.append(record)
            if self._fp is not None:
                self._fp.write(json.dumps(record, ensure_ascii=False) + "\n")
                self._fp.flush()

        return record

    def events(self) -> list[dict]:
        """Snapshot copy of all events recorded so far."""
        with self._lock:
            return list(self._events)

    def close(self) -> None:
        if self._fp is not None:
            self._fp.close()
            self._fp = None

    def __enter__(self) -> AuditLog:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
