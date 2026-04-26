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


if __name__ == "__main__":
    app()
