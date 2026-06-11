"""Fase 3 — aplica as fontes alternativas `any_of` ao ground truth (GT v2).

Edita SOMENTE gt-0002 e gt-0005 no JSONL local:
- adiciona `group="g1"` à fonte primária existente;
- anexa uma fonte alternativa legítima (mesmo grupo), com `support_excerpt`
  literal extraído do corpus do Hub (cobertura garantida).

gt-0005: + REN 1059/2023 (mesmo tipo ren) — central geradora de fonte despachável.
gt-0002: + PRORET Submódulo 6.8 (cross-tipo procedimento) — Bandeiras Tarifárias.

As demais 48 linhas ficam byte-idênticas. Ao final valida o GT contra o corpus.

Uso: .venv/bin/python scripts/apply_gt_v2_anyof.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.evaluation.ground_truth import text_coverage, validate_ground_truth
from src.ingestion.uploader import carregar_corpus_hub

GT_PATH = Path("data/evaluation/ground_truth/aneel_retrieval_50.jsonl")

ALT_SOURCES = {
    "gt-0005": {
        "document_id": "ren-2023-1059",
        "titulo": (
            "Aprimora as regras para conexão e faturamento de micro e "
            "minigeração distribuída (REN 1.059/2023)"
        ),
        "citation_label": "REN 1059/2023 (central geradora de fonte despachável)",
        "section_label": "",
        "url": "https://www2.aneel.gov.br/cedoc/ren20231059.pdf",
        "relevance": 3,
        "group": "g1",
        # Literal do corpus (REN 1059, def. central geradora de fonte
        # despachável, alínea fotovoltaica). cov_answer=0.79, cov_corpus=1.00.
        "support_excerpt": (
            "fotovoltaica de até 3 MW de potência instalada, que apresentem "
            "capacidade de modulação de geração por meio de armazenamento de "
            "energia em baterias, em quantidade de, pelo menos, 20% da "
            "capacidade de geração mensal das unidades de geração "
            "fotovoltaicas, nos termos do art. 655-B;"
        ),
    },
    "gt-0002": {
        "document_id": (
            "proret-modulo06-subm6-8-proret-submod-6-8-v-1-9c-aren20221003"
        ),
        "titulo": "PRORET — Proret Submod 6.8 V 1.9C aren20221003",
        "citation_label": "PRORET Submódulo 6.8 (Bandeiras Tarifárias)",
        "section_label": "",
        "url": (
            "https://git.aneel.gov.br/publico/centralconteudo/-/blob/main/"
            "procreg/proret/modulo06/subm6.8/Proret_Submod_6.8_V_1.9C_"
            "aren20221003.pdf"
        ),
        "relevance": 3,
        "group": "g1",
        # fonte cross-tipo: declara tipo/subtipo próprios (any_of)
        "tipo": "procedimento",
        "subtipo": "proret",
        # Literal do corpus (PRORET 6.8, objetivo das Bandeiras Tarifárias).
        # cov_answer=0.77, cov_corpus=1.00.
        "support_excerpt": (
            "Bandeiras Tarifárias têm como finalidade: A. Sinalizar aos "
            "consumidores as condições de geração de energia elétrica no SIN, "
            "por meio da cobrança de valor adicional à Tarifa de Energia – TE; "
            "e B. Equalizar parcela de custos variáveis relativa à aquisição "
            "de energia elétrica"
        ),
    },
}


def main() -> None:
    corpus = carregar_corpus_hub()

    lines = GT_PATH.read_text(encoding="utf-8").splitlines()
    rows: list[dict] = []
    new_lines: list[str] = []
    for line in lines:
        if not line.strip():
            continue
        row = json.loads(line)
        qid = row["question_id"]
        if qid in ALT_SOURCES:
            row["relevant_sources"][0]["group"] = "g1"
            alt = dict(ALT_SOURCES[qid])
            row["relevant_sources"].append(alt)
            cov, _ = text_coverage(row["expected_answer"], alt["support_excerpt"])
            print(f"{qid}: +{alt['document_id']} (cov_answer={cov:.2f})")
            print(f"   excerpt: {alt['support_excerpt']}")
            new_lines.append(json.dumps(row, ensure_ascii=False))
        else:
            new_lines.append(line)  # 48 linhas inalteradas ficam verbatim
        rows.append(row)

    # valida ANTES de gravar
    summary = validate_ground_truth(rows, corpus_df=corpus, expected_count=50)
    print(f"\nValidação OK: {summary}")

    GT_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print(f"Gravado: {GT_PATH}")


if __name__ == "__main__":
    main()
