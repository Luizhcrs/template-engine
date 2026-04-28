"""Heuristic header-based schema detector.

Given a docx table's row 0 (the header strings), pick the
:class:`TableSchema` whose column names align best, or ``None`` when
no builtin schema is a confident match. The matcher is deliberately
strict — a wrong match cascades through extraction + alignment and
produces garbage. Better to fall through to the legacy slot pipeline
than to mis-classify.
"""

from __future__ import annotations

import re
import unicodedata
from typing import TYPE_CHECKING

from engine.section_mapper.schemas.builtins import BUILTIN_SCHEMAS

if TYPE_CHECKING:
    from engine.section_mapper.schemas.types import TableSchema


_PUNCT_RE = re.compile(r"[^\w\s]")
_WHITESPACE_RE = re.compile(r"\s+")


def _normalise(text: str) -> str:
    """Lowercase, strip accents, drop punctuation, collapse spaces.
    ``E-mail`` / ``Email`` / ``e-mail`` all collapse to ``email``."""
    nfkd = unicodedata.normalize("NFKD", text)
    no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    no_punct = _PUNCT_RE.sub(" ", no_accents.lower())
    return _WHITESPACE_RE.sub(" ", no_punct).strip()


_HEADER_ALIASES: dict[str, set[str]] = {
    "no": {"no", "n", "num", "numero"},
    "nome": {"nome", "name"},
    "telefone": {"telefone", "tel", "phone", "fone"},
    "email": {"email", "e mail", "mail"},
    "versao": {"versao", "version", "ver"},
    "data": {"data", "date"},
    "descricao das mudancas": {"descricao das mudancas", "descricao", "mudancas", "description"},
    "requisitado por": {"requisitado por", "requisitado", "solicitante"},
    "setor": {"setor", "departamento", "unidade", "sector"},
    "funcao": {"funcao", "cargo", "role", "function"},
    "atividade": {"atividade", "activity"},
}


def _canonical_for(header: str) -> str:
    """Map a single header string to its canonical form via the alias
    table. Falls back to the normalised string if no alias matches."""
    norm = _normalise(header)
    for canon, aliases in _HEADER_ALIASES.items():
        if norm in aliases or norm == canon:
            return canon
    return norm


def detect_table_schema(headers: list[str]) -> TableSchema | None:
    """Return the :class:`TableSchema` whose column names match
    *headers* (column-count + canonical-name parity required), or
    ``None`` if no builtin schema is a confident match."""
    if not headers or all(not h.strip() for h in headers):
        return None

    canon_headers = [_canonical_for(h) for h in headers]

    for schema in BUILTIN_SCHEMAS:
        if len(schema.columns) != len(canon_headers):
            continue
        canon_schema = [_canonical_for(c.name) for c in schema.columns]
        if canon_schema == canon_headers:
            return schema

    return None


__all__ = [
    "detect_table_schema",
]
