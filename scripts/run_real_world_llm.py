"""Run mode='llm' against every real-world template in
``tests/real_world/`` and dump output + report.

Real templates downloaded from public sources (UNIFAP, Corentocantins).
Sources are realistic POP content built by ``build_real_world_source.py``.

Usage:
    python scripts/build_real_world_source.py
    python scripts/run_real_world_llm.py
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from engine.llm.openai_provider import OpenAIProvider
from engine.section_mapper import map_sections_async


def _load_env() -> None:
    env_path = Path(".env")
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()


PAIRS = (
    ("pop_unifap.docx", "source_unifap.docx"),
    ("pop_corentoc.docx", "source_corentoc.docx"),
)


async def main() -> None:
    _load_env()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY not set; populate .env")

    provider = OpenAIProvider(api_key=api_key, model="gpt-4o", timeout=300.0)

    base = Path("tests/real_world")

    for template_name, source_name in PAIRS:
        template_path = base / template_name
        source_path = base / source_name
        if not template_path.exists() or not source_path.exists():
            print(f"[skip] missing fixture: {template_name} / {source_name}")
            continue

        out_name = f"output_{template_name}"
        report_name = f"report_{template_name}.json"
        output_path = base / out_name
        report_path = base / report_name

        print(f"[run] {template_name} <- {source_name}")
        report = await map_sections_async(
            template_path=template_path,
            source_path=source_path,
            output_path=output_path,
            mode="llm",
            llm=provider,
        )

        report_path.write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        print(
            f"  sections mapped: {report.mapped_count} / {len(report.target_sections)} "
            f"| tables: {report.tables_filled} "
            f"| orphans: {len(report.orphan_paragraphs)}"
        )


if __name__ == "__main__":
    asyncio.run(main())
