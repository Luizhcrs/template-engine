"""Tests for engine.visual_validator and GeminiVisionProvider.

Mocks subprocess (LibreOffice) and pdf2image — no LibreOffice required to run.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from engine.visual_validator import (
    VisualIssue,
    VisualValidationResult,
    docx_to_png,
    validate_visual,
)


@pytest.fixture
def fake_docx(tmp_path: Path) -> Path:
    p = tmp_path / "fake.docx"
    p.write_bytes(b"PK\x03\x04 fake docx bytes")
    return p


def test_docx_to_png_missing_soffice_raises(fake_docx, tmp_path):
    with (
        patch("engine.visual_validator.shutil.which", return_value=None),
        pytest.raises(RuntimeError, match="LibreOffice not found"),
    ):
        docx_to_png(fake_docx, out_dir=tmp_path)


def test_docx_to_png_subprocess_failure_raises(fake_docx, tmp_path):
    fake_proc = MagicMock(returncode=1, stderr="error from soffice", stdout="")
    with (
        patch("engine.visual_validator.shutil.which", return_value="/usr/bin/soffice"),
        patch("engine.visual_validator.subprocess.run", return_value=fake_proc),
        pytest.raises(RuntimeError, match="LibreOffice conversion failed"),
    ):
        docx_to_png(fake_docx, out_dir=tmp_path)


def test_docx_to_png_missing_pdf_after_success_raises(fake_docx, tmp_path):
    """If soffice exits 0 but PDF doesn't appear at expected path."""
    fake_proc = MagicMock(returncode=0, stderr="", stdout="ok")
    with (
        patch("engine.visual_validator.shutil.which", return_value="/usr/bin/soffice"),
        patch("engine.visual_validator.subprocess.run", return_value=fake_proc),
        pytest.raises(RuntimeError, match="PDF not produced"),
    ):
        docx_to_png(fake_docx, out_dir=tmp_path)


def test_docx_to_png_happy_path(fake_docx, tmp_path):
    """Mocks subprocess + pdf2image; verifies PNG path returned."""
    fake_proc = MagicMock(returncode=0, stderr="", stdout="ok")

    expected_pdf = tmp_path / "fake.pdf"

    def mock_run(*args, **kwargs):
        # Simulate soffice creating the PDF
        expected_pdf.write_bytes(b"%PDF-1.4 fake")
        return fake_proc

    fake_image = MagicMock()

    with (
        patch("engine.visual_validator.shutil.which", return_value="/usr/bin/soffice"),
        patch("engine.visual_validator.subprocess.run", side_effect=mock_run),
        patch("pdf2image.convert_from_path", return_value=[fake_image]),
    ):
        png = docx_to_png(fake_docx, out_dir=tmp_path)

    assert png == tmp_path / "fake.png"
    fake_image.save.assert_called_once_with(png, "PNG")


@pytest.mark.asyncio
async def test_validate_visual_orchestrates_full_pipeline(fake_docx, tmp_path):
    """End-to-end: render gold + output, call LLM, parse result."""
    output_docx = tmp_path / "output.docx"
    output_docx.write_bytes(b"PK\x03\x04 fake output")

    # Mock LLM provider
    fake_llm = AsyncMock()
    fake_llm.compare_images.return_value = {
        "score": 0.85,
        "summary": "Mostly aligned, one minor spacing issue.",
        "issues": [
            {
                "category": "spacing",
                "severity": "low",
                "description": "Section 2 has extra blank line.",
            }
        ],
    }

    # Mock PNG paths to skip actual rendering
    fake_gold_png = tmp_path / "gold" / "fake.png"
    fake_output_png = tmp_path / "output" / "output.png"
    fake_gold_png.parent.mkdir(parents=True, exist_ok=True)
    fake_output_png.parent.mkdir(parents=True, exist_ok=True)
    fake_gold_png.write_bytes(b"\x89PNG fake")
    fake_output_png.write_bytes(b"\x89PNG fake")

    with patch(
        "engine.visual_validator.docx_to_png",
        side_effect=[fake_gold_png, fake_output_png],
    ):
        result = await validate_visual(
            gold_path=fake_docx,
            output_path=output_docx,
            llm=fake_llm,
            keep_images_dir=tmp_path,
        )

    assert isinstance(result, VisualValidationResult)
    assert result.score == 0.85
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert isinstance(issue, VisualIssue)
    assert issue.category == "spacing"
    assert issue.severity == "low"
    assert "extra blank line" in issue.description
    assert result.gold_image == fake_gold_png
    assert result.output_image == fake_output_png

    # Verify LLM was called with correct args
    fake_llm.compare_images.assert_awaited_once()
    call_args = fake_llm.compare_images.await_args
    assert len(call_args.args[1]) == 2  # 2 images


@pytest.mark.asyncio
async def test_validate_visual_missing_gold_raises(tmp_path):
    fake_llm = AsyncMock()
    with pytest.raises(FileNotFoundError, match="gold_path"):
        await validate_visual(
            gold_path=tmp_path / "missing.docx",
            output_path=tmp_path / "also-missing.docx",
            llm=fake_llm,
        )


@pytest.mark.asyncio
async def test_validate_visual_missing_output_raises(fake_docx, tmp_path):
    fake_llm = AsyncMock()
    with pytest.raises(FileNotFoundError, match="output_path"):
        await validate_visual(
            gold_path=fake_docx,
            output_path=tmp_path / "missing.docx",
            llm=fake_llm,
        )


# ===== GeminiVisionProvider =====


def test_gemini_vision_rejects_missing_api_key():
    from engine.llm.gemini_vision import GeminiVisionProvider

    with patch("engine.llm.gemini_vision.genai"), pytest.raises(RuntimeError, match="api_key"):
        GeminiVisionProvider(api_key="")


def test_gemini_vision_imports_with_default_model():
    from engine.llm.gemini_vision import GeminiVisionProvider

    with patch("engine.llm.gemini_vision.genai"):
        provider = GeminiVisionProvider(api_key="test-key")
    assert provider.name == "gemini-vision"
    assert provider.model == "gemini-2.5-flash"


@pytest.mark.asyncio
async def test_gemini_vision_compare_images_requires_min_2(tmp_path):
    from engine.llm.gemini_vision import GeminiVisionProvider

    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG fake")

    with patch("engine.llm.gemini_vision.genai"):
        provider = GeminiVisionProvider(api_key="test-key")

    with pytest.raises(ValueError, match="at least 2 images"):
        await provider.compare_images("prompt", [img], {"type": "object"})


@pytest.mark.asyncio
async def test_gemini_vision_compare_images_missing_file_raises(tmp_path):
    from engine.llm.gemini_vision import GeminiVisionProvider

    real = tmp_path / "real.png"
    real.write_bytes(b"\x89PNG fake")
    missing = tmp_path / "ghost.png"

    with patch("engine.llm.gemini_vision.genai"):
        provider = GeminiVisionProvider(api_key="test-key")

    with pytest.raises(FileNotFoundError, match="image not found"):
        await provider.compare_images("prompt", [real, missing], {"type": "object"})


@pytest.mark.asyncio
async def test_gemini_vision_returns_parsed_json(tmp_path):
    from engine.llm.gemini_vision import GeminiVisionProvider

    img1 = tmp_path / "g.png"
    img2 = tmp_path / "o.png"
    img1.write_bytes(b"\x89PNG g")
    img2.write_bytes(b"\x89PNG o")

    fake_resp = MagicMock()
    fake_resp.candidates = [MagicMock()]
    fake_resp.text = '{"score": 0.92, "summary": "ok", "issues": []}'

    with patch("engine.llm.gemini_vision.genai"):
        provider = GeminiVisionProvider(api_key="test-key")
    provider._model = MagicMock()
    provider._model.generate_content_async = AsyncMock(return_value=fake_resp)

    result = await provider.compare_images("prompt", [img1, img2], {"type": "object"})

    assert result == {"score": 0.92, "summary": "ok", "issues": []}
