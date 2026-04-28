"""template-engine CLI.

Commands:

- ``template-engine info`` — version + available providers
- ``template-engine extract <path>`` — extract text/tables from .docx/.pdf
- ``template-engine normalize`` — batch: 1 template + N source docs → N normalized
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
from engine.extractor import extract as engine_extract

app = typer.Typer(
    name="template-engine",
    help="Document normalization engine — batch orchestrator: regex first, LLM fallback.",
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
            f"provider {name!r} not installed. Try: pip install 'template-engine-ia[{name}]'"
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
            "Install missing providers via [bold]pip install 'template-engine-ia[<name>]'[/bold]\n"
            "Or all at once: [bold]pip install 'template-engine-ia[all]'[/bold]",
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


@app.command(name="list-formats")
def cmd_list_formats() -> None:
    """List all bundled formats."""
    from engine.formats import describe_formats

    table = Table(title="Bundled formats", show_header=True, header_style="bold")
    table.add_column("Name", style="bold")
    table.add_column("Spec")
    table.add_column("Fields")
    table.add_column("Title")
    for entry in describe_formats():
        table.add_row(
            entry["name"],
            entry["spec"],
            str(len(entry["fields"])),
            entry["title"],
        )
    console.print(table)
    console.print(
        Panel(
            "Use [bold]--format <name>[/bold] in [bold]normalize[/bold] or "
            "[bold]conformity[/bold] to apply a bundled format.",
            border_style="dim",
        )
    )


@app.command()
def normalize(
    template: Annotated[
        Path | None,
        typer.Option("--template", help="Template .docx with placeholder tokens"),
    ] = None,
    source_dir: Annotated[
        Path | None,
        typer.Option("--source-dir", help="Directory containing source .docx/.pdf files"),
    ] = None,
    output_dir: Annotated[
        Path | None, typer.Option("--output-dir", help="Where normalized outputs go")
    ] = None,
    format_name: Annotated[
        str | None,
        typer.Option("--format", help="Use a bundled format (run list-formats to see options)"),
    ] = None,
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
    """Normalize a directory of source documents against a template (batch).

    Pipeline: schema_inference → pattern_inference (if golds given) →
    hybrid_mapper (regex first, LLM fallback) → token-substitution renderer →
    semantic_diff (if LLM given). Output buckets each doc into high/medium/low
    confidence tiers.

    With ``--format <name>`` the bundled format provides gold docs + field
    examples + recommended threshold; you still pass ``--template`` (the
    standard target template) and ``--source-dir`` / ``--output-dir``.
    """
    from engine.batch import normalize_batch
    from engine.formats import FormatNotFound, load_format

    fmt = None
    if format_name:
        try:
            fmt = load_format(format_name)
        except FormatNotFound as e:
            raise typer.BadParameter(str(e)) from e
        console.print(f"[bold]Format:[/bold] {fmt.name} ({fmt.spec})")

    if template is None or source_dir is None or output_dir is None:
        raise typer.BadParameter("--template, --source-dir, --output-dir are required")
    if not template.exists():
        raise typer.BadParameter(f"--template not found: {template}")
    if not source_dir.exists():
        raise typer.BadParameter(f"--source-dir not found: {source_dir}")

    llm = None
    if provider:
        llm = _build_provider(provider, api_key, model)
        console.print(f"[bold]Provider:[/bold] {provider} ({getattr(llm, 'model', '?')})")
    else:
        console.print("[bold dim]Running in regex-only mode (no LLM provider)[/bold dim]")

    gold_docs_text: list[str] | None = None
    if gold_doc:
        gold_docs_text = [engine_extract(p).text for p in gold_doc]
        console.print(f"[dim]Loaded {len(gold_docs_text)} gold doc(s) from --gold-doc[/dim]")
    elif fmt is not None:
        gold_docs_text = list(fmt.gold_docs)
        console.print(f"[dim]Loaded {len(gold_docs_text)} gold doc(s) from format {fmt.name}[/dim]")

    field_examples_dict: dict[str, list[str]] | None = None
    if field_examples_json:
        field_examples_dict = json.loads(field_examples_json.read_text(encoding="utf-8"))
        console.print(f"[dim]Loaded {len(field_examples_dict)} field example(s) from JSON[/dim]")
    elif fmt is not None:
        field_examples_dict = dict(fmt.field_examples)
        console.print(f"[dim]Loaded {len(field_examples_dict)} field example(s) from format {fmt.name}[/dim]")

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

    summary_table = Table(
        title=f"Batch summary — {total} document(s)",
        show_header=True,
        header_style="bold",
    )
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


@app.command()
def conformity(
    template: Annotated[Path, typer.Option("--template", help="Template .docx (gold standard)", exists=True)],
    candidate: Annotated[Path, typer.Option("--candidate", help="Candidate .docx to evaluate", exists=True)],
    format_name: Annotated[
        str | None,
        typer.Option("--format", help="Use a bundled format (overrides default weights + threshold)"),
    ] = None,
    provider: Annotated[
        str | None,
        typer.Option("--provider", help="LLM provider for text dimension (omit to skip)"),
    ] = None,
    model: Annotated[str | None, typer.Option("--model", help="Override model id")] = None,
    api_key: Annotated[str | None, typer.Option("--api-key", help="API key (or use env var)")] = None,
    dimensions: Annotated[
        str,
        typer.Option(
            "--dimensions",
            help="Comma-separated subset of: text,structural,visual,design,technical",
        ),
    ] = "text,structural,visual,design,technical",
    threshold: Annotated[
        float, typer.Option("--threshold", help="Pass/fail cutoff for is_conformant")
    ] = 0.85,
    json_path: Annotated[
        Path | None, typer.Option("--json", help="Where to write the conformity report JSON")
    ] = None,
) -> None:
    """Multi-dimensional conformity check.

    Evaluates whether a candidate document conforms to a template across up to
    five dimensions: text (LLM), structural (docx parsing), visual (ascii layout),
    design (multimodal LLM, optional), technical (format validators).

    With ``--format <name>`` the bundled format provides the conformity weights
    and recommended threshold (overridable by ``--threshold``).
    """
    from engine.conformity import check_conformity
    from engine.formats import FormatNotFound, load_format

    fmt = None
    weights: dict[str, float] | None = None
    if format_name:
        try:
            fmt = load_format(format_name)
        except FormatNotFound as e:
            raise typer.BadParameter(str(e)) from e
        weights = dict(fmt.conformity_weights)
        if threshold == 0.85:
            threshold = fmt.recommended_threshold
        console.print(f"[bold]Format:[/bold] {fmt.name} ({fmt.spec})")

    llm = None
    if provider:
        llm = _build_provider(provider, api_key, model)
        console.print(f"[bold]Provider:[/bold] {provider} ({getattr(llm, 'model', '?')})")
    else:
        console.print("[bold dim]No LLM provider — text + design dimensions will be skipped[/bold dim]")

    dims = [d.strip() for d in dimensions.split(",") if d.strip()]
    console.print(f"[dim]Dimensions: {', '.join(dims)}[/dim]")

    with console.status("checking conformity...", spinner="dots"):
        report = asyncio.run(
            check_conformity(
                template_path=template,
                candidate_path=candidate,
                llm=llm,
                visual_llm=None,
                dimensions=dims,
                threshold=threshold,
                weights=weights,
            )
        )

    verdict_color = "green" if report.is_conformant else "red"
    console.print(
        Panel.fit(
            f"[bold]{'CONFORMANT' if report.is_conformant else 'NON_CONFORMANT'}[/bold]\n"
            f"Score: [{verdict_color}]{report.score:.3f}[/{verdict_color}] (threshold: {report.threshold:.2f})\n"
            f"Failures: {len(report.failures)} (critical: {len(report.critical_failures)})",
            title="Conformity verdict",
            border_style=verdict_color,
        )
    )

    table = Table(title="Per-dimension scores", show_header=True, header_style="bold")
    table.add_column("Dimension", style="bold")
    table.add_column("Score", justify="right")
    table.add_column("Failures", justify="right")
    table.add_column("Status")
    for name, dr in report.by_dimension.items():
        if dr.skipped:
            status = f"[dim]skipped: {dr.skip_reason}[/dim]"
        elif dr.score >= 0.95:
            status = "[green]ok[/green]"
        elif dr.score >= 0.7:
            status = "[yellow]warning[/yellow]"
        else:
            status = "[red]critical[/red]"
        table.add_row(name, f"{dr.score:.3f}", str(len(dr.failures)), status)
    console.print(table)

    if report.failures:
        fail_table = Table(title="Failures", show_header=True, header_style="bold")
        fail_table.add_column("Dimension")
        fail_table.add_column("Field")
        fail_table.add_column("Severity")
        fail_table.add_column("Note")
        for f in report.failures[:25]:
            sev_color = {"critical": "red", "warning": "yellow", "info": "dim"}.get(f.severity, "white")
            fail_table.add_row(
                f.dimension,
                f.field_or_excerpt,
                f"[{sev_color}]{f.severity}[/{sev_color}]",
                f.note,
            )
        console.print(fail_table)
        if len(report.failures) > 25:
            console.print(f"[dim]... +{len(report.failures) - 25} more (see --json)[/dim]")

    if json_path:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        console.print(f"[dim]report -> {json_path.resolve()}[/dim]")


@app.command(name="map-sections")
def cmd_map_sections(
    template: Annotated[
        Path,
        typer.Option("--template", help="Template .docx with empty sections / placeholders", exists=True),
    ],
    source: Annotated[Path, typer.Option("--source", help="Source document (.docx / .pdf)", exists=True)],
    output: Annotated[Path, typer.Option("--output", help="Where to write the filled .docx")],
    mode: Annotated[
        str | None,
        typer.Option(
            "--mode",
            help="rules / llm / hybrid. Auto: llm when --provider supplied, else rules.",
        ),
    ] = None,
    provider: Annotated[
        str | None,
        typer.Option(
            "--provider", help="LLM provider name (gemini / openai / anthropic / groq / ollama / openrouter)"
        ),
    ] = None,
    model: Annotated[str | None, typer.Option("--model", help="Override model id")] = None,
    api_key: Annotated[str | None, typer.Option("--api-key", help="API key (or use env var)")] = None,
    no_cache: Annotated[
        bool,
        typer.Option("--no-cache", help="Skip the on-disk plan cache for this run"),
    ] = False,
    json_path: Annotated[
        Path | None,
        typer.Option("--json", help="Where to write the SectionMappingReport JSON"),
    ] = None,
) -> None:
    """Fill a structural template (no ``{{X}}`` tokens) from a source document.

    rules mode or LLM mode mapping depending on whether a
    ``--provider`` is supplied:

    - No provider → ``rules`` mode (PT-BR / Engeman heuristics).
    - With provider → ``llm`` mode (vendor-agnostic, ~$0.001/doc with
      Gemini Flash, ~$0.05/doc with gpt-4o).

    On-disk plan cache keyed by template + source SHA-256 — the second
    run of the same pair pays no LLM cost.
    """
    from engine.section_mapper import map_sections, map_sections_async

    output.parent.mkdir(parents=True, exist_ok=True)

    llm_provider = None
    if provider:
        llm_provider = _build_provider(provider, api_key, model)

    if mode is None:
        mode = "llm" if llm_provider is not None else "rules"

    if mode == "rules":
        report = map_sections(
            template_path=template,
            source_path=source,
            output_path=output,
        )
    else:
        if llm_provider is None:
            raise typer.BadParameter(
                f"mode={mode!r} requires --provider (e.g. --provider openai --api-key ...)"
            )

        # The async path supports both 'llm' and 'hybrid' modes.
        async def _run() -> SectionMappingReport:  # type: ignore[name-defined]
            return await map_sections_async(
                template_path=template,
                source_path=source,
                output_path=output,
                llm=llm_provider,
                mode=mode,
            )

        report = asyncio.run(_run())

    console.print(
        Panel.fit(
            f"[bold green]OK[/bold green] mode=[bold]{mode}[/bold]\n"
            f"sections mapped: {report.mapped_count} / {len(report.target_sections)}\n"
            f"tables filled: {report.tables_filled}\n"
            f"orphan paragraphs: {len(report.orphan_paragraphs)}\n"
            f"output: {output.resolve()}",
            title="map-sections result",
            border_style="green",
        )
    )

    if json_path:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        console.print(f"[dim]report -> {json_path.resolve()}[/dim]")


# Keep the SectionMappingReport import name resolvable for the
# annotation in cmd_map_sections at runtime (typer evaluates the
# annotation lazily but mypy / docs prefer it visible).
from engine.section_mapper import SectionMappingReport  # noqa: E402, TC001

if __name__ == "__main__":
    app()
