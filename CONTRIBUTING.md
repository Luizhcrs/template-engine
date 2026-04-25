# Contributing

Thanks for considering a contribution to template-engine.

## Getting started

1. Fork + clone
2. Setup dev env:

```bash
python -m venv .venv
source .venv/bin/activate    # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
pip install pre-commit ruff mypy
pre-commit install
```

3. Run the test suite to confirm setup:

```bash
pytest
```

You should see 29 tests passing.

## Development workflow

### Before committing

Pre-commit hooks run automatically on `git commit`:

- `ruff check --fix` — lint + auto-fix
- `ruff format` — format
- `mypy` — type check (strict mode on `src/engine`)
- standard checks (trailing whitespace, large files, etc)

If a hook fails, fix the issue and re-stage. Don't bypass with `--no-verify`.

### Tests

Add tests for any behavior change. Engine philosophy:

- **Stateless API**: pass paths/dicts in, get paths/dicts out. No env reads, no implicit IO.
- **Async only when LLMs are involved.** Pipeline stages that don't call LLMs are sync.
- **Determinism in renderer.** LLMs only decide content; visual formatting lives in `render_ops.yaml`.

Run focused:

```bash
pytest tests/test_extractor.py -v
pytest tests/test_renderer.py::test_render_with_real_template -v
pytest --cov=engine --cov-report=term
```

### Adding an LLM provider

1. Implement `engine.llm.base.LLMProvider`:

```python
# src/engine/llm/my_provider.py
from __future__ import annotations
import structlog
from .base import LLMError, LLMRateLimit, LLMTimeout

log = structlog.get_logger(__name__)


class MyProvider:
    name = "my-provider"
    model = "default-model"

    def __init__(self, api_key: str, model: str | None = None) -> None:
        if not api_key:
            raise RuntimeError("api_key obrigatório")
        # ... initialize SDK
        if model:
            self.model = model

    async def generate_structured(self, prompt: str, json_schema: dict) -> dict:
        # ... call API, parse JSON, raise LLMRateLimit/LLMTimeout/LLMError as appropriate
        ...
```

2. Add tests in `tests/test_llm_my_provider.py` mirroring `tests/test_llm_gemini.py`.
3. Add the SDK as an optional dep in `pyproject.toml`:

```toml
[project.optional-dependencies]
my-provider = ["my-sdk>=1.0"]
```

4. Document in `README.md` under "Providers".
5. Add CHANGELOG entry under `[Unreleased]`.

### Code style

- **Type-safe**: `mypy --strict` must pass on `src/engine`. Add type hints, never `Any` without justification.
- **Imports**: `from __future__ import annotations` at top. ruff/isort handle ordering.
- **Logging**: `structlog.get_logger(__name__)` — never stdlib `logging`. Pass kwargs (`log.info("event.name", key=value)`).
- **Errors**: subclass appropriate base error (`LLMError`, `RenderError`, `PresetInvalid`). Don't `raise Exception(...)`.
- **Async**: only at I/O boundaries (LLM calls). Pipeline stages are sync unless they consume an LLM.
- **Pydantic v2** for schemas. No dataclasses for things that need validation.

### Commit messages

[Conventional Commits](https://www.conventionalcommits.org/):

```
feat(extractor): add ODT support
fix(renderer): handle empty body in write_section
docs: clarify multi-tenant path validation
test(validator): cover edge case for nested sections
refactor(llm_mapper): extract prompt builder
```

Breaking changes go in body with `BREAKING CHANGE: ...`.

### Pull requests

- One concern per PR. Multiple concerns = multiple PRs.
- Link related issues.
- Pass CI: lint + types + tests on Python 3.11/3.12/3.13.
- Update `CHANGELOG.md` under `[Unreleased]`.
- Update docs (`README.md`, `docs/` if relevant).
- Don't bump version — maintainer does it on release.

## Reporting bugs

Open an issue with:

- Python version + OS
- template-engine version
- Minimal reproducing snippet
- Expected vs actual behavior

For security issues see [SECURITY.md](SECURITY.md) — **don't** use public issues.

## Questions / discussions

Use GitHub Discussions for design conversations. Issues are for bugs and concrete feature requests.

## License

By contributing, you agree your contribution is licensed under Apache 2.0 (matching the project).
