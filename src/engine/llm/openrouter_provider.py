"""OpenRouter provider — uses openai SDK with base_url override.

OpenRouter aggregates 400+ models behind an OpenAI-compatible API. This provider is a
thin subclass of OpenAIProvider with the base_url pointing to openrouter.
"""

from __future__ import annotations

from .openai_provider import OpenAIProvider


class OpenRouterProvider(OpenAIProvider):
    """OpenRouter provider — pick any model from openrouter.ai/models."""

    name = "openrouter"
    model = "openai/gpt-4o-mini"

    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        timeout: float = 60.0,
        site_url: str | None = None,
        app_name: str | None = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model,
            base_url="https://openrouter.ai/api/v1",
            timeout=timeout,
        )
        # OpenRouter recommends sending HTTP-Referer + X-Title for analytics/ranking
        if site_url or app_name:
            extra_headers = {}
            if site_url:
                extra_headers["HTTP-Referer"] = site_url
            if app_name:
                extra_headers["X-Title"] = app_name
            self._client = self._client.with_options(default_headers=extra_headers)
