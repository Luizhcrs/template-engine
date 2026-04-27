"""Fill the template's header with metadata extracted from the source.

Industrial templates ship the header pre-laid with placeholders:

    XXXX              Rev. 00       Elaborado:        Aprovado:       Data:
    ENGEMAN ...                              (TITULO)

Each cell is a separate run group. Source documents (Engeman style)
carry the same fields in their own header — split across many ``<w:t>``
elements because Word fragments runs by formatting — and the body's
revision-history table holds the author/date pair.

This module:

1. Reads the source header XML, concatenates ``<w:t>`` text into a
   single normalized line, and extracts: document code, title, version,
   approver. It also reads the source's revision-history table (when
   present) to pull the most recent author + date.
2. Walks the template's header XML and substitutes the placeholders in
   place (preserving formatting), saving back to the docx zip.

When source metadata is missing, the corresponding placeholder is left
untouched so downstream reviewers can spot the gap.
"""

from __future__ import annotations

import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_HEADER_FILE_RE = re.compile(r"^word/header\d*\.xml$")


@dataclass(frozen=True)
class HeaderMetadata:
    """Metadata gathered from the source ``.docx`` header + body."""

    document_code: str | None
    title: str | None
    version: str | None  # "01", "02", ...
    author: str | None
    approver: str | None
    source_date: str | None

    def has_any(self) -> bool:
        return any(
            v is not None
            for v in (
                self.document_code,
                self.title,
                self.version,
                self.author,
                self.approver,
                self.source_date,
            )
        )


# ---------- extraction --------------------------------------------------------


# Document-code prefix recogniser. We search the SPACED flavor of the
# header (where every <w:t> run sits between spaces) for the prefix
# ``IT.PRO.`` / ``NO.SGI.`` / ``DS.SGI.`` etc. Once we have the prefix,
# we go to the GLUED flavor, find that prefix, and read forward until
# the dotted-decimal pattern breaks.
_DOC_CODE_PREFIX_RE = re.compile(
    r"(?:^|\s)([A-Z]{2,3}\.[A-Z]{2,5}\.)(?=\s|[A-Z0-9])",
)
_DOC_CODE_BODY_RE = re.compile(r"^([A-Z]+|\d+)([A-Z]+|\d+|\.)*")
_VERSION_RE = re.compile(r"Ver(?:s[aã]o|\.|:)?\s*[:.]?\s*(\d{1,3})", re.IGNORECASE)
_REV_RE = re.compile(r"Rev(?:is[aã]o|\.|:)?\s*[:.]?\s*(\d{1,3})", re.IGNORECASE)
_DATE_RE = re.compile(r"\b(\d{2}/\d{2}/\d{2,4})\b")
_APPROVER_RE = re.compile(
    r"Aprovador?\s*\(?es\)?\s*:?\s*(.+?)(?:\s*$|<)",
    re.IGNORECASE,
)


def extract_source_metadata(source_path: Path) -> HeaderMetadata:
    """Read the source ``.docx`` and gather header / history metadata."""
    if source_path.suffix.lower() != ".docx":
        return HeaderMetadata(None, None, None, None, None, None)

    header_text = _flat_header_text(source_path)
    document_code = _extract_document_code(header_text)
    version_match = _VERSION_RE.search(header_text) or _REV_RE.search(header_text)
    version = version_match.group(1).zfill(2) if version_match else None
    approver = _extract_approver(header_text)
    title = _extract_title(source_path, header_text, document_code)

    author, source_date = _extract_author_and_date_from_history(source_path)

    return HeaderMetadata(
        document_code=document_code,
        title=title,
        version=version,
        author=author,
        approver=approver,
        source_date=source_date,
    )


def _extract_document_code(header_text: str) -> str | None:
    """Locate the document code by scanning the SPACED flavor for a
    ``[A-Z]{2,3}.[A-Z]{2,5}.`` prefix, then walking the GLUED flavor
    starting at that prefix to gather the whole dotted-decimal code.
    """
    glued, _, spaced = header_text.partition("\n---\n")
    if not spaced:
        spaced = glued

    prefix_match = _DOC_CODE_PREFIX_RE.search(spaced)
    if prefix_match is None:
        return None
    prefix = prefix_match.group(1)  # e.g. "IT.PRO."

    # Find the prefix in the glued flavor and extract until the pattern
    # of letters/digits/dots ends with the last digit.
    start = glued.find(prefix)
    if start < 0:
        return None
    rest = glued[start:]
    # State machine: walk segments separated by dots. Within a segment,
    # a letter→digit (or vice versa) transition is invalid and ends the
    # match. This stops the walk at ``...0005PARTIDA`` (segment was
    # all-digits, then a letter appears with no separating dot).
    end = 0
    segment_kind: str | None = None  # "letter" / "digit" / None at "."
    for ch in rest:
        if ch == ".":
            segment_kind = None
            end += 1
            continue
        if ch.isupper():
            if segment_kind == "digit":
                break
            segment_kind = "letter"
            end += 1
            continue
        if ch.isdigit():
            if segment_kind == "letter":
                break
            segment_kind = "digit"
            end += 1
            continue
        break
    code = rest[:end].rstrip(".")
    if code.count(".") >= 2 and code[-1].isdigit():
        return code
    return None


def _flat_header_text(source_path: Path) -> str:
    """Concatenate every ``<w:t>`` in every header file.

    Two flavors are returned, glued together with a separator: first the
    runs WITHOUT spacing (so dotted document codes like ``IT.PRO.URE.``
    stay intact across run boundaries), then the runs WITH single-space
    separators (so titles like ``PARTIDA DA ÁREA DE SÍNTESE`` followed
    by ``Ver.:`` don't merge into ``SÍNTESEVer``). Downstream regexes
    pick whichever flavor fits.
    """
    glued_parts: list[str] = []
    spaced_parts: list[str] = []
    try:
        with zipfile.ZipFile(str(source_path)) as z:
            for name in z.namelist():
                if not _HEADER_FILE_RE.match(name):
                    continue
                xml = z.read(name).decode("utf-8")
                texts = re.findall(r"<w:t[^>]*>([^<]*)</w:t>", xml)
                glued_parts.append("".join(texts))
                spaced_parts.append(" ".join(t for t in texts if t.strip()))
    except (zipfile.BadZipFile, KeyError):
        return ""
    glued = " ".join(p.strip() for p in glued_parts if p.strip())
    spaced = " ".join(p.strip() for p in spaced_parts if p.strip())
    return f"{glued}\n---\n{spaced}"


def _first_match(pattern: re.Pattern[str], text: str) -> str | None:
    m = pattern.search(text)
    return m.group(1) if m else None


def _extract_approver(text: str) -> str | None:
    m = _APPROVER_RE.search(text)
    if not m:
        return None
    raw = m.group(1).strip()
    # Cut at common terminators that appear right after the name in the
    # header (page indicators, dates, "Fl. N/M").
    raw = re.split(r"\s+(?:Fl\.|Página|\d{2}/\d{2})", raw)[0].strip()
    return raw or None


def _extract_title(
    source_path: Path,
    header_text: str,
    document_code: str | None,
) -> str | None:
    """The source header contains the procedure title in caps. Find the
    longest all-caps run that isn't the document code or company name.

    Runs are matched against the SPACED flavor of the flat header text
    (the part after the ``\\n---\\n`` separator) so adjacent runs like
    ``SÍNTESE`` + ``Ver.: 01`` don't fuse into a single token.
    """
    spaced = header_text.split("\n---\n", 1)[-1]
    candidates: list[str] = []
    for match in re.finditer(
        r"(?:[A-ZÁÉÍÓÚÂÊÔÃÕÇ]{2,}(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ]{2,}){1,})",
        spaced,
    ):
        cand = match.group().strip()
        if 8 <= len(cand) <= 80:
            candidates.append(cand)

    blacklist = {
        "INSTRUCAO DE TRABALHO",
        "INSTRUÇÃO DE TRABALHO",
        "ENGEMAN MANUTENCAO DE EQUIPAMENTOS COM E IND LTDA",
        "ENGEMAN MANUTENÇÃO DE EQUIPAMENTOS COM E IND LTDA",
        "ENGEMAN",
    }

    def _norm(s: str) -> str:
        import unicodedata

        nkfd = unicodedata.normalize("NFKD", s)
        return "".join(c for c in nkfd if not unicodedata.combining(c)).upper()

    seen: set[str] = set()
    deduped: list[str] = []
    for c in candidates:
        n = _norm(c)
        if n in seen:
            continue
        if n in blacklist:
            continue
        if document_code and document_code in c:
            continue
        seen.add(n)
        deduped.append(c)

    if not deduped:
        return None
    # Heuristic: the title is the LONGEST candidate that is not the
    # document code / company. Industrial templates put a short header
    # banner plus a longer procedure-title — the longer wins.
    return max(deduped, key=len)


def _extract_author_and_date_from_history(
    source_path: Path,
) -> tuple[str | None, str | None]:
    """Pull (author, date) from the source's revision-history table."""
    try:
        from docx import Document

        doc = Document(str(source_path))
    except Exception:
        return None, None

    for table in doc.tables:
        if not table.rows:
            continue
        header_cells = [_norm_token(c.text) for c in table.rows[0].cells]
        # Detect the history table by AUTHOR + DATA columns.
        author_idx = next(
            (i for i, h in enumerate(header_cells) if "AUTOR" in h or "REVISOR" in h),
            None,
        )
        date_idx = next(
            (i for i, h in enumerate(header_cells) if "DATA" in h),
            None,
        )
        if author_idx is None or date_idx is None:
            continue
        # Take the FIRST non-empty data row.
        for r in table.rows[1:]:
            cells = [c.text.strip() for c in r.cells]
            if not any(cells):
                continue
            author = cells[author_idx] if author_idx < len(cells) else ""
            date_val = cells[date_idx] if date_idx < len(cells) else ""
            return (author or None, date_val or None)

    return None, None


def _norm_token(text: str) -> str:
    import unicodedata

    nkfd = unicodedata.normalize("NFKD", text)
    no_accent = "".join(c for c in nkfd if not unicodedata.combining(c))
    return re.sub(r"[^A-Z0-9 ]+", " ", no_accent.upper()).strip()


# ---------- substitution ------------------------------------------------------


def fill_template_header(
    output_path: Path,
    metadata: HeaderMetadata,
) -> int:
    """Substitute header placeholders in *output_path* with values from
    ``metadata``. Returns the number of placeholder substitutions made.

    Placeholders matched:

    - ``XXXX`` → document code
    - ``Rev. 00`` → ``Rev. <version>``
    - ``Elaborado:`` → ``Elaborado: <author>``
    - ``Aprovado:`` → ``Aprovado: <approver>``
    - ``Data:`` → ``Data: <iso_today>``
    - ``TITULO`` → procedure title
    """
    if not metadata.has_any():
        return 0

    substitutions = _build_substitutions(metadata)
    if not substitutions:
        return 0

    return _substitute_in_zip_headers(output_path, substitutions)


def _build_substitutions(metadata: HeaderMetadata) -> list[tuple[str, str]]:
    """Build ordered list of (placeholder, replacement) pairs.

    Order matters: more-specific patterns first so we don't accidentally
    rewrite a substring that's part of a longer placeholder.
    """
    from datetime import UTC, datetime

    out: list[tuple[str, str]] = []
    today_iso = datetime.now(UTC).date().isoformat()

    if metadata.document_code:
        out.append(("XXXX", metadata.document_code))
    if metadata.version:
        out.append(("Rev. 00", f"Rev. {metadata.version}"))
    if metadata.author:
        out.append(("Elaborado:", f"Elaborado: {metadata.author}"))
    if metadata.approver:
        out.append(("Aprovado:", f"Aprovado: {metadata.approver}"))
    out.append(("Data:", f"Data: {today_iso}"))
    if metadata.title:
        out.append(("TITULO", metadata.title))

    return out


def _substitute_in_zip_headers(
    docx_path: Path,
    substitutions: list[tuple[str, str]],
) -> int:
    """Open *docx_path*, walk its header*.xml entries, apply
    placeholder substitutions inside ``<w:t>`` elements, write back.
    Returns total substitutions applied.

    Each ``<w:t>`` is treated as an atomic text node — we replace
    ``placeholder`` with ``replacement`` only when the placeholder
    sits entirely inside one ``<w:t>``. This is the typical case for
    Engeman templates (every header field is its own run group).
    """
    total = 0
    with tempfile.NamedTemporaryFile(
        suffix=".docx",
        delete=False,
        dir=str(docx_path.parent),
    ) as tmp:
        tmp_path = Path(tmp.name)
    try:
        with (
            zipfile.ZipFile(str(docx_path), "r") as zin,
            zipfile.ZipFile(str(tmp_path), "w", zipfile.ZIP_DEFLATED) as zout,
        ):
            for item in zin.infolist():
                data = zin.read(item.filename)
                if _HEADER_FILE_RE.match(item.filename):
                    text = data.decode("utf-8")
                    text, n = _replace_in_runs(text, substitutions)
                    total += n
                    data = text.encode("utf-8")
                zout.writestr(item, data)
        shutil.move(str(tmp_path), str(docx_path))
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise

    return total


def _replace_in_runs(
    xml: str,
    substitutions: list[tuple[str, str]],
) -> tuple[str, int]:
    """Walk every ``<w:t ...>...</w:t>`` element and apply substitutions
    inside its inner text. Returns ``(new_xml, count)``.
    """
    count = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal count
        prefix = m.group(1)
        inner = m.group(2)
        suffix = m.group(3)
        for placeholder, replacement in substitutions:
            if placeholder in inner:
                inner = inner.replace(placeholder, _xml_escape(replacement), 1)
                count += 1
        return f"{prefix}{inner}{suffix}"

    pattern = re.compile(r"(<w:t(?:\s[^>]*)?>)([^<]*)(</w:t>)")
    new_xml = pattern.sub(repl, xml)
    return new_xml, count


def _xml_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


__all__ = [
    "HeaderMetadata",
    "extract_source_metadata",
    "fill_template_header",
]
