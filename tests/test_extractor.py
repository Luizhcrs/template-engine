from pathlib import Path

import pytest

from engine.extractor import extract

FIXTURES = Path(__file__).parent / "fixtures"


def test_extract_docx_returns_paragraphs():
    result = extract(FIXTURES / "gold_sample_01.docx")
    assert len(result.paragraphs) > 0
    assert "OBJETIVO" in result.text.upper()


def test_extract_docx_finds_code():
    result = extract(FIXTURES / "gold_sample_01.docx")
    assert "DOC.001" in result.text


def test_extract_unsupported_format_raises():
    with pytest.raises(ValueError):
        extract(Path("dummy.xlsx"))
