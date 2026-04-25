from __future__ import annotations
from engine.preset_schemas import PresetBundle
from engine.llm.base import LLMProvider
from engine.extractor import extract
import logging

log = logging.getLogger(__name__)

_MAX_GOLD_DOCS = 3
_MAX_SOURCE_CHARS = 12000
_MAX_GOLD_CHARS = 8000


def _build_prompt(preset: PresetBundle, source_text: str, gold_texts: list[str]) -> str:
    gold_section = ""
    if gold_texts:
        gold_section = "\n\n# Exemplos de documentos no padrão desejado:\n\n"
        for i, g in enumerate(gold_texts, 1):
            gold_section += f"## Exemplo {i}\n{g[:_MAX_GOLD_CHARS]}\n\n"

    return (
        f"# Padrão deste template\n{preset.pattern_md}\n"
        f"{gold_section}"
        f"# Documento fonte (texto bruto a ser normalizado):\n{source_text[:_MAX_SOURCE_CHARS]}\n\n"
        f"Extraia o conteúdo do documento-fonte e organize-o conforme o padrão descrito, "
        f"preservando TODOS os termos técnicos, códigos e siglas exatamente como no fonte. "
        f"Retorne um objeto JSON que siga o schema fornecido."
    )


async def map_content(preset: PresetBundle, source_text: str, llm: LLMProvider) -> dict:
    """Build prompt with preset pattern + few-shot gold docs and call LLM.

    Returns the JSON content dict produced by the LLM, conforming to
    `preset.schema_json`. Consumers validate the result downstream.
    """
    gold_texts = [extract(p).text for p in preset.gold_docs_paths[:_MAX_GOLD_DOCS]]
    prompt = _build_prompt(preset, source_text, gold_texts)

    log.info(
        "llm_mapper.call",
        preset=preset.manifest.slug,
        source_chars=len(source_text),
        gold_count=len(gold_texts),
    )
    content = await llm.generate_structured(prompt, preset.schema_json)
    log.info("llm_mapper.ok", keys=list(content.keys()))
    return content
