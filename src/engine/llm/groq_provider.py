"""Groq provider — Groq SDK is OpenAI-compatible; uses JSON mode."""

from __future__ import annotations

import json
from typing import Any

import structlog

from ._utils import retry_after_from_error
from .base import LLMError, LLMRateLimit, LLMTimeout

try:
    from groq import APITimeoutError, AsyncGroq, RateLimitError
except ImportError as e:  # pragma: no cover - optional dep
    raise ImportError("groq SDK não instalado. Instale com: pip install template-engine-ia[groq]") from e

log = structlog.get_logger(__name__)


class GroqProvider:
    """Groq provider — fast inference, OpenAI-compatible JSON mode."""

    name = "groq"
    model = "llama-3.3-70b-versatile"

    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        if not api_key:
            raise RuntimeError("api_key obrigatório")
        if model:
            self.model = model
        self._client: AsyncGroq = AsyncGroq(api_key=api_key, timeout=timeout)

    async def generate_structured(self, prompt: str, json_schema: dict) -> dict[str, Any]:
        # Groq expõe JSON mode mas não json_schema strict — injetamos schema no prompt.
        full_prompt = (
            prompt
            + "\n\nResponda APENAS com JSON válido seguindo este schema:\n"
            + json.dumps(json_schema, ensure_ascii=False)
        )
        try:
            resp = await self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": full_prompt}],
                response_format={"type": "json_object"},
                temperature=0,
            )
        except RateLimitError as e:
            retry_after = retry_after_from_error(e, default=60)
            log.warning("groq.rate_limit", error=str(e), retry_after=retry_after)
            raise LLMRateLimit(retry_after=retry_after) from e
        except APITimeoutError as e:
            log.warning("groq.timeout", error=str(e))
            raise LLMTimeout() from e
        except Exception as e:
            log.error("groq.error", error=str(e), error_type=type(e).__name__)
            raise LLMError(str(e)) from e

        if not resp.choices:
            raise LLMError("Groq retornou resposta sem choices")
        content = resp.choices[0].message.content
        if not content:
            raise LLMError("Groq retornou content vazio")

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            log.error("groq.invalid_json", text_preview=content[:500])
            raise LLMError(f"JSON inválido: {e}") from e
