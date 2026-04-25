"""02 — Custom LLM provider.

Como implementar um provider próprio que satisfaz `engine.llm.base.LLMProvider`.
Útil pra integrar OpenAI, Anthropic, Ollama, ou qualquer SDK que retorne JSON.

Demonstra também o uso de mock pra desenvolvimento sem chamar API real.
"""
from __future__ import annotations
import asyncio
import json
from pathlib import Path

from engine import create_preset, load_preset
from engine.llm.base import LLMError


class MockProvider:
    """Provider determinístico pra dev/CI. Não faz chamadas externas."""

    name = "mock"
    model = "mock-1.0"

    def __init__(self, response: dict) -> None:
        self._response = response

    async def generate_structured(self, prompt: str, json_schema: dict) -> dict:
        # Em provider real você chamaria SDK; aqui apenas devolve resposta fixa.
        if not isinstance(self._response, dict):
            raise LLMError("response deve ser dict")
        return self._response


async def main() -> None:
    fixtures = Path(__file__).parent.parent / "tests" / "fixtures"

    fake_preset_response = {
        "pattern_md": "# Padrão simulado\nApenas pra demo.",
        "content_schema": {
            "type": "object",
            "properties": {"titulo": {"type": "string"}},
            "required": ["titulo"],
        },
        "render_ops": [
            {"op": "set_header_field", "params": {"name": "CODIGO", "source_key": "codigo"}}
        ],
        "validation": {"critical_tokens": [], "required_sections": [], "min_completeness": 0.7},
    }

    out_dir = Path("./out/custom-provider-demo")
    provider = MockProvider(response=fake_preset_response)

    await create_preset(
        llm=provider,
        template_path=fixtures / "template_sample.docx",
        gold_paths=[fixtures / "gold_sample_01.docx"],
        dest_dir=out_dir,
    )

    bundle = load_preset(out_dir)
    print(f"preset criado: {bundle.manifest.slug} ({bundle.manifest.name})")
    print(f"render ops: {[op.op for op in bundle.render_ops.operations]}")
    print(f"\nschema:\n{json.dumps(bundle.schema_json, indent=2, ensure_ascii=False)}")


if __name__ == "__main__":
    asyncio.run(main())
