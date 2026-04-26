"""14 — POC: regex inference automatica (Wave A).

Antes: cada POC tinha _FIELD_PATTERNS hardcoded com regex escrito a mao.
Agora: passa 3 gold docs + exemplos dos campos, sintetiza regex automatico.

Run:
    python examples/14_pattern_inference.py
"""

from __future__ import annotations

from engine.pattern_inference import apply_inferred, infer_field_patterns

# 3 gold docs ficticios — mesma estrutura, valores diferentes.
GOLD_DOCS = [
    """LAUDO TECNICO - Q1
Codigo: LAUDO-2026-001
Revisao: 02
Data de emissao: 2026-01-15
Responsavel: Ana Carolina Souza
Classe operacional: A

Objetivo: avaliar conformidade do equipamento Alpha-1.
""",
    """LAUDO TECNICO - Q2
Codigo: LAUDO-2026-042
Revisao: 03
Data de emissao: 2026-04-26
Responsavel: Maria Jose Silva
Classe operacional: B

Objetivo: avaliar conformidade do equipamento Beta-2.
""",
    """LAUDO TECNICO - Q3
Codigo: LAUDO-2026-099
Revisao: 01
Data de emissao: 2026-07-30
Responsavel: Pedro Henrique Lima
Classe operacional: A

Objetivo: avaliar conformidade do equipamento Gamma-3.
""",
]

# Exemplos rotulados manualmente (1x — depois inferencia escala pra novos docs)
FIELD_EXAMPLES = {
    "CODIGO": ["LAUDO-2026-001", "LAUDO-2026-042", "LAUDO-2026-099"],
    "REVISAO": ["02", "03", "01"],
    "DATA": ["2026-01-15", "2026-04-26", "2026-07-30"],
    "RESPONSAVEL": ["Ana Carolina Souza", "Maria Jose Silva", "Pedro Henrique Lima"],
    "CLASSE": ["A", "B", "A"],
}


def main() -> None:
    print("=" * 80)
    print("WAVE A — REGEX INFERENCE (sintese automatica de patterns)")
    print("=" * 80)
    print()
    print(f"Gold docs: {len(GOLD_DOCS)}")
    print(f"Campos a inferir: {len(FIELD_EXAMPLES)}")
    print()

    # Inferencia
    inferred = infer_field_patterns(
        gold_docs=GOLD_DOCS,
        field_examples=FIELD_EXAMPLES,
    )

    print("=" * 80)
    print("PATTERNS INFERIDOS")
    print("=" * 80)
    print(f"{'campo':<14} | {'shape':<14} | {'cov':>5} | {'labels'}")
    print("-" * 80)
    for field, ip in inferred.items():
        labels = " / ".join(ip.label_variants[:3]) if ip.label_variants else "(none)"
        print(f"{field:<14} | {ip.value_shape_name:<14} | {ip.coverage:.2f} | {labels}")
    print()

    print("=" * 80)
    print("REGEX GERADO")
    print("=" * 80)
    for field, ip in inferred.items():
        print(f"{field:<14} -> {ip.regex.pattern}")
    print()

    # Teste em doc novo (nao visto na inferencia)
    new_doc = """LAUDO TECNICO - Q4 (doc novo, nunca visto)
Codigo: LAUDO-2026-150
Revisao: 04
Data de emissao: 2026-10-22
Responsavel: Lucia Fernanda Costa
Classe operacional: C

Outras informacoes irrelevantes...
"""

    print("=" * 80)
    print("APLICANDO PATTERNS INFERIDOS EM DOC NOVO")
    print("=" * 80)
    print(f"Doc input ({len(new_doc)} chars):")
    print(new_doc[:200] + "...")
    print()

    extracted = apply_inferred(inferred, new_doc)
    print("Extraidos:")
    for field in FIELD_EXAMPLES:
        v = extracted.get(field, "(NOT FOUND)")
        ok = "OK" if field in extracted else "MISS"
        print(f"  [{ok:<4}] {field:<14} -> {v}")

    print()
    print("=" * 80)
    print("VEREDITO")
    print("=" * 80)
    print(f"Campos extraidos: {len(extracted)}/{len(FIELD_EXAMPLES)}")
    print(f"Coverage media:   {sum(ip.coverage for ip in inferred.values()) / len(inferred):.2f}")
    print()
    print("Comparacao:")
    print("  ANTES: regex hardcoded em _FIELD_PATTERNS por POC (manual, 1x por campo)")
    print("  DEPOIS: regex inferido de exemplos (escalavel, novos docs sem retrabalho)")


if __name__ == "__main__":
    main()
