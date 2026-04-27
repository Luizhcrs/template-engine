"""Anthropic provider — uses tool use to coerce JSON output."""

from __future__ import annotations

import json
from typing import Any

import structlog

from ._utils import retry_after_from_error
from .base import LLMError, LLMRateLimit, LLMTimeout

try:
    from anthropic import APITimeoutError, AsyncAnthropic, RateLimitError
except ImportError as e:  # pragma: no cover - optional dep
    raise ImportError(
        "anthropic SDK não instalado. Instale com: pip install template-engine-ia[anthropic]"
    ) from e

log = structlog.get_logger(__name__)


_TOOL_NAME = "respond_with_structured_output"


class AnthropicProvider:
    """Anthropic provider using tool use to force structured JSON."""

    name = "anthropic"
    model = "claude-sonnet-4-5"

    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        max_tokens: int = 8192,
        timeout: float = 60.0,
    ) -> None:
        if not api_key:
            raise RuntimeError("api_key obrigatório")
        if model:
            self.model = model
        self._client: AsyncAnthropic = AsyncAnthropic(api_key=api_key, timeout=timeout)
        self._max_tokens = max_tokens

    async def generate_structured(self, prompt: str, json_schema: dict) -> dict[str, Any]:
        tool = {
            "name": _TOOL_NAME,
            "description": "Return the structured output as the function arguments.",
            "input_schema": json_schema,
        }
        try:
            resp = await self._client.messages.create(  # type: ignore[call-overload]
                model=self.model,
                max_tokens=self._max_tokens,
                temperature=0,
                tools=[tool],
                tool_choice={"type": "tool", "name": _TOOL_NAME},
                messages=[{"role": "user", "content": prompt}],
            )
        except RateLimitError as e:
            retry_after = retry_after_from_error(e, default=60)
            log.warning("anthropic.rate_limit", error=str(e), retry_after=retry_after)
            raise LLMRateLimit(retry_after=retry_after) from e
        except APITimeoutError as e:
            log.warning("anthropic.timeout", error=str(e))
            raise LLMTimeout() from e
        except Exception as e:
            log.error("anthropic.error", error=str(e), error_type=type(e).__name__)
            raise LLMError(str(e)) from e

        for block in resp.content:
            if block.type == "tool_use" and block.name == _TOOL_NAME:
                # block.input já é dict
                if isinstance(block.input, dict):
                    return block.input
                # fallback se vier string JSON
                try:
                    return json.loads(str(block.input))
                except json.JSONDecodeError as e:
                    raise LLMError(f"tool input não é JSON: {e}") from e

        log.error("anthropic.no_tool_use")
        raise LLMError("Anthropic não retornou tool_use; resposta inesperada")
