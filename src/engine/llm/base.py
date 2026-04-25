from __future__ import annotations
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
    name: str
    model: str

    async def generate_structured(self, prompt: str, json_schema: dict) -> dict: ...
