"""01 — Quickstart end-to-end.

Cria preset a partir de template + 1 gold doc, depois converte um source.

Uso:
    GEMINI_API_KEY=AIza... python examples/01_quickstart.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from engine import create_preset, extract, load_preset, map_content, render
from engine.llm.gemini_free import GeminiFreeProvider


async def main() -> None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERRO: defina GEMINI_API_KEY no ambiente.", file=sys.stderr)
        sys.exit(1)

    fixtures = Path(__file__).parent.parent / "tests" / "fixtures"
    template = fixtures / "template_sample.docx"
    gold = fixtures / "gold_sample_01.docx"
    source = fixtures / "fonte_sample.docx"

    if not all(p.exists() for p in (template, gold, source)):
        print("ERRO: fixtures não encontrados em tests/fixtures/", file=sys.stderr)
        sys.exit(1)

    out_dir = Path("./out")
    out_dir.mkdir(exist_ok=True)
    preset_dir = out_dir / "my-template"
    output_doc = out_dir / "result.docx"

    provider = GeminiFreeProvider(api_key=api_key)

    print("[1/4] aprendendo padrão a partir do template + gold docs...")
    await create_preset(
        llm=provider,
        template_path=template,
        gold_paths=[gold],
        dest_dir=preset_dir,
    )
    print(f"      preset salvo em {preset_dir}")

    print("[2/4] carregando preset...")
    preset = load_preset(preset_dir)

    print("[3/4] extraindo + mapeando documento-fonte...")
    doc = extract(source)
    data = await map_content(preset, doc.text, provider)

    print("[4/4] renderizando .docx final...")
    render(preset, data, output_path=output_doc)

    print(f"\n[OK] saída: {output_doc.resolve()}")


if __name__ == "__main__":
    asyncio.run(main())
