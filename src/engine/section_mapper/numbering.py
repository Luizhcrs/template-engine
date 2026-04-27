"""Resolve docx auto-numbering (``<w:numPr>``) into rendered markers.

Word's numbering is computed at render time from ``word/numbering.xml``:
each ``<w:numId>`` points at an ``<w:abstractNumId>`` whose per-``<w:ilvl>``
entry carries a ``numFmt`` (``decimal`` / ``lowerLetter`` / ``bullet`` /
...) and a ``lvlText`` template (``"%1."``, ``"%1.%2.%3."``, ``"•"``).

When we extract paragraph text via ``python-docx``, the text only carries
what the author typed — the marker (``"1."``, ``"5.2.1."``, ``"a)"``,
``"•"``) is missing because Word renders it from the numbering tree.

This module reads the numbering tree once, then exposes a stateful
``NumberingResolver`` that walks paragraphs and returns the rendered
marker for each ``<w:numPr>``-bound paragraph. Counter state is per
``numId``; advancing one level resets all deeper levels.

Faithful to numFmt (no heuristics):

- ``decimal``      — Arabic counter (``1``, ``2``, ``3``)
- ``lowerLetter``  — ``a``, ``b``, ``c`` (cycles ``z`` -> ``aa`` Excel-style)
- ``upperLetter``  — ``A``, ``B``, ``C``
- ``lowerRoman``   — ``i``, ``ii``, ``iii``
- ``upperRoman``   — ``I``, ``II``, ``III``
- ``bullet``       — single-char ``"•"`` regardless of source glyph
- anything else    — single-char ``"•"`` (defensive)

DOcStream-style heuristics (e.g. rendering Wingdings bullets as ``a.``,
``b.``) are deliberately out of scope for the faithful path; callers who
want that can post-process.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


@dataclass(frozen=True)
class _LevelDef:
    ilvl: int
    num_fmt: str
    lvl_text: str
    start: int


@dataclass
class NumberingResolver:
    """Stateful numbering renderer keyed by ``numId``.

    Build via :func:`load_resolver_from_docx`; then call
    :meth:`marker_for` once per paragraph (in document order) to advance
    counters and get the rendered marker (or ``""`` when the paragraph has
    no ``<w:numPr>``).

    ``bullet_as_letters`` (default ``True``) is an Engeman-style
    heuristic: bullets at ilvl=0 of any list whose source glyph is a
    Wingdings/Symbol-style placeholder render as Excel-style letters
    (``a.``, ``b.``, ``c.``, ...). Set ``False`` for faithful rendering
    that emits ``"•"`` for every bullet level. Higher ilvls (sub-bullets)
    always render as ``"•"`` regardless of this flag.
    """

    # numId -> {ilvl -> _LevelDef}
    _levels: dict[int, dict[int, _LevelDef]] = field(default_factory=dict)
    # numId -> {ilvl -> current_count}
    _counters: dict[int, dict[int, int]] = field(default_factory=dict)
    bullet_as_letters: bool = True

    def has_num(self, num_id: int) -> bool:
        return num_id in self._levels

    def reset_bullet_counters(self) -> None:
        """Reset every bullet-format counter back to ``start - 1``.

        Engeman-style heuristic: when a structural decimal heading
        advances, lettered bullet sequences should restart so each
        sub-section gets its own ``a.``-``z.`` run.
        """
        for num_id, levels in self._levels.items():
            for ilvl, lvl in levels.items():
                if lvl.num_fmt != "bullet":
                    continue
                self._counters.setdefault(num_id, {})[ilvl] = lvl.start - 1

    def marker_for(self, num_id: int, ilvl: int) -> str:
        """Advance counter for ``(num_id, ilvl)`` and return rendered marker."""
        marker, _ = self.marker_with_fmt(num_id, ilvl)
        return marker

    def marker_with_fmt(self, num_id: int, ilvl: int) -> tuple[str, str]:
        """Like :meth:`marker_for` but also returns the source ``numFmt``.

        Returns ``(marker, num_fmt)`` where ``num_fmt`` is the original
        format declared in ``numbering.xml`` (``"bullet"``, ``"decimal"``,
        ``"lowerLetter"``, ...). Useful for callers who need to know if
        the marker is bullet-origin even when ``bullet_as_letters`` made
        it look lettered.

        Side-effect: increments ``counters[num_id][ilvl]`` and resets
        every deeper level back to its ``start - 1``.
        """
        levels = self._levels.get(num_id)
        if levels is None:
            return "", ""
        lvl = levels.get(ilvl)
        if lvl is None:
            return "", ""

        counters = self._counters.setdefault(num_id, {})
        for k, v in levels.items():
            counters.setdefault(k, v.start - 1)

        counters[ilvl] = counters[ilvl] + 1
        for deeper in list(counters.keys()):
            if deeper > ilvl:
                deeper_lvl = levels.get(deeper)
                counters[deeper] = (deeper_lvl.start - 1) if deeper_lvl else 0

        marker = _render_marker(
            lvl,
            counters,
            levels,
            bullet_as_letters=self.bullet_as_letters,
        )
        return marker, lvl.num_fmt


def load_resolver_from_docx(path: Path) -> NumberingResolver:
    """Read ``word/numbering.xml`` from *path* and build a resolver.

    Returns an empty resolver (``has_num`` always ``False``) when the
    file is missing — fine for docs without auto-numbering.
    """
    try:
        with zipfile.ZipFile(str(path)) as z:
            try:
                raw = z.read("word/numbering.xml").decode("utf-8")
            except KeyError:
                return NumberingResolver()
    except zipfile.BadZipFile:
        return NumberingResolver()

    return _build_resolver(raw)


def _build_resolver(numbering_xml: str) -> NumberingResolver:
    abstracts = _parse_abstracts(numbering_xml)
    num_to_abstract = _parse_num_to_abstract(numbering_xml)

    levels: dict[int, dict[int, _LevelDef]] = {}
    for num_id, abstract_id in num_to_abstract.items():
        a = abstracts.get(abstract_id)
        if a is None:
            continue
        levels[num_id] = a
    return NumberingResolver(_levels=levels)


_ABSTRACT_BLOCK_RE = re.compile(
    r'<w:abstractNum w:abstractNumId="(\d+)"[^>]*>(.*?)</w:abstractNum>',
    re.DOTALL,
)
_LEVEL_BLOCK_RE = re.compile(
    r'<w:lvl w:ilvl="(\d+)"[^>]*>(.*?)</w:lvl>',
    re.DOTALL,
)
_FMT_RE = re.compile(r'<w:numFmt w:val="([^"]+)"')
_LVL_TEXT_RE = re.compile(r'<w:lvlText w:val="([^"]*)"')
_START_RE = re.compile(r'<w:start w:val="(\d+)"')
_NUM_TO_ABSTRACT_RE = re.compile(
    r'<w:num w:numId="(\d+)"[^>]*>.*?<w:abstractNumId w:val="(\d+)"',
    re.DOTALL,
)


def _parse_abstracts(xml: str) -> dict[int, dict[int, _LevelDef]]:
    out: dict[int, dict[int, _LevelDef]] = {}
    for abs_id, body in _ABSTRACT_BLOCK_RE.findall(xml):
        per_lvl: dict[int, _LevelDef] = {}
        for ilvl, lvl_body in _LEVEL_BLOCK_RE.findall(body):
            fmt = _FMT_RE.search(lvl_body)
            txt = _LVL_TEXT_RE.search(lvl_body)
            start = _START_RE.search(lvl_body)
            per_lvl[int(ilvl)] = _LevelDef(
                ilvl=int(ilvl),
                num_fmt=(fmt.group(1) if fmt else "decimal"),
                lvl_text=(txt.group(1) if txt else ""),
                start=(int(start.group(1)) if start else 1),
            )
        out[int(abs_id)] = per_lvl
    return out


def _parse_num_to_abstract(xml: str) -> dict[int, int]:
    return {int(n): int(a) for n, a in _NUM_TO_ABSTRACT_RE.findall(xml)}


def _render_marker(
    lvl: _LevelDef,
    counters: dict[int, int],
    all_levels: dict[int, _LevelDef],
    *,
    bullet_as_letters: bool = False,
) -> str:
    """Render ``lvl.lvl_text`` substituting ``%N`` with the formatted counter."""
    if lvl.num_fmt == "bullet":
        if bullet_as_letters and lvl.ilvl == 0:
            return _format_count(counters.get(0, 1), "lowerLetter") + "."
        return "•"

    def repl(m: re.Match[str]) -> str:
        n = int(m.group(1))
        # %N refers to ilvl=N-1's counter, formatted per that level's numFmt.
        target_ilvl = n - 1
        target_lvl = all_levels.get(target_ilvl, lvl)
        count = counters.get(target_ilvl, target_lvl.start)
        return _format_count(count, target_lvl.num_fmt)

    return re.sub(r"%(\d+)", repl, lvl.lvl_text)


def _format_count(n: int, num_fmt: str) -> str:
    if n < 1:
        n = 1
    if num_fmt == "decimal":
        return str(n)
    if num_fmt == "lowerLetter":
        return _to_letters(n, base=ord("a"))
    if num_fmt == "upperLetter":
        return _to_letters(n, base=ord("A"))
    if num_fmt == "lowerRoman":
        return _to_roman(n).lower()
    if num_fmt == "upperRoman":
        return _to_roman(n)
    return str(n)


def _to_letters(n: int, *, base: int) -> str:
    """Excel-column-style: 1->a, 26->z, 27->aa, ..."""
    out = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        out = chr(base + rem) + out
    return out


_ROMAN_NUMERALS: list[tuple[int, str]] = [
    (1000, "M"),
    (900, "CM"),
    (500, "D"),
    (400, "CD"),
    (100, "C"),
    (90, "XC"),
    (50, "L"),
    (40, "XL"),
    (10, "X"),
    (9, "IX"),
    (5, "V"),
    (4, "IV"),
    (1, "I"),
]


def _to_roman(n: int) -> str:
    out = ""
    for value, sym in _ROMAN_NUMERALS:
        while n >= value:
            out += sym
            n -= value
    return out


# ---------- helpers for callers walking python-docx paragraphs --------------


_NUMID_RE = re.compile(r'<w:numId w:val="(\d+)"')
_ILVL_RE = re.compile(r'<w:ilvl w:val="(\d+)"')


def extract_num_pr(p_xml: str) -> tuple[int, int] | None:
    """Return ``(numId, ilvl)`` from a paragraph's XML, or ``None``."""
    if "<w:numPr>" not in p_xml:
        return None
    m_id = _NUMID_RE.search(p_xml)
    if m_id is None:
        return None
    m_ilvl = _ILVL_RE.search(p_xml)
    return int(m_id.group(1)), (int(m_ilvl.group(1)) if m_ilvl else 0)


__all__ = [
    "NumberingResolver",
    "extract_num_pr",
    "load_resolver_from_docx",
]
