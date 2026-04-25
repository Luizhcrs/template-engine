"""LLM router with fallback rotation.

Tries providers in order; on rate-limit / timeout, falls back to next.
Other errors propagate immediately (LLMError without retry semantics).
"""
from __future__ import annotations
from typing import Any

import structlog

from .base import LLMError, LLMProvider, LLMRateLimit, LLMTimeout

log = structlog.get_logger(__name__)


class AllProvidersFailed(LLMError):
    """All providers in the fallback chain failed."""


class LLMRouter:
    """Tries providers in order; falls back to next on transient failures (rate-limit/timeout).

    Example:
        router = LLMRouter([
            GroqProvider(api_key=g),
            GeminiFreeProvider(api_key=ge),
            OpenAIProvider(api_key=o, model="gpt-4o-mini"),
        ])
        result = await router.generate_structured(prompt, schema)
    """

    def __init__(self, providers: list[LLMProvider]) -> None:
        if not providers:
            raise ValueError("LLMRouter requer pelo menos 1 provider")
        self._providers = providers
        self.name = "router(" + ",".join(p.name for p in providers) + ")"
        self.model = "multi"

    async def generate_structured(self, prompt: str, json_schema: dict) -> dict[str, Any]:
        last_error: Exception | None = None
        for i, provider in enumerate(self._providers):
            try:
                log.info("router.try", provider=provider.name, index=i)
                return await provider.generate_structured(prompt, json_schema)
            except (LLMRateLimit, LLMTimeout) as e:
                log.warning(
                    "router.fallback",
                    provider=provider.name,
                    index=i,
                    reason=type(e).__name__,
                )
                last_error = e
                continue

        raise AllProvidersFailed(
            f"all providers exhausted: {[p.name for p in self._providers]}"
        ) from last_error
