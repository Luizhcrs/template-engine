"""Gemini vision provider — multi-modal LLM for image comparison.

Implements ``VisualLLMProvider`` Protocol. Used by ``engine.visual_validator``.
Reuses ``google-generativeai`` SDK already required by ``GeminiFreeProvider``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog

from .base import LLMError, LLMRateLimit, LLMTimeout

try:
    import google.generativeai as genai
except ImportError as e:  # pragma: no cover - optional dep
    raise ImportError(
        "google-generativeai not installed. Install with: pip install 'template-engine[gemini]'"
    ) from e

# Specific exception types from google.api_core (transitive dep of google-generativeai)
_RATE_LIMIT_EXCS: tuple[type[BaseException], ...] = ()
_TIMEOUT_EXCS: tuple[type[BaseException], ...] = ()
try:
    from google.api_core import exceptions as gapi_exc

    _RATE_LIMIT_EXCS = (gapi_exc.ResourceExhausted, gapi_exc.TooManyRequests)
    _TIMEOUT_EXCS = (gapi_exc.DeadlineExceeded, gapi_exc.ServiceUnavailable)
except ImportError:
    pass

log = structlog.get_logger(__name__)


class GeminiVisionProvider:
    """Multi-modal Gemini provider for visual comparison.

    Default model is ``gemini-2.5-flash`` (multi-modal). Override via ``model``.
    Free tier of Google AI Studio includes vision quota; suitable for eval suites.
    """

    name = "gemini-vision"
    model = "gemini-2.5-flash"

    def __init__(self, api_key: str, model: str | None = None) -> None:
        if not api_key:
            raise RuntimeError("api_key obrigatório (passe via construtor)")
        genai.configure(api_key=api_key)  # type: ignore[attr-defined]
        if model:
            self.model = model
        self._model = genai.GenerativeModel(self.model)  # type: ignore[attr-defined]

    async def compare_images(
        self,
        prompt: str,
        image_paths: list[Path],
        json_schema: dict,
    ) -> dict[str, Any]:
        """Send prompt + image list, request structured JSON response.

        Image labels are inserted as text tags (``[GOLD]``, ``[OUTPUT]``) before each image
        in the order received, so the LLM can refer to them by role.
        """
        if len(image_paths) < 2:
            raise ValueError("compare_images requires at least 2 images (gold + output)")

        roles = ["GOLD", "OUTPUT"] + [f"EXTRA_{i}" for i in range(len(image_paths) - 2)]
        parts: list[Any] = [prompt]
        for role, path in zip(roles, image_paths, strict=False):
            path = Path(path)
            if not path.exists():
                raise FileNotFoundError(f"image not found: {path}")
            parts.append(f"\n[{role}]")
            parts.append(
                {
                    "mime_type": "image/png",
                    "data": path.read_bytes(),
                }
            )

        full_prompt_suffix = "\n\nReturn a JSON object matching this schema:\n" + json.dumps(
            json_schema, ensure_ascii=False
        )
        parts.append(full_prompt_suffix)

        try:
            resp = await self._model.generate_content_async(
                parts,
                generation_config={"response_mime_type": "application/json", "temperature": 0},
            )
        except _RATE_LIMIT_EXCS as e:
            log.warning("gemini_vision.rate_limit", error=str(e))
            raise LLMRateLimit(retry_after=60) from e
        except _TIMEOUT_EXCS as e:
            log.warning("gemini_vision.timeout", error=str(e))
            raise LLMTimeout() from e
        except Exception as e:
            msg = str(e).lower()
            if "rate" in msg or "quota" in msg or "429" in msg:
                raise LLMRateLimit(retry_after=60) from e
            if "timeout" in msg or "deadline" in msg:
                raise LLMTimeout() from e
            log.error("gemini_vision.error", error=str(e), error_type=type(e).__name__)
            raise LLMError(str(e)) from e

        if not resp.candidates:
            log.error("gemini_vision.no_candidates")
            raise LLMError("Gemini retornou resposta sem candidatos (possível filtro de segurança)")

        try:
            return json.loads(resp.text)
        except json.JSONDecodeError as e:
            log.error("gemini_vision.invalid_json", text_preview=resp.text[:500])
            raise LLMError(f"JSON inválido: {e}") from e
