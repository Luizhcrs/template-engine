# Providers — Overview

6 LLM providers ship with template-engine. All implement the `engine.llm.base.LLMProvider` Protocol and accept the same interface: `generate_structured(prompt, json_schema) -> dict`.

## Comparison

| Provider | Strategy | Best for | Install extra |
|---|---|---|---|
| **Gemini** | `response_mime_type=application/json` | Free tier, Brazilian users | `[gemini]` |
| **OpenAI** | `response_format=json_schema` strict | Production, structured outputs | `[openai]` |
| **Anthropic** | Forced tool use | Long context, accuracy | `[anthropic]` |
| **Groq** | `json_object` mode | Fastest inference | `[groq]` |
| **Ollama** | Local `/api/generate` | Air-gapped, no API costs | `[ollama]` |
| **OpenRouter** | OpenAI-compatible w/ alt base_url | Access 400+ models | `[openrouter]` |

## Quick examples

### Gemini

```python
from engine.llm.gemini_free import GeminiFreeProvider
provider = GeminiFreeProvider(api_key="AIza...")
```

### OpenAI

```python
from engine.llm.openai_provider import OpenAIProvider
provider = OpenAIProvider(api_key="sk-...", model="gpt-4o-mini")
```

### Anthropic

```python
from engine.llm.anthropic_provider import AnthropicProvider
provider = AnthropicProvider(api_key="sk-ant-...", model="claude-sonnet-4-5")
```

### Groq

```python
from engine.llm.groq_provider import GroqProvider
provider = GroqProvider(api_key="gsk_...", model="llama-3.3-70b-versatile")
```

### Ollama (local)

```python
from engine.llm.ollama_provider import OllamaProvider
provider = OllamaProvider(model="llama3.1", base_url="http://localhost:11434")
```

### OpenRouter

```python
from engine.llm.openrouter_provider import OpenRouterProvider
provider = OpenRouterProvider(
    api_key="sk-or-...",
    model="anthropic/claude-sonnet-4-5",
    site_url="https://yourapp.com",
    app_name="YourApp",
)
```

## Router (fallback chain)

Wrap multiple providers; on `LLMRateLimit` / `LLMTimeout`, automatically falls back to the next.

```python
from engine.llm import LLMRouter
from engine.llm.groq_provider import GroqProvider
from engine.llm.gemini_free import GeminiFreeProvider

router = LLMRouter([
    GroqProvider(api_key=g_key),         # primary (fast + cheap)
    GeminiFreeProvider(api_key=ge_key),  # fallback (free)
])

result = await router.generate_structured(prompt, schema)
```

Generic `LLMError` propagates **without** fallback — the router only retries transient failures.

## Add a custom provider

```python
from engine.llm.base import LLMError, LLMRateLimit, LLMTimeout

class MyProvider:
    name = "my-provider"
    model = "default"

    def __init__(self, api_key: str, model: str | None = None) -> None:
        if not api_key:
            raise RuntimeError("api_key required")
        if model:
            self.model = model
        # ... initialize SDK

    async def generate_structured(self, prompt: str, json_schema: dict) -> dict:
        # ... call API, return parsed JSON
        # raise LLMRateLimit / LLMTimeout / LLMError as appropriate
        ...
```

See [Contributing](../contributing.md) for the full provider checklist.
