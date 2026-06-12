"""Fase F1.5 (Gate 2) — correções de GT que acompanham a higiene de versão.

Edita SOMENTE gt-0004 e gt-0002 no JSONL local; as demais 48 linhas ficam
byte-idênticas. Ao final valida o GT inteiro contra o corpus do Hub.

- **gt-0004 (norma relacionada, `any_of` legítimo):** a definição de
  "autoconsumo remoto" foi INTRODUZIDA na REN 1000 pela REN 1.059/2023 — o
  próprio texto da REN 1000 traz "(Incluído pela REN ANEEL 1.059…)". O sistema
  responde certo citando a REN 1059. Adiciona-se a REN 1059 como fonte
  alternativa (grupo g1) à REN 1000. Conteúdo idêntico nas duas → honesto.

- **gt-0002 (versão vigente sob higiene):** a fonte alternativa PRORET 6.8 era a
  v1.9c/2022, mas a vigente do submódulo 6.8 é a **v1.10c/2024**. Sob a higiene
  de versão a v1.9c é descartada do índice; o sistema passa a ver a v1.10c.
  Atualiza-se a fonte para a v1.10c (o excerpt de finalidade das bandeiras é
  literal nas duas versões). Mantém a REN 1000 como fonte primária do grupo g1.

Uso: .venv/bin/python scripts/apply_gt_version_fixes.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.evaluation.ground_truth import (
    GroundTruthValidationError,
    validate_ground_truth,
)
from src.ingestion.uploader import carregar_corpus_hub

GT_PATH = Path("data/evaluation/ground_truth/aneel_retrieval_50.jsonl")

# Fonte alternativa a ANEXAR em gt-0004 (REN 1059 introduziu a definição).
GT0004_ALT = {
    "document_id": "ren-2023-1059",
    "titulo": (
        "Aprimora as regras para conexão e faturamento de micro e "
        "minigeração distribuída (REN 1.059/2023)"
    ),
    "citation_label": "REN 1059/2023 (autoconsumo remoto)",
    "section_label": "",
    "url": "https://www2.aneel.gov.br/cedoc/ren20231059.pdf",
    "relevance": 3,
    "group": "g1",
    # Literal do corpus (REN 1059, inclusão do inciso I-A na REN 1000).
    "support_excerpt": (
        "autoconsumo remoto: modalidade de participação no SCEE caracterizada "
        "por: a) unidades consumidoras de titularidade de uma mesma pessoa "
        "física ou jurídica, incluídas matriz e filial; b) possuir unidade "
        "consumidora com microgeração ou minigeração distribuída em local "
        "diferente das unidades consumidoras que recebem excedentes de "
        "energia; e c) atendimento de todas as unidades consumidoras pela "
        "mesma distribuidora."
    ),
}

# Fonte 6.8 ATUALIZADA para a versão vigente (v1.10c/2024) em gt-0002.
GT0002_V110C = {
    "document_id": "proret-modulo06-subm6-8-proret-submod-6-8-v-1-10c-aren20241084",
    "titulo": "PRORET — Proret Submod 6.8 V 1.10C aren20241084",
    "citation_label": "PRORET Submódulo 6.8 (Bandeiras Tarifárias)",
    "section_label": "",
    "url": (
        "https://git.aneel.gov.br/publico/centralconteudo/-/blob/main/"
        "procreg/proret/modulo06/subm6.8/Proret_Submod_6.8_V_1.10C_"
        "aren20241084.pdf"
    ),
    "relevance": 3,
    "group": "g1",
    "tipo": "procedimento",
    "subtipo": "proret",
    # Excerpt literal — presente igual na v1.9c e na v1.10c.
    "support_excerpt": (
        "Bandeiras Tarifárias têm como finalidade: A. Sinalizar aos "
        "consumidores as condições de geração de energia elétrica no SIN, por "
        "meio da cobrança de valor adicional à Tarifa de Energia – TE; e B. "
        "Equalizar parcela de custos variáveis relativa à aquisição de energia "
        "elétrica"
    ),
}


def main() -> None:
    rows = [json.loads(line) for line in GT_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    por_id = {r["question_id"]: r for r in rows}

    # gt-0004 — adiciona group g1 na fonte primária + anexa a REN 1059.
    g4 = por_id["gt-0004"]
    prim4 = g4["relevant_sources"][0]
    assert prim4["document_id"] == "ren-2021-1000", prim4["document_id"]
    prim4["group"] = "g1"
    if not any(s["document_id"] == "ren-2023-1059" for s in g4["relevant_sources"]):
        g4["relevant_sources"].append(dict(GT0004_ALT))
        print("gt-0004: anexada fonte any_of REN 1059 (autoconsumo remoto)")
    else:
        print("gt-0004: REN 1059 já presente — nada a fazer")

    # gt-0002 — substitui a fonte 6.8 v1.9c pela vigente v1.10c.
    g2 = por_id["gt-0002"]
    novos = []
    trocou = False
    for s in g2["relevant_sources"]:
        if "subm6-8" in s["document_id"] and "v-1-9c" in s["document_id"]:
            novos.append(dict(GT0002_V110C))
            trocou = True
        else:
            novos.append(s)
    g2["relevant_sources"] = novos
    print(f"gt-0002: fonte 6.8 v1.9c -> v1.10c (trocou={trocou})")

    # Validação contra o corpus (URL ∈ corpus, cobertura de excerpt ≥ 0.70).
    print("\nValidando GT contra o corpus do Hub ...")
    corpus = carregar_corpus_hub()
    try:
        resumo = validate_ground_truth(rows, corpus_df=corpus)
    except GroundTruthValidationError as exc:
        print("❌ VALIDAÇÃO FALHOU:")
        print(str(exc))
        sys.exit(1)
    print(f"✅ GT válido: {resumo}")

    GT_PATH.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )
    print(f"Escrito {GT_PATH}")


if __name__ == "__main__":
    main()
