"""Auto-detect empty tables in a template and synthesize sensible defaults.

Industrial templates ship a few canonical empty tables that 90% of users
will fill the same way:

- ``Histórico de Revisões`` (``Rev. | Data | Alteração``) — first row
  defaults to ``"00"`` / today / ``"Emissão inicial"``.
- ``Atribuições e Responsabilidades`` (``Atividades | Responsabilidade``)
  — left empty unless caller supplies rows.

The orchestrator wires this in when the caller doesn't pass ``table_specs``,
so a brand-new template-source pair gets sensible output without manual
configuration.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from engine.section_mapper.table_filler import TableSpec

if TYPE_CHECKING:
    from pathlib import Path


def _normalize(text: str) -> str:
    nkfd = unicodedata.normalize("NFKD", text)
    no_accent = "".join(c for c in nkfd if not unicodedata.combining(c))
    return re.sub(r"[^A-Z0-9 ]+", " ", no_accent.upper()).strip()


def _today_iso() -> str:
    return datetime.now(UTC).date().isoformat()


_HISTORICO_HEADERS: frozenset[str] = frozenset({"REV", "DATA", "ALTERACAO"})


def detect_default_specs(template_path: Path) -> list[TableSpec]:
    """Walk template tables and synthesize a default :class:`TableSpec` per
    canonical empty table found.
    """
    from docx import Document

    doc = Document(str(template_path))
    specs: list[TableSpec] = []

    for table in doc.tables:
        if not table.rows:
            continue
        header = {_normalize(c.text) for c in table.rows[0].cells if c.text.strip()}
        if not header:
            continue

        # Histórico de Revisões / Rev | Data | Alteração
        if header >= _HISTORICO_HEADERS:
            specs.append(
                TableSpec(
                    headers=[c.text.strip() for c in table.rows[0].cells],
                    rows=[
                        {
                            "Rev.": "00",
                            "Rev": "00",
                            "Data": _today_iso(),
                            "Alteração": "Emissão inicial",
                            "Alteracao": "Emissão inicial",
                        }
                    ],
                )
            )

    return specs


def merge_specs(
    auto: list[TableSpec],
    user: list[TableSpec] | None,
) -> list[TableSpec]:
    """User-supplied specs win over auto-detected ones with the same headers."""
    if not user:
        return auto

    user_keys = [{_normalize(h) for h in sp.headers} for sp in user]
    out = list(user)
    for auto_spec in auto:
        auto_key = {_normalize(h) for h in auto_spec.headers}
        if auto_key in user_keys:
            continue
        out.append(auto_spec)
    return out


__all__ = ["detect_default_specs", "merge_specs"]


# Suppress unused import warning when called from the package
_ = date
