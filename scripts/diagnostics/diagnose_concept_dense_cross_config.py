"""1.3-alt-b — Concept-dense é específico de fixed-size+markdown?

Testa se as 3 perguntas com Achado 7 (gt-0005, gt-0025, gt-0027) ainda
falham nas 6 configs já publicadas. Sem rerank, sem query expansion,
sem rebuild — apenas usa retriever atual.

Configs:
1. large + fixed-size + markdown + flat   (baseline atual)
2. large + fixed-size + texto + flat
3. large + article-aware + texto + flat
4. large + hierarchical-child + texto + hierarchical
5. large + article-aware + markdown + flat
6. large + hierarchical-child + markdown + hierarchical

Para cada (pergunta, config), reporta:
- passage_recall@10
- doc_recall@10
- rank do primeiro chunk do doc esperado no top-100
- rank do primeiro chunk que passa matching no top-100
- rank do melhor chunk por cobertura no top-100
- melhor cobertura no top-100

Caveat gt-0027 (registrado no output): a oracle_expansion de 1.3-alt
NÃO incluiu termos discriminantes do excerpt ("taxa regulatória de
remuneração de capital", "estrutura de capital regulatória"). Portanto,
conclusões sobre gt-0027 ser concept-dense ainda dependem de teste com
oracle de verdade.

Saída: data/evaluation/results/diagnostic/concept_dense_cross_config.md

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

# Workaround: DNS do cas-bridge.xethub.hf.co falha intermitentemente.
# `_read_hub_file_bytes` em src/vectorstore/hub.py usa requests.get direto,
# que segue o redirect e quebra no Xet. `hf_hub_download` da huggingface_hub
# tem cliente Xet integrado e funciona. Patcheamos só nesta execução.
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
                f"  [download retry {tentativa + 1}/6] falhou: "
                f"{type(exc).__name__}; aguardando {wait}s",
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

PERGUNTAS_FOCO = ["gt-0005", "gt-0025", "gt-0027"]

# (model, chunk_strategy, metodo_extracao, mode, label_curto)
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
    "data/evaluation/results/diagnostic/concept_dense_cross_config.md"
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


def evaluate(
    retriever: Retriever,
    pergunta: str,
    source: dict,
) -> dict:
    chunks_top = retriever.retrieve(pergunta, top_k=TOP_K_RETRIEVE)
    doc_id = str(source.get("document_id") or "")
    excerpt = str(source.get("support_excerpt") or "")

    # primeiro chunk do doc esperado
    primeiro_chunk_doc_rank = None
    for rank, c in enumerate(chunks_top, start=1):
        if str(c.get("document_id") or "") == doc_id:
            primeiro_chunk_doc_rank = rank
            break

    # primeiro chunk que passa matching
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

    # melhor chunk por cobertura no top-100 (entre chunks do doc esperado)
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
        "best_cov_rank_top100": best_cov_rank,
        "best_cov_top100": round(best_cov, 3),
    }


def main() -> None:
    print("Carregando ground truth ...", file=sys.stderr)
    todas = load_ground_truth_hub()
    foco = [q for q in todas if str(q.get("question_id")) in PERGUNTAS_FOCO]
    print(f"  {len(foco)} perguntas de foco.", file=sys.stderr)

    cache = QueryEmbeddingCache()

    # Cache de retrievers por config
    retrievers: dict[str, Retriever] = {}

    resultados: list[dict] = []
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

        for q in foco:
            qid = str(q.get("question_id"))
            pergunta = str(q.get("question") or "")
            src = list(q.get("relevant_sources") or [])[0]
            print(f"  {qid} ...", file=sys.stderr)
            ev = evaluate(retriever, pergunta, src)
            ev.update(
                {
                    "question_id": qid,
                    "config_label": label,
                    "chunk_strategy": strategy,
                    "metodo_extracao": metodo,
                    "mode": mode,
                }
            )
            resultados.append(ev)

    # Render markdown
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append(
        "# 1.3-alt-b — Concept-dense persiste em outras configs?\n"
    )
    lines.append(
        "Teste das 3 perguntas com Achado 7 (gt-0005, gt-0025, gt-0027) "
        "em 6 configs Dense+Hierarchical já publicadas. Sem rerank, "
        "sem query expansion.\n"
    )
    lines.append(
        f"Top-{TOP_K_RETRIEVE} recuperados; passage/doc recall medidos "
        f"em top-{TOP_K_EVAL}. Matching threshold = "
        f"{SUPPORT_EXCERPT_TOKEN_THRESHOLD}.\n"
    )

    lines.append("\n## Caveat sobre gt-0027\n")
    lines.append(
        "A oracle_expansion de 1.3-alt para gt-0027 NÃO incluiu os "
        "termos discriminantes do excerpt (`taxa regulatória de "
        "remuneração de capital`, `estrutura de capital regulatória`). "
        "Portanto, a classificação de gt-0027 como concept-dense ainda "
        "depende de teste com oracle de verdade. Este teste cross-config "
        "ajuda mas não fecha a questão para gt-0027.\n"
    )

    # Por pergunta
    for qid in PERGUNTAS_FOCO:
        lines.append(f"\n---\n\n## {qid}\n")
        items = [r for r in resultados if r["question_id"] == qid]
        if not items:
            continue
        # Detalhe da pergunta (de qualquer item — todos têm a mesma)
        q_obj = next(q for q in foco if str(q.get("question_id")) == qid)
        src0 = list(q_obj.get("relevant_sources") or [])[0]
        lines.append(f"**Pergunta:** {q_obj.get('question')}")
        lines.append(f"**Doc esperado:** `{src0.get('document_id')}`")
        lines.append(f"**Support excerpt:** > {src0.get('support_excerpt')}\n")

        lines.append(
            "| config | passage_recall@10 | doc_recall@10 | "
            "chunk_doc rank | match rank | best cov rank | best cov |"
        )
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for r in items:
            lines.append(
                f"| {r['config_label']} "
                f"| {r['passage_recall_at_10']} "
                f"| {r['doc_recall_at_10']} "
                f"| {r['primeiro_chunk_doc_rank']} "
                f"| {r['primeiro_match_rank']} "
                f"| {r['best_cov_rank_top100']} "
                f"| {r['best_cov_top100']} |"
            )

    # Visão por config (matriz)
    lines.append("\n---\n\n## Visão cruzada — passage_recall@10\n")
    lines.append(
        "| config | " + " | ".join(PERGUNTAS_FOCO) + " |"
    )
    lines.append("|---|" + "---:|" * len(PERGUNTAS_FOCO))
    for cfg in CONFIGS:
        label = cfg[4]
        row = [label]
        for qid in PERGUNTAS_FOCO:
            r = next(
                (
                    x
                    for x in resultados
                    if x["question_id"] == qid and x["config_label"] == label
                ),
                None,
            )
            row.append(f"{r['passage_recall_at_10']}" if r else "—")
        lines.append("| " + " | ".join(row) + " |")

    lines.append("\n## Visão cruzada — best cov no top-100\n")
    lines.append(
        "| config | " + " | ".join(PERGUNTAS_FOCO) + " |"
    )
    lines.append("|---|" + "---:|" * len(PERGUNTAS_FOCO))
    for cfg in CONFIGS:
        label = cfg[4]
        row = [label]
        for qid in PERGUNTAS_FOCO:
            r = next(
                (
                    x
                    for x in resultados
                    if x["question_id"] == qid and x["config_label"] == label
                ),
                None,
            )
            row.append(f"{r['best_cov_top100']}" if r else "—")
        lines.append("| " + " | ".join(row) + " |")

    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Resumo terminal
    print()
    print("=== Resumo passage_recall@10 ===")
    print(
        f"{'config':25s}  " + "  ".join(f"{q:>10s}" for q in PERGUNTAS_FOCO)
    )
    for cfg in CONFIGS:
        label = cfg[4]
        row = []
        for qid in PERGUNTAS_FOCO:
            r = next(
                (
                    x
                    for x in resultados
                    if x["question_id"] == qid and x["config_label"] == label
                ),
                None,
            )
            row.append(f"{r['passage_recall_at_10']:>10.2f}" if r else "         —")
        print(f"{label:25s}  " + "  ".join(row))

    print()
    print("=== Resumo best_cov no top-100 ===")
    print(
        f"{'config':25s}  " + "  ".join(f"{q:>10s}" for q in PERGUNTAS_FOCO)
    )
    for cfg in CONFIGS:
        label = cfg[4]
        row = []
        for qid in PERGUNTAS_FOCO:
            r = next(
                (
                    x
                    for x in resultados
                    if x["question_id"] == qid and x["config_label"] == label
                ),
                None,
            )
            row.append(f"{r['best_cov_top100']:>10.2f}" if r else "         —")
        print(f"{label:25s}  " + "  ".join(row))

    print(f"\nCache: {cache.stats}")
    print(f"\nSaída salva em: {OUT_PATH}")


if __name__ == "__main__":
    main()
