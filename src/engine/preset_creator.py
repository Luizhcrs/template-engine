from __future__ import annotations
import json
import shutil
from pathlib import Path
from datetime import datetime, timezone
import yaml
from engine.llm.base import LLMProvider
from engine.extractor import extract
from engine.preset_schemas import PresetManifest
import logging

log = logging.getLogger(__name__)

CREATOR_SCHEMA = {
    "type": "object",
    "properties": {
        "pattern_md": {"type": "string"},
        "content_schema": {"type": "object"},
        "render_ops": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "op": {"type": "string"},
                    "params": {"type": "object"},
                },
            },
        },
        "validation": {
            "type": "object",
            "properties": {
                "critical_tokens": {"type": "array"},
                "required_sections": {"type": "array"},
                "min_completeness": {"type": "number"},
            },
        },
    },
    "required": ["pattern_md", "content_schema", "render_ops", "validation"],
}


def _build_prompt(template_text: str, gold_texts: list[str]) -> str:
    golds_block = "\n\n".join([f"## Gold doc {i+1}\n{g[:8000]}" for i, g in enumerate(gold_texts)])
    return f"""Analise o template-alvo e os documentos de referencia (gold docs). Sua tarefa e
identificar o padrao visual, estrutural, semantico e estilistico e retornar um objeto JSON com:

1. `pattern_md`: descricao em markdown do padrao detectado (estrutura, tom, vocabulario,
   regras implicitas, convencoes tipograficas). Se houver ambiguidades, decida a opcao
   mais provavel e registre como "> Decisao do analisador: X".

2. `content_schema`: JSON Schema com os campos que o LLM deve extrair de documentos-fonte
   futuros pra alimentar o renderer.

3. `render_ops`: lista de operacoes deterministicas. Ops disponiveis:
   - set_header_field (params: name, source_key)
   - write_section (params: heading, source_key)
   - write_list (params: heading, source_key, marker)
   - write_table (params: heading, source_key, columns)
   - write_steps (params: heading, source_key, prefix, note_prefix)
   - write_auto_migration (params: heading, columns, default_text, source_key)

4. `validation`: {{ critical_tokens: [{{name, regex}}], required_sections: [...], min_completeness: 0.7 }}

# Template-alvo:
{template_text[:8000]}

# Gold docs:
{golds_block}
"""


async def create_preset(
    llm: LLMProvider,
    slug: str,
    name: str,
    template_path: Path,
    gold_paths: list[Path],
    dest_dir: Path,
    owner_sub: str | None,
) -> Path:
    """Generate and save a full preset bundle. Single LLM call, no conversation."""
    dest_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy(template_path, dest_dir / "template.docx")
    gold_dir = dest_dir / "gold"
    gold_dir.mkdir(exist_ok=True)
    for i, g in enumerate(gold_paths, 1):
        shutil.copy(g, gold_dir / f"gold-{i:02d}.docx")

    template_text = extract(template_path).text
    gold_texts = [extract(g).text for g in gold_paths]

    prompt = _build_prompt(template_text, gold_texts)
    log.info("preset_creator.call", slug=slug, gold_count=len(gold_paths))
    result = await llm.generate_structured(prompt, CREATOR_SCHEMA)

    (dest_dir / "pattern.md").write_text(result["pattern_md"], encoding="utf-8")
    (dest_dir / "schema.json").write_text(
        json.dumps(result["content_schema"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (dest_dir / "render_ops.yaml").write_text(
        yaml.safe_dump({"operations": result["render_ops"]}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    (dest_dir / "validation.yaml").write_text(
        yaml.safe_dump(result["validation"], allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    manifest = PresetManifest(
        slug=slug,
        name=name,
        version=1,
        owner_sub=owner_sub,
        locked=False,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    (dest_dir / "manifest.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

    log.info("preset_creator.ok", slug=slug, path=str(dest_dir))
    return dest_dir
