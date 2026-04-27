"""Pre-defined document formats (Wave H).

Ready-made schemas, field examples, gold docs, and conformity weights for
common document standards. Use ``load_format(name)`` to get a :class:`Format`,
or ``list_formats()`` for the registry.

Bundled formats:

- ``abnt_artigo`` - ABNT NBR 6022 (artigo cientifico)
- ``abnt_tcc`` - ABNT NBR 14724 (TCC, dissertacao, tese)
- ``abnt_referencia`` - ABNT NBR 6023 (referencias bibliograficas)
- ``abnt_relatorio_tecnico`` - ABNT NBR 10719 (relatorio tecnico-cientifico)
- ``laudo_nr12`` - NR-12 (laudo de seguranca em maquinas)
- ``nr13`` - NR-13 (caldeiras e vasos de pressao)
- ``nr35`` - NR-35 (permissao de trabalho em altura)
- ``ata_reuniao`` - ata de reuniao corporativa generica
- ``contrato_simples`` - contrato bilateral generico
- ``procuracao_simples`` - procuracao por instrumento particular

Adding a new format: drop a module under ``engine/formats/`` exposing a
``FORMAT`` constant of type :class:`Format`, then add it to the ``_REGISTRY``
dict below.
"""

from __future__ import annotations

from engine.formats import (
    abnt_artigo,
    abnt_referencia,
    abnt_relatorio_tecnico,
    abnt_tcc,
    ata_reuniao,
    contrato_simples,
    laudo_nr12,
    nr13,
    nr35,
    procuracao_simples,
)
from engine.formats._base import Format

_REGISTRY: dict[str, Format] = {
    abnt_artigo.FORMAT.name: abnt_artigo.FORMAT,
    abnt_tcc.FORMAT.name: abnt_tcc.FORMAT,
    abnt_referencia.FORMAT.name: abnt_referencia.FORMAT,
    abnt_relatorio_tecnico.FORMAT.name: abnt_relatorio_tecnico.FORMAT,
    laudo_nr12.FORMAT.name: laudo_nr12.FORMAT,
    nr13.FORMAT.name: nr13.FORMAT,
    nr35.FORMAT.name: nr35.FORMAT,
    ata_reuniao.FORMAT.name: ata_reuniao.FORMAT,
    contrato_simples.FORMAT.name: contrato_simples.FORMAT,
    procuracao_simples.FORMAT.name: procuracao_simples.FORMAT,
}


class FormatNotFound(KeyError):
    """Raised by :func:`load_format` when the requested name is unknown."""


def list_formats() -> list[str]:
    """Return the names of all bundled formats, sorted."""
    return sorted(_REGISTRY)


def load_format(name: str) -> Format:
    """Return the :class:`Format` registered under *name*.

    Raises:
        FormatNotFound: when *name* is not in the registry.
    """
    if name not in _REGISTRY:
        available = ", ".join(list_formats())
        raise FormatNotFound(f"unknown format {name!r}. Available: {available}")
    return _REGISTRY[name]


def describe_formats() -> list[dict]:
    """Return a serializable list with one entry per format.

    Useful for CLI output (``template-engine list-formats``) and JSON exports.
    """
    return [
        {
            "name": fmt.name,
            "title": fmt.title,
            "spec": fmt.spec,
            "fields": [s.name for s in fmt.schemas],
            "required_headings": fmt.required_headings,
            "recommended_threshold": fmt.recommended_threshold,
        }
        for fmt in (_REGISTRY[k] for k in list_formats())
    ]


__all__ = [
    "Format",
    "FormatNotFound",
    "describe_formats",
    "list_formats",
    "load_format",
]
