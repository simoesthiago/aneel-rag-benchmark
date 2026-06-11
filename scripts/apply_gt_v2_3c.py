"""Fase 3c — correções pontuais do ground truth (GT v2).

Edita SOMENTE gt-0041 e gt-0013 no JSONL local:

- gt-0041 (`fix_excerpt`/answer 3→11 parcelas): o `expected_answer` listava
  só 3 parcelas do VMEuRB; o corpus (proc-rede-8-3-pr, item 1.2.1.1) lista
  11 — (a) a (k). O sistema já respondia as 11, mas levava correctness baixa
  contra um gabarito incompleto. Completa-se o `expected_answer` e o
  `support_excerpt` (literal do corpus).
- gt-0013 (`clarify_question`): a REN 1095/2024 padroniza DUAS coisas (o
  número de identificação da UC e o uso de CPF/CNPJ); a pergunta original era
  ambígua (auditor: "2 dimensões"). Reformula-se a pergunta para apontar,
  sem ambiguidade, à padronização do número de identificação da UC — que é a
  resposta documentada no GT. `expected_answer`/fonte ficam inalterados.

As demais 48 linhas ficam byte-idênticas. Valida o GT contra o corpus.

Uso: .venv/bin/python scripts/apply_gt_v2_3c.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.evaluation.ground_truth import text_coverage, validate_ground_truth
from src.ingestion.uploader import carregar_corpus_hub

GT_PATH = Path("data/evaluation/ground_truth/aneel_retrieval_50.jsonl")

GT0041_EXPECTED = (
    "Na apuração do VMEuRB são consideradas onze parcelas: (a) os EUST "
    "relativos à Rede Básica em função do MUST contratado e da TUSTRB; (b) os "
    "EUST de importação ou exportação de energia elétrica; (c) eventuais "
    "diferenças entre MUST verificado e MUST contratado; (d) o encargo da "
    "TUSDg-T; (e) o encargo da TUSDg-ONS; (f) o repasse de potência da Itaipu "
    "Binacional; (g) o ressarcimento por sobrecarga de transformadores; (h) a "
    "Parcela de Ineficiência por Ultrapassagem (PIU); (i) a Parcela de "
    "Ineficiência por Sobrecontratação (PIS); (j) a retificação de encargos "
    "de meses anteriores; e (k) o encargo de reserva da rede de transmissão "
    "por postergação do CUST."
)

GT0013_QUESTION = (
    "Qual padronização relativa ao número de identificação das unidades "
    "consumidoras e das demais instalações dos usuários foi estabelecida pela "
    "REN 1095/2024?"
)


def _gt0041_excerpt(corpus) -> str:
    sub = corpus[corpus["id"].astype(str) == "proc-rede-8-3-pr"]
    texto = ""
    for _, row in sub.iterrows():
        if str(row.get("metodo_extracao")) == "markdown":
            texto = str(row["texto_bruto"])
            break
    i = texto.lower().find("apuração do vmeurb são considerados")
    end = texto.find("1.2.1.1.1")
    raw = texto[i:end]
    limpo = re.sub(r"\s+", " ", raw.replace("**", "").replace("-", "")).strip()
    return limpo[:1300]


def main() -> None:
    corpus = carregar_corpus_hub()
    gt0041_excerpt = _gt0041_excerpt(corpus)

    lines = GT_PATH.read_text(encoding="utf-8").splitlines()
    rows: list[dict] = []
    new_lines: list[str] = []
    for line in lines:
        if not line.strip():
            continue
        row = json.loads(line)
        qid = row["question_id"]
        if qid == "gt-0041":
            row["expected_answer"] = GT0041_EXPECTED
            row["relevant_sources"][0]["support_excerpt"] = gt0041_excerpt
            cov, _ = text_coverage(GT0041_EXPECTED, gt0041_excerpt)
            print(f"gt-0041: expected_answer + excerpt (11 parcelas, cov={cov:.2f})")
            new_lines.append(json.dumps(row, ensure_ascii=False))
        elif qid == "gt-0013":
            row["question"] = GT0013_QUESTION
            print("gt-0013: pergunta reformulada (desambiguação)")
            new_lines.append(json.dumps(row, ensure_ascii=False))
        else:
            new_lines.append(line)  # 48 linhas inalteradas ficam verbatim
        rows.append(row)

    summary = validate_ground_truth(rows, corpus_df=corpus, expected_count=50)
    print(f"\nValidação OK: {summary}")

    GT_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print(f"Gravado: {GT_PATH}")


if __name__ == "__main__":
    main()
