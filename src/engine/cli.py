"""template-engine CLI.

Commands:

- ``template-engine info`` — version + available providers
- ``template-engine extract <path>`` — extract text/tables from .docx/.pdf
- ``template-engine convert <source> --preset <dir> --output <out> --provider gemini --api-key ...``
- ``template-engine version`` — print version and exit
"""

from __future__ import annotations

import asyncio
import importlib
import json
import os
from pathlib import Path  # noqa: TC003 - runtime needed by typer.Argument
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from engine import __version__
from engine.confidence import calculate_confidence, confidence_label
from engine.extractor import extract as engine_extract
from engine.llm_mapper import map_content
from engine.preset_loader import load_preset
from engine.renderer import render
from engine.validator import validate
from engine.visual_validator import validate_visual as engine_validate_visual

app = typer.Typer(
    name="template-engine",
    help="Document normalization engine — learn templates from examples and convert any document via LLM.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

console = Console()


_PROVIDER_REGISTRY: dict[str, tuple[str, str, str]] = {
    # name: (module_path, class_name, env_var_for_api_key)
    "gemini": ("engine.llm.gemini_free", "GeminiFreeProvider", "GEMINI_API_KEY"),
    "openai": ("engine.llm.openai_provider", "OpenAIProvider", "OPENAI_API_KEY"),
    "anthropic": ("engine.llm.anthropic_provider", "AnthropicProvider", "ANTHROPIC_API_KEY"),
    "groq": ("engine.llm.groq_provider", "GroqProvider", "GROQ_API_KEY"),
    "ollama": ("engine.llm.ollama_provider", "OllamaProvider", ""),
    "openrouter": ("engine.llm.openrouter_provider", "OpenRouterProvider", "OPENROUTER_API_KEY"),
}


def _provider_available(name: str) -> bool:
    module_path, _, _ = _PROVIDER_REGISTRY[name]
    try:
        importlib.import_module(module_path)
    except ImportError:
        return False
    return True


def _build_provider(name: str, api_key: str | None, model: str | None):
    if name not in _PROVIDER_REGISTRY:
        available = ", ".join(_PROVIDER_REGISTRY.keys())
        raise typer.BadParameter(f"unknown provider {name!r}. Available: {available}")
    module_path, class_name, env_var = _PROVIDER_REGISTRY[name]
    try:
        module = importlib.import_module(module_path)
    except ImportError as e:
        raise typer.BadParameter(
            f"provider {name!r} not installed. Try: pip install 'template-engine[{name}]'"
        ) from e
    cls = getattr(module, class_name)
    if name == "ollama":
        return cls(model=model) if model else cls()
    api_key = api_key or os.environ.get(env_var, "")
    if not api_key:
        raise typer.BadParameter(f"--api-key required (or set ${env_var}) for provider {name!r}")
    return cls(api_key=api_key, model=model) if model else cls(api_key=api_key)


@app.command()
def version() -> None:
    """Print version and exit."""
    console.print(f"template-engine [bold orange3]{__version__}[/bold orange3]")


@app.command()
def info() -> None:
    """Show version, available providers, and module status."""
    table = Table(title=f"template-engine v{__version__}", show_header=True, header_style="bold")
    table.add_column("Provider", style="bold")
    table.add_column("Module")
    table.add_column("Available", justify="center")
    table.add_column("Env var")
    for name, (module_path, _, env_var) in _PROVIDER_REGISTRY.items():
        ok = _provider_available(name)
        table.add_row(
            name,
            module_path,
            "[green]yes[/green]" if ok else "[red]no[/red]",
            env_var or "—",
        )
    console.print(table)
    console.print(
        Panel(
            "Install missing providers via [bold]pip install 'template-engine[<name>]'[/bold]\n"
            "Or all at once: [bold]pip install 'template-engine[all]'[/bold]",
            title="Tips",
            border_style="dim",
        )
    )


@app.command()
def extract(
    path: Annotated[Path, typer.Argument(help="Path to .docx or .pdf file", exists=True)],
    json_out: Annotated[bool, typer.Option("--json", help="Output full ExtractedDoc as JSON")] = False,
) -> None:
    """Extract text/tables/headers from a document."""
    doc = engine_extract(path)
    if json_out:
        payload = {
            "text": doc.text,
            "paragraphs": doc.paragraphs,
            "tables": doc.tables,
            "header_fields": doc.header_fields,
        }
        console.print_json(json.dumps(payload, ensure_ascii=False))
        return

    console.print(
        Panel.fit(
            f"[bold]Paragraphs:[/bold] {len(doc.paragraphs)}\n"
            f"[bold]Tables:[/bold] {len(doc.tables)}\n"
            f"[bold]Chars:[/bold] {len(doc.text)}",
            title=f"[bold]{path.name}[/bold]",
            border_style="orange3",
        )
    )
    if doc.text:
        preview = doc.text[:600] + ("..." if len(doc.text) > 600 else "")
        console.print(Panel(preview, title="Text preview", border_style="dim"))


@app.command()
def convert(
    source: Annotated[Path, typer.Argument(help="Source document (.docx or .pdf)", exists=True)],
    preset: Annotated[Path, typer.Option("--preset", help="Preset directory", exists=True)],
    output: Annotated[Path, typer.Option("--output", "-o", help="Output .docx path")],
    provider: Annotated[str, typer.Option("--provider", help="LLM provider")] = "gemini",
    model: Annotated[str | None, typer.Option("--model", help="Override model id")] = None,
    api_key: Annotated[str | None, typer.Option("--api-key", help="API key (or use env var)")] = None,
    skip_validation: Annotated[bool, typer.Option("--skip-validation", help="Skip validation step")] = False,
) -> None:
    """Run the full pipeline: extract → map → validate → render."""
    bundle = load_preset(preset)
    llm = _build_provider(provider, api_key, model)

    console.print(
        f"[bold]Provider:[/bold] {provider} ({getattr(llm, 'model', '?')})  "
        f"[bold]Preset:[/bold] {bundle.manifest.slug}"
    )

    with console.status("[1/4] extracting source...", spinner="dots"):
        doc = engine_extract(source)

    console.print(f"  paragraphs={len(doc.paragraphs)} tables={len(doc.tables)} chars={len(doc.text)}")

    with console.status("[2/4] calling LLM...", spinner="dots"):
        data = asyncio.run(map_content(bundle, doc.text, llm))

    console.print(f"  keys={list(data.keys())}")

    if not skip_validation:
        with console.status("[3/4] validating...", spinner="dots"):
            result = validate(doc.text, data, bundle.validation)
            score = calculate_confidence(result)
            label = confidence_label(score)
        color = {"high": "green", "medium": "yellow", "low": "red"}[label.value]
        console.print(
            f"  tokens={result.critical_tokens_found}/{result.critical_tokens_total} "
            f"sections={result.sections_present}/{result.sections_required} "
            f"score={score:.2f} [{color}]{label.value}[/{color}]"
        )

    with console.status("[4/4] rendering...", spinner="dots"):
        render(bundle, data, output_path=output)

    console.print(f"\n[bold green]OK[/bold green] -> {output.resolve()}")


@app.command(name="visual-validate")
def visual_validate(
    gold: Annotated[Path, typer.Argument(help="Gold/reference .docx", exists=True)],
    output: Annotated[Path, typer.Argument(help="Output .docx to validate", exists=True)],
    api_key: Annotated[
        str | None, typer.Option("--api-key", help="Gemini API key (or $GEMINI_API_KEY)")
    ] = None,
    model: Annotated[str | None, typer.Option("--model", help="Override Gemini model id")] = None,
    keep_images: Annotated[
        Path | None,
        typer.Option("--keep-images", help="Keep rendered PNGs in this dir for inspection"),
    ] = None,
    dpi: Annotated[int, typer.Option("--dpi", help="Rasterization DPI")] = 150,
) -> None:
    """Compare two .docx visually using Gemini Vision (requires LibreOffice on PATH)."""
    import os

    key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise typer.BadParameter("--api-key required (or set $GEMINI_API_KEY)")

    try:
        from engine.llm.gemini_vision import GeminiVisionProvider
    except ImportError as e:
        raise typer.BadParameter(
            "visual deps missing. Install: pip install 'template-engine[gemini,visual]'"
        ) from e

    llm = GeminiVisionProvider(api_key=key, model=model) if model else GeminiVisionProvider(api_key=key)
    console.print(f"[bold]Visual provider:[/bold] {llm.name} ({llm.model})")

    with console.status("rendering + comparing...", spinner="dots"):
        result = asyncio.run(
            engine_validate_visual(
                gold_path=gold,
                output_path=output,
                llm=llm,
                dpi=dpi,
                keep_images_dir=keep_images,
            )
        )

    color = "green" if result.score >= 0.9 else ("yellow" if result.score >= 0.7 else "red")
    console.print(
        Panel.fit(
            f"[bold]Score:[/bold] [{color}]{result.score:.2f}[/{color}]\n"
            f"[bold]Issues:[/bold] {len(result.issues)} "
            f"(high={sum(1 for i in result.issues if i.severity == 'high')})\n\n"
            f"{result.summary}",
            title="Visual validation",
            border_style=color,
        )
    )

    if result.issues:
        issues_table = Table(show_header=True, header_style="bold")
        issues_table.add_column("Severity")
        issues_table.add_column("Category")
        issues_table.add_column("Description")
        for issue in result.issues:
            sev_color = {"high": "red", "medium": "yellow", "low": "dim"}[issue.severity]
            issues_table.add_row(
                f"[{sev_color}]{issue.severity}[/{sev_color}]",
                issue.category,
                issue.description,
            )
        console.print(issues_table)

    console.print(f"\n[dim]gold image:[/dim] {result.gold_image}")
    console.print(f"[dim]output image:[/dim] {result.output_image}")


@app.command()
def normalize(
    template: Annotated[
        Path, typer.Option("--template", help="Template .docx with placeholder tokens", exists=True)
    ],
    source_dir: Annotated[
        Path,
        typer.Option("--source-dir", help="Directory containing source .docx/.pdf files", exists=True),
    ],
    output_dir: Annotated[Path, typer.Option("--output-dir", help="Where normalized outputs go")],
    provider: Annotated[
        str | None,
        typer.Option("--provider", help="LLM provider for fallback + diff (omit for regex-only)"),
    ] = None,
    model: Annotated[str | None, typer.Option("--model", help="Override model id")] = None,
    api_key: Annotated[str | None, typer.Option("--api-key", help="API key (or use env var)")] = None,
    gold_doc: Annotated[
        list[Path] | None,
        typer.Option("--gold-doc", help="Gold reference doc (repeat for each)", exists=True),
    ] = None,
    field_examples_json: Annotated[
        Path | None,
        typer.Option(
            "--field-examples",
            help="JSON file mapping {field_name: [example_values]}",
            exists=True,
        ),
    ] = None,
    report_path: Annotated[Path | None, typer.Option("--report", help="Where to write report.json")] = None,
    skip_diff: Annotated[bool, typer.Option("--skip-diff", help="Skip semantic diff QA pass")] = False,
    max_concurrent: Annotated[int, typer.Option("--max-concurrent", help="Parallel workers")] = 4,
) -> None:
    """Normalize a directory of source documents against a template (Wave D batch).

    Pipeline: schema_inference → pattern_inference (if golds given) →
    hybrid_mapper (regex first, LLM fallback) → token-substitution renderer →
    semantic_diff (if LLM given). Output buckets each doc into high/medium/low
    confidence tiers.
    """
    from engine.batch import normalize_batch

    llm = None
    if provider:
        llm = _build_provider(provider, api_key, model)
        console.print(f"[bold]Provider:[/bold] {provider} ({getattr(llm, 'model', '?')})")
    else:
        console.print("[bold dim]Running in regex-only mode (no LLM provider)[/bold dim]")

    gold_docs_text: list[str] | None = None
    if gold_doc:
        gold_docs_text = [engine_extract(p).text for p in gold_doc]
        console.print(f"[dim]Loaded {len(gold_docs_text)} gold doc(s)[/dim]")

    field_examples_dict: dict[str, list[str]] | None = None
    if field_examples_json:
        field_examples_dict = json.loads(field_examples_json.read_text(encoding="utf-8"))
        console.print(f"[dim]Loaded {len(field_examples_dict)} field example(s)[/dim]")

    with console.status("normalizing batch...", spinner="dots"):
        report = asyncio.run(
            normalize_batch(
                template_path=template,
                source_dir=source_dir,
                output_dir=output_dir,
                llm=llm,
                gold_docs=gold_docs_text,
                field_examples=field_examples_dict,
                enable_semantic_diff=(not skip_diff),
                max_concurrent=max_concurrent,
            )
        )

    tier_counts = report.by_tier
    total = sum(tier_counts.values())

    summary_table = Table(title=f"Batch summary — {total} document(s)", show_header=True, header_style="bold")
    summary_table.add_column("Tier", style="bold")
    summary_table.add_column("Count", justify="right")
    summary_table.add_column("Meaning")
    summary_table.add_row(
        "[green]high[/green]",
        str(tier_counts["high"]),
        "regex resolved everything, no critical diff",
    )
    summary_table.add_row(
        "[yellow]medium[/yellow]",
        str(tier_counts["medium"]),
        "LLM filled some fields, or warning-level diff",
    )
    summary_table.add_row(
        "[red]low[/red]",
        str(tier_counts["low"]),
        "missing required field or critical discrepancy",
    )
    summary_table.add_row(
        "[dim]error[/dim]",
        str(tier_counts["error"]),
        "extraction or render failure",
    )
    console.print(summary_table)
    console.print(f"[dim]LLM calls: {report.llm_call_count}[/dim]")

    if report_path is None:
        report_path = output_dir / "report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    console.print(f"\n[bold green]OK[/bold green] report -> {report_path.resolve()}")
    console.print(f"[bold green]OK[/bold green] outputs -> {output_dir.resolve()}")


if __name__ == "__main__":
    app()
