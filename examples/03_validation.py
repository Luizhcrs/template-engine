"""03 — Validar saída + medir confiança.

Mostra como rodar `validate` + `calculate_confidence` + `confidence_label`
pra decidir se uma saída do LLM tem qualidade suficiente pra publicar.
"""

from __future__ import annotations

from engine import (
    ConfidenceLabel,
    ValidationConfig,
    calculate_confidence,
    confidence_label,
    validate,
)


def main() -> None:
    config = ValidationConfig(
        critical_tokens=[
            {"name": "doc_code", "regex": r"DOC\.\d{3}"},
            {"name": "rev_year", "regex": r"\b20\d{2}\b"},
        ],
        required_sections=["objetivo", "procedimento", "responsaveis"],
        min_completeness=0.7,
    )

    source_text = "Documento DOC.001 versão 2026 descreve a normalização."
    llm_output = {
        "objetivo": "Padronizar revisão de DOC.001 conforme 2026.",
        "procedimento": "Aplicar template e revisar campos.",
        "responsaveis": "Equipe de qualidade.",
    }

    result = validate(source_text, llm_output, config)
    score = calculate_confidence(result, min_completeness=config.min_completeness)
    label = confidence_label(score)

    print(f"válido?           {result.ok}")
    print(f"tokens críticos:  {result.critical_tokens_found}/{result.critical_tokens_total}")
    print(f"seções:           {result.sections_present}/{result.sections_required}")
    print(f"score:            {score:.3f}")
    print(f"label:            {label.value}")

    if label == ConfidenceLabel.HIGH:
        print("\n→ confiança alta. Pode publicar direto.")
    elif label == ConfidenceLabel.MEDIUM:
        print("\n→ confiança média. Recomendado revisão humana.")
    else:
        print("\n→ confiança baixa. Refazer ou ajustar prompt.")


if __name__ == "__main__":
    main()
