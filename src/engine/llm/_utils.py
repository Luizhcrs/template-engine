"""Internal helpers shared across providers."""

from __future__ import annotations


def retry_after_from_error(e: Exception, default: int = 60) -> int:
    """Extract retry-after from response headers or exception attribute, fallback to default.

    Looks for headers in this order: ``retry-after``, ``Retry-After``, ``x-ratelimit-reset``.
    Then checks ``e.retry_after`` attribute. If nothing found, returns ``default``.

    Used by all OpenAI-compatible providers (OpenAI, Anthropic, Groq, OpenRouter).
    """
    response = getattr(e, "response", None)
    if response is not None:
        headers = getattr(response, "headers", {}) or {}
        for key in ("retry-after", "Retry-After", "x-ratelimit-reset"):
            value = headers.get(key)
            if value:
                try:
                    return int(float(value))
                except (TypeError, ValueError):
                    pass
    attr = getattr(e, "retry_after", None)
    if attr:
        try:
            return int(float(attr))
        except (TypeError, ValueError):
            pass
    return default
