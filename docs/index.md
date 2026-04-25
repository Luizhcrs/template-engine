# template-engine

Document normalization engine: learn a pattern from example documents and convert any source document to that pattern automatically via LLM.

## Por quê

Padronizar documentos é trabalho repetitivo, propenso a erro, e geralmente feito copiando-colando trechos entre arquivos `.docx`. template-engine **aprende o padrão** a partir de 1-5 documentos-exemplo (gold docs) e **converte** qualquer documento-fonte pro mesmo padrão automaticamente.

## Princípio

**Renderer determinístico, conteúdo via LLM.** Regras de formatação vivem em YAML; conteúdo é extraído pelo modelo. Trocar de LLM (Gemini → GPT → Claude) não muda o resultado visual.

## Quem usa

- **SaaS B2B** que padronizam documentos internos (contratos, laudos, relatórios, propostas).
- **Migrações de legado** entre formatos corporativos (template antigo → novo).
- **Compliance** que exige consistência tipográfica + tokens críticos preservados.

## Comece

[Quickstart →](quickstart.md){: .md-button .md-button--primary }
[Conceitos →](concepts/pipeline.md){: .md-button }

## License

[Apache 2.0](https://github.com/Luizhcrs/template-engine/blob/main/LICENSE)
