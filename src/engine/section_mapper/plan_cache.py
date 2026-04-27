"""File-based cache for :class:`MappingPlan` keyed by template + source.

Same template + source pair → same plan, no LLM call. Useful when:

- The same template is filled with hundreds of different source
  documents (cache hits per template = cheap; per source = paying).
- A pipeline re-runs after fixing a downstream step — the LLM call
  cost is already paid.

Cache key: ``sha256(template_bytes) + sha256(source_bytes) + prompt
version tag``. Prompt version bumps invalidate the cache when the
prompt changes shape.

Storage: JSON file under ``$XDG_CACHE_HOME/template-engine/plans/`` (or
``~/.cache/template-engine/plans/`` fallback). One JSON file per cache
entry.

Thread-safe at the file level via temp-write + atomic rename.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from engine.section_mapper.auto_mapper import MappingPlan


log = structlog.get_logger(__name__)


# Prompt-version tag — bump when the prompt or schema changes so old
# plans don't get re-used incorrectly.
PROMPT_VERSION = "v1"


@dataclass(frozen=True)
class CacheKey:
    template_hash: str
    source_hash: str
    prompt_version: str = PROMPT_VERSION

    @property
    def filename(self) -> str:
        return f"{self.template_hash[:16]}_{self.source_hash[:16]}_{self.prompt_version}.json"


def hash_file(path: Path) -> str:
    """SHA-256 of the file's bytes, hex-encoded."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def cache_key_for(template_path: Path, source_path: Path) -> CacheKey:
    return CacheKey(
        template_hash=hash_file(template_path),
        source_hash=hash_file(source_path),
    )


def _cache_dir() -> Path:
    """Resolve the cache directory.

    Honors ``$TEMPLATE_ENGINE_CACHE_DIR`` first (so callers can pin a
    specific path in tests / CI), then ``$XDG_CACHE_HOME``, finally the
    POSIX default ``~/.cache`` (also works on Windows via ``Path.home()``).
    """
    override = os.environ.get("TEMPLATE_ENGINE_CACHE_DIR")
    if override:
        d = Path(override)
    else:
        xdg = os.environ.get("XDG_CACHE_HOME")
        d = Path(xdg) if xdg else Path.home() / ".cache"
        d = d / "template-engine" / "plans"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_plan(key: CacheKey) -> MappingPlan | None:
    """Return a cached :class:`MappingPlan` or ``None`` on miss."""
    from engine.section_mapper.auto_mapper import (
        MappingPlan,
        ParagraphRewrite,
        TableFillData,
    )

    path = _cache_dir() / key.filename
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("section_mapper.plan_cache.read_failed", path=str(path), error=str(exc))
        return None

    return MappingPlan(
        header_substitutions=dict(raw.get("header_substitutions") or {}),
        section_content=dict(raw.get("section_content") or {}),
        table_data=[
            TableFillData(
                template_table_index=int(t["template_table_index"]),
                sub_headers=[str(s) for s in t.get("sub_headers", [])],
                rows=[
                    {str(k): str(v) for k, v in row.items()}
                    for row in t.get("rows", [])
                    if isinstance(row, dict)
                ],
            )
            for t in raw.get("table_data") or []
            if isinstance(t, dict)
        ],
        paragraph_rewrites=[
            ParagraphRewrite(
                match_text=str(r["match_text"]),
                replacement_text=str(r["replacement_text"]),
            )
            for r in raw.get("paragraph_rewrites") or []
            if isinstance(r, dict)
        ],
    )


def save_plan(key: CacheKey, plan: MappingPlan) -> None:
    """Persist *plan* under *key*. Atomic-replace if a previous file exists."""
    path = _cache_dir() / key.filename
    payload = json.dumps(plan.to_dict(), ensure_ascii=False, indent=2)

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        delete=False,
        dir=str(path.parent),
        suffix=".tmp",
    ) as tmp:
        tmp.write(payload)
        tmp_path = Path(tmp.name)
    try:
        shutil.move(str(tmp_path), str(path))
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


__all__ = [
    "PROMPT_VERSION",
    "CacheKey",
    "cache_key_for",
    "hash_file",
    "load_plan",
    "save_plan",
]
