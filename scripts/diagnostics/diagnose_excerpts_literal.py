"""A.2 - Validação literal do support_excerpt no documento original.

Para cada (question_id, source) do ground truth, verifica se o support_excerpt
aparece no texto bruto do documento esperado (texto_bruto da corpus). Roda
contra as DUAS extrações (markdown + texto) — se aparecer em pelo menos uma,
o GT é defensável; se não aparecer em nenhuma, é sinal de paráfrase ou erro.

Classificação por (question_id, source):
- LITERAL_MATCH: substring encontrada após normalização (lowercase + sem
  acento + pontuação reduzida). GT íntegro; problema está em chunking.
- TOKEN_MATCH:  substring não, mas ≥60% dos tokens informativos presentes.
  GT borderline (parafraseado mas semanticamente preservado).
- LOW_COVERAGE: 30-59% dos tokens. GT suspeito; sintese provável.
- NOT_FOUND:    <30% dos tokens. GT errado, ou doc errado, ou trecho não
  está mesmo no documento.

Hipóteses cobertas: H3 direta, parcialmente H5 (extração corrompida).
Saída: data/evaluation/results/diagnostic/excerpt_literal_audit.json

NOTA: usa `huggingface_hub.hf_hub_download`, que materializa em
~/.cache/huggingface/hub/. Exceção explícita à regra Hub-first do projeto
— vale apenas para diagnóstico pontual. Ver Troubleshooting no README.md.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402
from huggingface_hub import HfApi, hf_hub_download  # noqa: E402

from src.config.settings import HF_DATASET_REPO  # noqa: E402
from src.evaluation.ground_truth import (  # noqa: E402
    informative_tokens,
    load_ground_truth_hub,
    normalize_text,
)

LITERAL = "LITERAL_MATCH"
TOKEN = "TOKEN_MATCH"
LOW = "LOW_COVERAGE"
MISSING = "NOT_FOUND"

TOKEN_THRESHOLD_OK = 0.60
TOKEN_THRESHOLD_LOW = 0.30

OUT_PATH = Path(
    "data/evaluation/results/diagnostic/excerpt_literal_audit.json"
)


def load_corpus_texts() -> dict[tuple[str, str], str]:
    """Carrega corpus completo e devolve {(doc_id, metodo): texto_bruto}."""
    api = HfApi()
    arquivos = api.list_repo_files(HF_DATASET_REPO, repo_type="dataset")
    parquets = sorted(
        p
        for p in arquivos
        if p.startswith("data/documents/") and p.endswith(".parquet")
    )
    print(f"  {len(parquets)} parquets de corpus a baixar.", file=sys.stderr)

    textos: dict[tuple[str, str], str] = {}
    for path in parquets:
        # metodo_extracao é coluna de partição Hive-style — vem do path,
        # não do parquet (uploader stripa colunas de partição).
        match = re.search(r"metodo_extracao=([^/]+)/", path)
        if not match:
            print(f"  AVISO: path sem partição: {path}", file=sys.stderr)
            continue
        metodo = match.group(1)

        local = hf_hub_download(
            repo_id=HF_DATASET_REPO, filename=path, repo_type="dataset"
        )
        df = pd.read_parquet(local, engine="pyarrow")
        for _, row in df.iterrows():
            key = (str(row["id"]), metodo)
            textos[key] = str(row.get("texto_bruto") or "")
        print(
            f"    {path}: {len(df)} docs (acumulado {len(textos)})",
            file=sys.stderr,
        )
    return textos


def classify(
    excerpt: str, doc_text: str
) -> tuple[str, float, bool, int, int]:
    """Devolve (categoria, cobertura_tokens, achou_literal, hits, total)."""
    if not excerpt or not doc_text:
        return MISSING, 0.0, False, 0, 0

    excerpt_norm = normalize_text(excerpt)
    doc_norm = normalize_text(doc_text)
    literal = bool(excerpt_norm) and excerpt_norm in doc_norm

    tokens_excerpt = informative_tokens(excerpt)
    tokens_doc = set(informative_tokens(doc_text))
    if not tokens_excerpt:
        return MISSING, 0.0, literal, 0, 0
    hits = sum(1 for t in tokens_excerpt if t in tokens_doc)
    coverage = hits / len(tokens_excerpt)

    if literal:
        cat = LITERAL
    elif coverage >= TOKEN_THRESHOLD_OK:
        cat = TOKEN
    elif coverage >= TOKEN_THRESHOLD_LOW:
        cat = LOW
    else:
        cat = MISSING
    return cat, coverage, literal, hits, len(tokens_excerpt)


def main() -> None:
    print("Carregando ground truth ...", file=sys.stderr)
    questions = load_ground_truth_hub()
    print(f"  {len(questions)} perguntas.", file=sys.stderr)

    print("Carregando corpus do Hub ...", file=sys.stderr)
    textos = load_corpus_texts()
    print(f"  {len(textos)} (doc, metodo) carregados.", file=sys.stderr)

    audit: list[dict[str, object]] = []
    for q in questions:
        qid = q.get("question_id")
        for src in q.get("relevant_sources") or []:
            doc_id = str(src.get("document_id") or "")
            excerpt = str(src.get("support_excerpt") or "")
            section = str(src.get("section_label") or "")

            por_metodo: dict[str, dict[str, object]] = {}
            for metodo in ("markdown", "texto"):
                doc_text = textos.get((doc_id, metodo), "")
                cat, cov, lit, hits, total = classify(excerpt, doc_text)
                por_metodo[metodo] = {
                    "categoria": cat,
                    "cobertura_tokens": round(cov, 3),
                    "literal_match": lit,
                    "hits": hits,
                    "tokens_total": total,
                    "doc_existe_no_corpus": (doc_id, metodo) in textos,
                }

            # Melhor categoria entre os dois métodos (ranking LITERAL > TOKEN
            # > LOW > NOT_FOUND).
            ordem = {LITERAL: 3, TOKEN: 2, LOW: 1, MISSING: 0}
            melhor = max(
                (por_metodo[m]["categoria"] for m in ("markdown", "texto")),
                key=lambda c: ordem[c],
            )

            audit.append(
                {
                    "question_id": qid,
                    "answerability": q.get("answerability"),
                    "document_id": doc_id,
                    "section_label": section,
                    "support_excerpt_preview": excerpt[:200],
                    "support_excerpt_len_chars": len(excerpt),
                    "categoria_consolidada": melhor,
                    "por_metodo": por_metodo,
                }
            )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(
            {
                "n_questions": len(questions),
                "n_source_records": len(audit),
                "categorias": dict(
                    Counter(r["categoria_consolidada"] for r in audit)
                ),
                "items": audit,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # Resumo no terminal
    cat_counts = Counter(r["categoria_consolidada"] for r in audit)
    total = sum(cat_counts.values())
    print()
    print("=== Resumo: distribuição das fontes do GT ===")
    for cat in (LITERAL, TOKEN, LOW, MISSING):
        n = cat_counts.get(cat, 0)
        pct = n / total * 100 if total else 0
        print(f"  {cat:14s}: {n:3d} ({pct:5.1f}%)")

    # Foco: 11 falhas conhecidas + revisão
    focos = {
        "gt-0002",
        "gt-0005",
        "gt-0007",
        "gt-0012",
        "gt-0017",
        "gt-0025",
        "gt-0026",
        "gt-0027",
        "gt-0029",
        "gt-0030",
        "gt-0034",
    }
    print()
    print("=== Foco nas 11 falhas residuais ===")
    print(
        f"{'qid':10s}  {'doc_id':30s}  {'categoria':14s}  "
        f"{'cob_md':>7s}  {'cob_tx':>7s}"
    )
    for r in audit:
        if r["question_id"] not in focos:
            continue
        md = r["por_metodo"]["markdown"]
        tx = r["por_metodo"]["texto"]
        print(
            f"{r['question_id']:10s}  {r['document_id'][:30]:30s}  "
            f"{r['categoria_consolidada']:14s}  "
            f"{md['cobertura_tokens']:>7.3f}  {tx['cobertura_tokens']:>7.3f}"
        )

    print(f"\nDetalhe completo salvo em: {OUT_PATH}")


if __name__ == "__main__":
    main()
