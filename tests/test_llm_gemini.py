from unittest.mock import MagicMock, patch

import pytest

from engine.llm.base import LLMError, LLMRateLimit


def _make_provider():
    from engine.llm.gemini_free import GeminiFreeProvider

    with patch("engine.llm.gemini_free.genai"):
        return GeminiFreeProvider(api_key="test-key")


def test_gemini_provider_imports():
    provider = _make_provider()
    assert provider.name == "gemini-free"
    assert provider.model == "gemini-2.5-flash"


def test_gemini_rejects_missing_api_key():
    from engine.llm.gemini_free import GeminiFreeProvider

    with patch("engine.llm.gemini_free.genai"), pytest.raises(RuntimeError, match="api_key"):
        GeminiFreeProvider(api_key="")


def test_gemini_custom_model_override():
    from engine.llm.gemini_free import GeminiFreeProvider

    with patch("engine.llm.gemini_free.genai"):
        provider = GeminiFreeProvider(api_key="test-key", model="gemini-2.0-flash")
        assert provider.model == "gemini-2.0-flash"


@pytest.mark.asyncio
async def test_gemini_rate_limit_raises():
    provider = _make_provider()
    mock_model = MagicMock()

    async def rate_limited(*args, **kwargs):
        raise Exception("429 rate limit exceeded")

    mock_model.generate_content_async = rate_limited
    provider._model = mock_model

    with pytest.raises(LLMRateLimit):
        await provider.generate_structured("test", {"type": "object"})


@pytest.mark.asyncio
async def test_gemini_returns_parsed_json():
    provider = _make_provider()
    mock_model = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = '{"foo": "bar"}'

    async def ok_response(*args, **kwargs):
        return mock_resp

    mock_model.generate_content_async = ok_response
    provider._model = mock_model

    result = await provider.generate_structured("test", {"type": "object"})
    assert result == {"foo": "bar"}


@pytest.mark.asyncio
async def test_gemini_invalid_json_raises():
    provider = _make_provider()
    mock_model = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = "not valid json"

    async def broken_json(*args, **kwargs):
        return mock_resp

    mock_model.generate_content_async = broken_json
    provider._model = mock_model

    with pytest.raises(LLMError, match="JSON inválido"):
        await provider.generate_structured("test", {"type": "object"})
