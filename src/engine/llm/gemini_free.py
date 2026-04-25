from __future__ import annotations
import json
import logging
import google.generativeai as genai

from .base import LLMError, LLMRateLimit, LLMTimeout

log = logging.getLogger(__name__)


class GeminiFreeProvider:
    name = "gemini-free"
    model = "gemini-2.5-flash"

    def __init__(self, api_key: str, model: str | None = None):
        if not api_key:
            raise RuntimeError("api_key obrigatório (passe via construtor)")
        genai.configure(api_key=api_key)
        if model:
            self.model = model
        self._model = genai.GenerativeModel(self.model)

    async def generate_structured(self, prompt: str, json_schema: dict) -> dict:
        full_prompt = (
            prompt
            + "\n\nResponda APENAS com um objeto JSON válido seguindo o schema:\n"
            + json.dumps(json_schema, ensure_ascii=False)
        )
        try:
            resp = await self._model.generate_content_async(
                full_prompt,
                generation_config={"response_mime_type": "application/json", "temperature": 0},
            )
        except Exception as e:
            msg = str(e).lower()
            if "rate" in msg or "quota" in msg or "429" in msg:
                raise LLMRateLimit(retry_after=60)
            if "timeout" in msg or "deadline" in msg:
                raise LLMTimeout()
            log.error("gemini.error: %s", str(e))
            raise LLMError(str(e))

        try:
            return json.loads(resp.text)
        except json.JSONDecodeError as e:
            log.error("gemini.invalid_json text=%s", resp.text[:500])
            raise LLMError(f"JSON inválido: {e}")
