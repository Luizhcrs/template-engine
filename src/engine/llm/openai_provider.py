"""OpenAI provider — uses Chat Completions with response_format=json_schema."""

from __future__ import annotations

import json
from typing import Any

import structlog

from ._schema import normalize_for_strict
from ._utils import retry_after_from_error
from .base import LLMError, LLMRateLimit, LLMTimeout

try:
    from openai import APITimeoutError, AsyncOpenAI, RateLimitError
except ImportError as e:  # pragma: no cover - optional dep
    raise ImportError("openai SDK não instalado. Instale com: pip install template-engine-ia[openai]") from e

log = structlog.get_logger(__name__)


class OpenAIProvider:
    """OpenAI provider using Chat Completions + structured outputs (json_schema response_format).

    Args:
        api_key: OpenAI API key (required)
        model: model id (default ``gpt-4o-mini``)
        base_url: optional override (used by OpenRouterProvider)
        timeout: request timeout in seconds (default 60)
        strict: when True, schema is normalized for OpenAI strict mode
            (``additionalProperties: false`` recursive + every key in ``required``).
            Strict mode is more reliable but rejects schemas with optional fields.
            Default: False (most permissive, compatible with arbitrary schemas).
    """

    name = "openai"
    model = "gpt-4o-mini"

    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
        strict: bool = False,
    ) -> None:
        if not api_key:
            raise RuntimeError("api_key obrigatório")
        if model:
            self.model = model
        self._strict = strict
        self._client: AsyncOpenAI = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    async def generate_structured(self, prompt: str, json_schema: dict) -> dict[str, Any]:
        schema_for_request = normalize_for_strict(json_schema) if self._strict else json_schema
        try:
            resp = await self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "structured_output",
                        "schema": schema_for_request,
                        "strict": self._strict,
                    },
                },
                temperature=0,
            )
        except RateLimitError as e:
            retry_after = retry_after_from_error(e, default=60)
            log.warning("openai.rate_limit", error=str(e), retry_after=retry_after)
            raise LLMRateLimit(retry_after=retry_after) from e
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
