# template-engine

Engine proprietária de normalização documental: aprende padrão a partir de documentos-exemplo e converte qualquer documento-fonte pro padrão automaticamente.

**Status:** v0.1.0 — proprietário, todos os direitos reservados.

## O que faz

Pipeline de 5 etapas:

```
extractor → preset_creator → llm_mapper → validator → renderer
```

- **`extractor`** — `.docx`/`.pdf` → texto + tabelas + cabeçalhos
- **`preset_creator`** — template + 1-5 docs de referência → `pattern.md` + `schema.json` + `render_ops.yaml`
- **`llm_mapper`** — prompt + few-shot + JSON Schema → JSON estruturado
- **`validator`** — tokens críticos + cobertura + score 0-1
- **`renderer`** — template + JSON + render_ops → `.docx` final determinístico

## Uso

```python
from engine.extractor import extract
from engine.preset_creator import create_preset
from engine.llm.gemini_free import GeminiFreeProvider
from engine.llm_mapper import map_extracted_to_json
from engine.renderer import render_preset

provider = GeminiFreeProvider(api_key="AIza...")

doc = extract("source.docx")
preset = create_preset(template_path="template.docx", gold_paths=[...], llm=provider)
json_out = await map_extracted_to_json(doc, preset, provider)
render_preset(preset, json_out, output_path="out.docx")
```

## Arquitetura

**Stateless:** recebe paths/bytes, retorna paths/bytes/dicts. Sem dependência de FastAPI, SQLAlchemy ou qualquer framework de SaaS.

**Determinístico no rendering:** LLM nunca decide forma visual. Tudo que afeta visual vive em `render_ops.yaml`. Trocar de LLM não muda output visual.

## Desenvolvimento

```bash
pip install -e ".[dev]"
pytest
```

## Licença

Proprietário. Não distribuir, redistribuir, ou modificar sem autorização.
