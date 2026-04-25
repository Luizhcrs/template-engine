from unittest.mock import AsyncMock

import pytest

from engine.llm import AllProvidersFailed, LLMRouter
from engine.llm.base import LLMError, LLMRateLimit, LLMTimeout


def _make_provider(name: str, side_effect=None, return_value=None):
    p = AsyncMock()
    p.name = name
    p.model = "mock"
    if side_effect is not None:
        p.generate_structured.side_effect = side_effect
    else:
        p.generate_structured.return_value = return_value
    return p


def test_router_requires_at_least_one_provider():
    with pytest.raises(ValueError, match="pelo menos 1 provider"):
        LLMRouter([])


@pytest.mark.asyncio
async def test_router_uses_first_provider_when_ok():
    p1 = _make_provider("p1", return_value={"k": "v1"})
    p2 = _make_provider("p2", return_value={"k": "v2"})
    router = LLMRouter([p1, p2])

    result = await router.generate_structured("prompt", {})

    assert result == {"k": "v1"}
    p1.generate_structured.assert_awaited_once()
    p2.generate_structured.assert_not_awaited()


@pytest.mark.asyncio
async def test_router_falls_back_on_rate_limit():
    p1 = _make_provider("p1", side_effect=LLMRateLimit(retry_after=60))
    p2 = _make_provider("p2", return_value={"ok": True})
    router = LLMRouter([p1, p2])

    result = await router.generate_structured("prompt", {})

    assert result == {"ok": True}
    p1.generate_structured.assert_awaited_once()
    p2.generate_structured.assert_awaited_once()


@pytest.mark.asyncio
async def test_router_falls_back_on_timeout():
    p1 = _make_provider("p1", side_effect=LLMTimeout())
    p2 = _make_provider("p2", side_effect=LLMTimeout())
    p3 = _make_provider("p3", return_value={"final": "yes"})
    router = LLMRouter([p1, p2, p3])

    result = await router.generate_structured("prompt", {})

    assert result == {"final": "yes"}


@pytest.mark.asyncio
async def test_router_does_not_fallback_on_generic_error():
    p1 = _make_provider("p1", side_effect=LLMError("hard fail"))
    p2 = _make_provider("p2", return_value={"never": "called"})
    router = LLMRouter([p1, p2])

    with pytest.raises(LLMError, match="hard fail"):
        await router.generate_structured("prompt", {})

    p2.generate_structured.assert_not_awaited()


@pytest.mark.asyncio
async def test_router_raises_when_all_providers_exhaust():
    p1 = _make_provider("p1", side_effect=LLMRateLimit(retry_after=60))
    p2 = _make_provider("p2", side_effect=LLMTimeout())
    router = LLMRouter([p1, p2])

    with pytest.raises(AllProvidersFailed, match="all providers exhausted"):
        await router.generate_structured("prompt", {})


def test_router_name_includes_all_providers():
    p1 = _make_provider("groq")
    p2 = _make_provider("gemini-free")
    router = LLMRouter([p1, p2])
    assert router.name == "router(groq,gemini-free)"
