from __future__ import annotations

from pathlib import Path  # noqa: TC003 - runtime Protocol annotation
from typing import Protocol


class LLMError(Exception):
    """Base class for LLM provider errors."""


class LLMRateLimit(LLMError):
    def __init__(self, retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(f"rate limited, retry after {retry_after}s")


class LLMTimeout(LLMError):
    pass


class LLMProvider(Protocol):
    """Text-only LLM provider. Returns structured JSON from text prompts."""

    name: str
    model: str

    async def generate_structured(self, prompt: str, json_schema: dict) -> dict: ...


class VisualLLMProvider(Protocol):
    """Multi-modal LLM provider. Accepts images alongside text + returns structured JSON.

    Used by ``engine.visual_validator`` to compare rendered ``.docx`` outputs against gold docs.
    Implementations: ``GeminiVisionProvider``. OpenAI/Anthropic vision providers planned for v0.3+.
    """

    name: str
    model: str

    async def compare_images(
        self,
        prompt: str,
        image_paths: list[Path],
        json_schema: dict,
    ) -> dict: ...
