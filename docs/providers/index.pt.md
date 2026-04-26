# Provedores — Visão geral

6 provedores LLM já vêm com template-engine. Todos implementam o Protocol `engine.llm.base.LLMProvider` e aceitam a mesma interface: `generate_structured(prompt, json_schema) -> dict`.

## Comparação

| Provider | Estratégia | Quando usar | Extra de install |
|---|---|---|---|
| **Gemini** | `response_mime_type=application/json` | Free tier, usuários BR | `[gemini]` |
| **OpenAI** | `response_format=json_schema` strict | Produção, output estruturado | `[openai]` |
| **Anthropic** | Tool use forçado | Long context, acurácia | `[anthropic]` |
| **Groq** | `json_object` mode | Inferência mais rápida | `[groq]` |
| **Ollama** | `/api/generate` local | Air-gapped, sem custo de API | `[ollama]` |
| **OpenRouter** | OpenAI-compatible com base_url alternativo | Acesso a 400+ modelos | `[openrouter]` |

## Exemplos rápidos

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
    site_url="https://seuapp.com",
    app_name="SeuApp",
)
```

## Router (cadeia de fallback)

Encapsula vários providers; em `LLMRateLimit` / `LLMTimeout`, faz fallback automático pro próximo.

```python
from engine.llm import LLMRouter
from engine.llm.groq_provider import GroqProvider
from engine.llm.gemini_free import GeminiFreeProvider

router = LLMRouter([
    GroqProvider(api_key=g_key),         # primário (rápido + barato)
    GeminiFreeProvider(api_key=ge_key),  # fallback (grátis)
])

result = await router.generate_structured(prompt, schema)
```

`LLMError` genérico propaga **sem** fallback — o router só retenta falhas transientes.

## Adicionar provider customizado

```python
from engine.llm.base import LLMError, LLMRateLimit, LLMTimeout

class MyProvider:
    name = "my-provider"
    model = "default"

    def __init__(self, api_key: str, model: str | None = None) -> None:
        if not api_key:
            raise RuntimeError("api_key obrigatório")
        if model:
            self.model = model
        # ... inicializa SDK

    async def generate_structured(self, prompt: str, json_schema: dict) -> dict:
        # ... chama API, retorna JSON parseado
        # levanta LLMRateLimit / LLMTimeout / LLMError quando apropriado
        ...
```

Veja [Contribuindo](../contributing.md) pra checklist completa de novo provider.
