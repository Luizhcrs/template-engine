"""Run mode='llm' against every adversarial fixture pair and dump the
output for inspection.

Loads ``OPENAI_API_KEY`` from ``.env`` at the project root.

Outputs go to ``tests/<vendor>/output_llm.docx`` and a JSON sidecar
``tests/<vendor>/report.json`` with the SectionMappingReport summary.
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


VENDORS = ("vendor_c", "vendor_d", "vendor_e")


async def main() -> None:
    _load_env()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY not set; populate .env")

    provider = OpenAIProvider(api_key=api_key, model="gpt-4o", timeout=300.0)

    for vendor in VENDORS:
        base = Path("tests") / vendor
        template_path = base / "template.docx"
        source_path = base / "source.docx"
        output_path = base / "output_llm.docx"
        report_path = base / "report.json"
        if not template_path.exists() or not source_path.exists():
            print(f"[skip] {vendor}: missing fixture")
            continue
        print(f"[run] {vendor}")
        # Debug: capture the raw mapping plan separately so we can see
        # exactly what the LLM returned per vendor.
        from engine.section_mapper.auto_mapper import build_mapping_plan
        from engine.section_mapper.source_profiler import profile_source
        from engine.section_mapper.template_profiler import profile_template

        ts = profile_template(template_path)
        ss = profile_source(source_path)
        plan = await build_mapping_plan(ts, ss, llm=provider)
        plan_path = base / "plan.json"
        plan_path.write_text(
            json.dumps(plan.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

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
        non_empty_sections = sum(1 for v in plan.section_content.values() if v.strip())
        total_sections = len(plan.section_content)
        print(
            f"  filled={non_empty_sections}/{total_sections} sections "
            f"+ {len(plan.paragraph_rewrites)} rewrites "
            f"+ {report.tables_filled} tables "
            f"+ {len(plan.header_substitutions)} header subs "
            f"| orphans={len(report.orphan_paragraphs)}"
        )


if __name__ == "__main__":
    asyncio.run(main())
