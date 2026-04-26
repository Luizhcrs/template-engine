# Contributing

Thanks for considering a contribution.

The full contributor guide lives in [`CONTRIBUTING.md`](https://github.com/Luizhcrs/template-engine/blob/main/CONTRIBUTING.md) at the repo root. Highlights:

- **Setup**: `pip install -e ".[dev]"` then `pre-commit install`
- **Tests**: `pytest` (36 tests today)
- **Lint + types + format**: `ruff check . && ruff format --check . && mypy src/engine`
- **Conventional Commits**: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`
- **One concern per PR**

## Add a provider checklist

1. Implement `engine.llm.<name>_provider.py` matching `LLMProvider` Protocol
2. Add unit tests in `tests/test_llm_<name>.py` mirroring `tests/test_llm_gemini.py`
3. Add SDK as optional dep in `pyproject.toml`: `[project.optional-dependencies] <name> = ["sdk>=x"]`
4. Document in `docs/providers/index.md` (both EN + `.pt.md`)
5. Add CHANGELOG entry under `[Unreleased]`

## Reporting bugs

GitHub issue with: Python version, OS, template-engine version, minimal repro, expected vs actual behavior.

For security issues see [`SECURITY.md`](https://github.com/Luizhcrs/template-engine/blob/main/SECURITY.md).
