"""Ollama provider — local inference via HTTP API."""

from __future__ import annotations

import json
from typing import Any

import structlog

from .base import LLMError, LLMTimeout

try:
    import httpx
except ImportError as e:  # pragma: no cover - optional dep
    raise ImportError("httpx não instalado. Instale com: pip install template-engine-ia[ollama]") from e

log = structlog.get_logger(__name__)


class OllamaProvider:
    """Ollama provider — runs against a local Ollama daemon (default http://localhost:11434).

    Uses Ollama's `format=json` mode + injects schema into the prompt.
    """

    name = "ollama"
    model = "llama3.1"

    def __init__(
        self,
        model: str | None = None,
        base_url: str = "http://localhost:11434",
        timeout: float = 120.0,
    ) -> None:
        if model:
            self.model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def generate_structured(self, prompt: str, json_schema: dict) -> dict[str, Any]:
        full_prompt = (
            prompt
            + "\n\nResponda APENAS com JSON válido seguindo este schema:\n"
            + json.dumps(json_schema, ensure_ascii=False)
        )
        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "format": "json",
            "stream": False,
            "options": {"temperature": 0},
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                r = await client.post(f"{self._base_url}/api/generate", json=payload)
                r.raise_for_status()
                data = r.json()
        except httpx.TimeoutException as e:
            log.warning("ollama.timeout", error=str(e))
            raise LLMTimeout() from e
        except httpx.HTTPStatusError as e:
            log.error("ollama.http_error", status=e.response.status_code, body=e.response.text[:300])
            raise LLMError(f"Ollama HTTP {e.response.status_code}: {e.response.text[:200]}") from e
        except Exception as e:
            log.error("ollama.error", error=str(e), error_type=type(e).__name__)
            raise LLMError(str(e)) from e

        content = data.get("response", "")
        if not content:
            raise LLMError("Ollama retornou response vazio")

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            log.error("ollama.invalid_json", text_preview=content[:500])
            raise LLMError(f"JSON inválido: {e}") from e
