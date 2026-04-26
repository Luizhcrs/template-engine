# Contribuindo

Obrigado por considerar contribuir.

O guia completo do contribuidor vive em [`CONTRIBUTING.md`](https://github.com/Luizhcrs/template-engine/blob/main/CONTRIBUTING.md) na raiz do repo. Resumo:

- **Setup**: `pip install -e ".[dev]"` depois `pre-commit install`
- **Tests**: `pytest` (36 tests hoje)
- **Lint + types + format**: `ruff check . && ruff format --check . && mypy src/engine`
- **Conventional Commits**: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`
- **Uma preocupação por PR**

## Checklist pra adicionar provider

1. Implemente `engine.llm.<nome>_provider.py` casando o Protocol `LLMProvider`
2. Adicione testes unitários em `tests/test_llm_<nome>.py` espelhando `tests/test_llm_gemini.py`
3. Adicione SDK como dep opcional em `pyproject.toml`: `[project.optional-dependencies] <nome> = ["sdk>=x"]`
4. Documente em `docs/providers/index.md` (ambos EN + `.pt.md`)
5. Adicione entrada no CHANGELOG sob `[Unreleased]`

## Reportando bugs

Issue no GitHub com: versão Python, OS, versão template-engine, repro mínimo, expected vs actual.

Pra issues de segurança veja [`SECURITY.md`](https://github.com/Luizhcrs/template-engine/blob/main/SECURITY.md).
