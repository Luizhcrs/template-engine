from __future__ import annotations
import json
import structlog
import google.generativeai as genai

from .base import LLMError, LLMRateLimit, LLMTimeout

# Specific exception types from google.api_core (transitive dep of google-generativeai)
try:
    from google.api_core import exceptions as gapi_exc
    _RATE_LIMIT_EXCS = (gapi_exc.ResourceExhausted, gapi_exc.TooManyRequests)
    _TIMEOUT_EXCS = (gapi_exc.DeadlineExceeded, gapi_exc.ServiceUnavailable)
except ImportError:
    _RATE_LIMIT_EXCS = ()
    _TIMEOUT_EXCS = ()

log = structlog.get_logger(__name__)


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
        except _RATE_LIMIT_EXCS as e:
            log.warning("gemini.rate_limit", error=str(e))
            raise LLMRateLimit(retry_after=60) from e
        except _TIMEOUT_EXCS as e:
            log.warning("gemini.timeout", error=str(e))
            raise LLMTimeout() from e
        except Exception as e:
            # Last-resort substring match for SDK exceptions not in google.api_core
            msg = str(e).lower()
            if "rate" in msg or "quota" in msg or "429" in msg or "resource_exhausted" in msg:
                raise LLMRateLimit(retry_after=60) from e
            if "timeout" in msg or "deadline" in msg:
                raise LLMTimeout() from e
            log.error("gemini.error", error=str(e), error_type=type(e).__name__)
            raise LLMError(str(e)) from e

        # Safety filter or empty response — resp.text raises if no candidates
        if not resp.candidates:
            log.error("gemini.no_candidates")
            raise LLMError("Gemini retornou resposta sem candidatos (possível filtro de segurança)")

        try:
            return json.loads(resp.text)
        except json.JSONDecodeError as e:
            log.error("gemini.invalid_json", text_preview=resp.text[:500])
            raise LLMError(f"JSON inválido: {e}") from e
