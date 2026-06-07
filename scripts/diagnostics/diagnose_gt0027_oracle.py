"""A — Reteste de gt-0027 com oracle real.

Em 1.3-alt a oracle_expansion (LLM-rewriter) não usou os termos
discriminantes do excerpt. Aqui, monta query "oracle real" manualmente
com os termos exigidos pelo usuário:

- taxa regulatória de remuneração de capital
- estrutura de capital regulatória
- custo de capital
- PRORET Submódulo 2.4
- revisão tarifária periódica
- concessionárias de distribuição

Roda nas mesmas 6 configs do 1.3-alt-b. Sem rerank, sem mexer em
threshold/chunker/GT/vectorstore.

Saída: data/evaluation/results/diagnostic/gt0027_oracle_retest.md

NOTA: usa `huggingface_hub.hf_hub_download` (incluindo monkey-patch em
`src.vectorstore.hub._read_hub_file_bytes` para contornar instabilidade do
Xet bridge). Materializa cache local em ~/.cache/huggingface/hub/. Exceção
explícita à regra Hub-first do projeto — vale apenas para diagnóstico
pontual. Ver Troubleshooting no README.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from huggingface_hub import hf_hub_download  # noqa: E402
import src.vectorstore.hub as _hub  # noqa: E402


def _patched_read_hub_file_bytes(repo_id: str, path: str) -> bytes:
    import time

    last_exc = None
    for tentativa in range(6):
        try:
            local = hf_hub_download(
                repo_id=repo_id, filename=path, repo_type="dataset"
            )
            return Path(local).read_bytes()
        except Exception as exc:
            last_exc = exc
            wait = 5 * (tentativa + 1)
            print(
                f"  [retry {tentativa + 1}/6] {type(exc).__name__}; "
                f"wait {wait}s",
                file=sys.stderr,
            )
            time.sleep(wait)
    raise last_exc if last_exc else RuntimeError("download falhou")


_hub._read_hub_file_bytes = _patched_read_hub_file_bytes

from src.embeddings.cache import QueryEmbeddingCache  # noqa: E402
from src.evaluation.ground_truth import (  # noqa: E402
    informative_tokens,
    load_ground_truth_hub,
)
from src.evaluation.matching import (  # noqa: E402
    SUPPORT_EXCERPT_TOKEN_THRESHOLD,
    section_signature_from_chunk,
    section_signature_from_label,
    source_coverage,
)
from src.evaluation.metrics import doc_recall_at_k  # noqa: E402
from src.rag.retriever import Retriever  # noqa: E402

QID = "gt-0027"

# Query original do GT (referência)
QUERY_ORIGINAL = (
    "Qual é a finalidade metodológica do PRORET Submódulo 2.4 na revisão "
    "tarifária de distribuidoras?"
)

# Oracle real construído com os termos discriminantes pedidos pelo usuário
QUERY_ORACLE_REAL = (
    "No PRORET Submódulo 2.4, qual é a metodologia para definição da "
    "taxa regulatória de remuneração de capital e da estrutura de "
    "capital regulatória no processo de revisão tarifária periódica das "
    "concessionárias de distribuição? Trate de custo de capital."
)

CONFIGS: list[tuple[str, str, str, str, str]] = [
    ("text-embedding-3-large", "fixed-size", "markdown", "flat", "fixed/md/flat"),
    ("text-embedding-3-large", "fixed-size", "texto", "flat", "fixed/tx/flat"),
    ("text-embedding-3-large", "article-aware", "texto", "flat", "article/tx/flat"),
    ("text-embedding-3-large", "hierarchical-child", "texto", "hierarchical", "hier/tx/hier"),
    ("text-embedding-3-large", "article-aware", "markdown", "flat", "article/md/flat"),
    ("text-embedding-3-large", "hierarchical-child", "markdown", "hierarchical", "hier/md/hier"),
]

TOP_K_RETRIEVE = 100
TOP_K_EVAL = 10

OUT_PATH = Path(
    "data/evaluation/results/diagnostic/gt0027_oracle_retest.md"
)


def section_match(chunk: dict, source: dict) -> bool:
    chunk_sig = section_signature_from_chunk(chunk)
    source_sig = section_signature_from_label(
        str(source.get("section_label") or "")
    )
    if not source_sig or not chunk_sig:
        return False
    if chunk_sig == source_sig:
        return True
    return source_sig.startswith(chunk_sig + ".") or chunk_sig.startswith(
        source_sig + "."
    )


def coverage_chunk(chunk_text: str, excerpt: str) -> float:
    excerpt_tokens = informative_tokens(excerpt)
    if not excerpt_tokens:
        return 0.0
    chunk_tokens = set(informative_tokens(chunk_text))
    hits = sum(1 for t in excerpt_tokens if t in chunk_tokens)
    return hits / len(excerpt_tokens)


def evaluate(retriever: Retriever, query: str, source: dict) -> dict:
    chunks_top = retriever.retrieve(query, top_k=TOP_K_RETRIEVE)
    doc_id = str(source.get("document_id") or "")
    excerpt = str(source.get("support_excerpt") or "")

    primeiro_chunk_doc_rank = None
    for rank, c in enumerate(chunks_top, start=1):
        if str(c.get("document_id") or "") == doc_id:
            primeiro_chunk_doc_rank = rank
            break

    primeiro_match_rank = None
    for rank, c in enumerate(chunks_top, start=1):
        if str(c.get("document_id") or "") != doc_id:
            continue
        if section_match(c, source):
            primeiro_match_rank = rank
            break
        if (
            coverage_chunk(str(c.get("texto") or ""), excerpt)
            >= SUPPORT_EXCERPT_TOKEN_THRESHOLD
        ):
            primeiro_match_rank = rank
            break

    best_cov = 0.0
    best_cov_rank = None
    for rank, c in enumerate(chunks_top, start=1):
        if str(c.get("document_id") or "") != doc_id:
            continue
        cov = coverage_chunk(str(c.get("texto") or ""), excerpt)
        if cov > best_cov:
            best_cov = cov
            best_cov_rank = rank

    return {
        "passage_recall_at_10": round(
            source_coverage(chunks_top[:TOP_K_EVAL], [source]), 3
        ),
        "doc_recall_at_10": round(
            doc_recall_at_k(chunks_top[:TOP_K_EVAL], [doc_id], k=TOP_K_EVAL),
            3,
        ),
        "primeiro_chunk_doc_rank": primeiro_chunk_doc_rank,
        "primeiro_match_rank": primeiro_match_rank,
        "best_cov_rank": best_cov_rank,
        "best_cov": round(best_cov, 3),
    }


def main() -> None:
    print("Carregando ground truth ...", file=sys.stderr)
    todas = load_ground_truth_hub()
    q_obj = next(q for q in todas if str(q.get("question_id")) == QID)
    src = list(q_obj.get("relevant_sources") or [])[0]

    cache = QueryEmbeddingCache()
    retrievers: dict[str, Retriever] = {}

    variantes = {
        "ORIGINAL": QUERY_ORIGINAL,
        "ORACLE_REAL": QUERY_ORACLE_REAL,
    }

    resultados: dict[str, dict[str, dict]] = {nome: {} for nome in variantes}

    for cfg in CONFIGS:
        model, strategy, metodo, mode, label = cfg
        key = f"{model}|{strategy}|{metodo}|{mode}"
        print(f"\n=== Config: {label} ===", file=sys.stderr)
        if key not in retrievers:
            retrievers[key] = Retriever(
                provider="openai",
                model=model,
                chunk_strategy=strategy,
                metodo_extracao=metodo,
                mode=mode,
                query_cache=cache,
            )
        retriever = retrievers[key]

        for nome, query in variantes.items():
            print(f"  {nome} ...", file=sys.stderr)
            resultados[nome][label] = evaluate(retriever, query, src)

    # Render
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append(f"# gt-0027 — reteste com oracle real\n")
    lines.append(
        "Em 1.3-alt, a oracle_expansion automática (LLM) não usou os "
        "termos discriminantes. Aqui, query oracle construída manualmente "
        "com os termos exigidos.\n"
    )
    lines.append(f"**Pergunta original:**\n> {QUERY_ORIGINAL}\n")
    lines.append(f"**Oracle real (manual):**\n> {QUERY_ORACLE_REAL}\n")
    lines.append(
        f"**Doc esperado:** `{src.get('document_id')}`\n"
        f"**Support excerpt:** > {src.get('support_excerpt')}\n"
    )

    for nome in ("ORIGINAL", "ORACLE_REAL"):
        lines.append(f"\n## {nome}\n")
        lines.append(
            "| config | passage_recall@10 | doc_recall@10 | "
            "chunk_doc rank | match rank | best_cov rank | best_cov |"
        )
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for cfg in CONFIGS:
            label = cfg[4]
            r = resultados[nome][label]
            lines.append(
                f"| {label} "
                f"| {r['passage_recall_at_10']} "
                f"| {r['doc_recall_at_10']} "
                f"| {r['primeiro_chunk_doc_rank']} "
                f"| {r['primeiro_match_rank']} "
                f"| {r['best_cov_rank']} "
                f"| {r['best_cov']} |"
            )

    # Delta
    lines.append("\n## Delta ORACLE_REAL vs ORIGINAL\n")
    lines.append(
        "| config | passage Δ | best_cov Δ | "
        "chunk_doc rank (orig → oracle) |"
    )
    lines.append("|---|---:|---:|---|")
    for cfg in CONFIGS:
        label = cfg[4]
        o = resultados["ORIGINAL"][label]
        x = resultados["ORACLE_REAL"][label]
        d_pass = x["passage_recall_at_10"] - o["passage_recall_at_10"]
        d_cov = x["best_cov"] - o["best_cov"]
        rank_str = (
            f"{o['primeiro_chunk_doc_rank']} → "
            f"{x['primeiro_chunk_doc_rank']}"
        )
        sinal_p = "+" if d_pass >= 0 else ""
        sinal_c = "+" if d_cov >= 0 else ""
        lines.append(
            f"| {label} | {sinal_p}{d_pass:.2f} | {sinal_c}{d_cov:.2f} "
            f"| {rank_str} |"
        )

    # Veredito
    lines.append("\n## Veredito\n")
    # Quantas configs passam com oracle real?
    oracle_passes = sum(
        1
        for cfg in CONFIGS
        if resultados["ORACLE_REAL"][cfg[4]]["passage_recall_at_10"] > 0
    )
    orig_passes = sum(
        1
        for cfg in CONFIGS
        if resultados["ORIGINAL"][cfg[4]]["passage_recall_at_10"] > 0
    )
    lines.append(
        f"- Configs em que ORIGINAL passa (passage_recall > 0): "
        f"{orig_passes}/{len(CONFIGS)}"
    )
    lines.append(
        f"- Configs em que ORACLE_REAL passa: {oracle_passes}/{len(CONFIGS)}"
    )
    if oracle_passes > orig_passes:
        lines.append(
            "\n→ **H6 (vocabulário) CONFIRMADA** para gt-0027: "
            "vocabulário discriminante muda o resultado. Fixável por "
            "query expansion realística (não-oracle) só se LLM-rewriter "
            "souber inferir os termos sem ver o documento."
        )
    else:
        lines.append(
            "\n→ **gt-0027 NÃO se resolve por oracle real** em nenhuma "
            "config. Causa diferente de H6 puro — pode ser concept-dense, "
            "extração corrompida ou outro fator estrutural."
        )

    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print()
    print("=== Resumo passage_recall@10 ===")
    print(
        f"{'config':25s}  {'ORIGINAL':>10s}  {'ORACLE_REAL':>12s}"
    )
    for cfg in CONFIGS:
        label = cfg[4]
        o = resultados["ORIGINAL"][label]["passage_recall_at_10"]
        x = resultados["ORACLE_REAL"][label]["passage_recall_at_10"]
        print(f"{label:25s}  {o:>10.2f}  {x:>12.2f}")
    print()
    print("=== Resumo best_cov no top-100 ===")
    print(
        f"{'config':25s}  {'ORIGINAL':>10s}  {'ORACLE_REAL':>12s}"
    )
    for cfg in CONFIGS:
        label = cfg[4]
        o = resultados["ORIGINAL"][label]["best_cov"]
        x = resultados["ORACLE_REAL"][label]["best_cov"]
        print(f"{label:25s}  {o:>10.2f}  {x:>12.2f}")

    print(f"\nCache: {cache.stats}")
    print(f"\nSaída: {OUT_PATH}")


if __name__ == "__main__":
    main()
