"""OpenAI provider — uses Chat Completions with response_format=json_schema."""

from __future__ import annotations

import json
from typing import Any

import structlog

from .base import LLMError, LLMRateLimit, LLMTimeout

try:
    from openai import APITimeoutError, AsyncOpenAI, RateLimitError
except ImportError as e:  # pragma: no cover - optional dep
    raise ImportError("openai SDK não instalado. Instale com: pip install template-engine[openai]") from e

log = structlog.get_logger(__name__)


class OpenAIProvider:
    """OpenAI provider using Chat Completions + structured outputs (json_schema response_format)."""

    name = "openai"
    model = "gpt-4o-mini"

    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        if not api_key:
            raise RuntimeError("api_key obrigatório")
        if model:
            self.model = model
        self._client: AsyncOpenAI = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    async def generate_structured(self, prompt: str, json_schema: dict) -> dict[str, Any]:
        try:
            resp = await self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "structured_output",
                        "schema": json_schema,
                        "strict": False,
                    },
                },
                temperature=0,
            )
        except RateLimitError as e:
            log.warning("openai.rate_limit", error=str(e))
            raise LLMRateLimit(retry_after=60) from e
        except APITimeoutError as e:
            log.warning("openai.timeout", error=str(e))
            raise LLMTimeout() from e
        except Exception as e:
            log.error("openai.error", error=str(e), error_type=type(e).__name__)
            raise LLMError(str(e)) from e

        if not resp.choices:
            raise LLMError("OpenAI retornou resposta sem choices")
        content = resp.choices[0].message.content
        if not content:
            raise LLMError("OpenAI retornou content vazio")

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            log.error("openai.invalid_json", text_preview=content[:500])
            raise LLMError(f"JSON inválido: {e}") from e
