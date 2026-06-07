"""1.3-alt — Query expansion contra gap de vocabulário (H6).

Para gt-0005, gt-0025 e gt-0027 (perguntas com gap formal-vs-informal
identificado em 1.2b/Fase B), testa 3 variantes:

1. ORIGINAL: query como está no GT.
2. GENERIC_EXPANSION: LLM reescreve em linguagem regulatória ANEEL
   SEM ver o documento esperado (variante realística para produção).
3. ORACLE_EXPANSION: LLM reescreve usando termos do documento esperado
   (DIAGNÓSTICO apenas — mostra o ceiling, não é proposta de produto).

Para cada (pergunta, variante), recupera top-100 na melhor config e
reporta:
- passage_recall@10 (matching atual threshold 0.60)
- doc_recall@10
- rank do primeiro chunk do doc esperado
- rank do primeiro chunk que passa matching
- se o "chunk perfeito" (cov 1.0 visto em 1.2b) entra no top-100
- comparação antes/depois

Não altera GT, threshold, chunker ou rerank. Não é decisão de produção
— apenas diagnóstico de H6.

Saída: data/evaluation/results/diagnostic/query_expansion_diagnostic.md

NOTA: usa `huggingface_hub.hf_hub_download`, que materializa em
~/.cache/huggingface/hub/. Exceção explícita à regra Hub-first do projeto
— vale apenas para diagnóstico pontual. Ver Troubleshooting no README.md.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402
from huggingface_hub import hf_hub_download  # noqa: E402

from src.config.settings import HF_DATASET_REPO, get_openai_api_key  # noqa: E402
from src.evaluation.ground_truth import (  # noqa: E402
    informative_tokens,
    load_ground_truth_hub,
)
from src.evaluation.matching import (  # noqa: E402
    SUPPORT_EXCERPT_TOKEN_THRESHOLD,
    section_signature_from_chunk,
    section_signature_from_label,
)
from src.evaluation.metrics import doc_recall_at_k  # noqa: E402
from src.rag.retriever import Retriever  # noqa: E402
from src.vectorstore.hub import hub_prefix  # noqa: E402
from src.vectorstore.metadata import METADATA_FILENAME  # noqa: E402

PERGUNTAS_FOCO = ["gt-0005", "gt-0025", "gt-0027"]
TOP_K_RETRIEVE = 100
TOP_K_EVAL = 10
REWRITER_MODEL = "gpt-4o-mini"

OUT_PATH = Path(
    "data/evaluation/results/diagnostic/query_expansion_diagnostic.md"
)

GENERIC_SYSTEM = """\
Você é especialista em linguagem regulatória da ANEEL (Agência Nacional de
Energia Elétrica do Brasil). Sua tarefa é reescrever uma pergunta em
linguagem técnica/regulatória formal típica das normas da ANEEL (RENs,
PRODIST, PRORET, Procedimentos de Rede), mantendo o significado original.

NÃO veja o documento esperado. Use apenas seu conhecimento sobre como a
ANEEL escreve suas normas (termos como "central geradora", "concessionária",
"submódulo", "metodologia regulatória", "taxa de remuneração de capital",
"WACC", "estrutura tarifária", "revisão tarifária periódica", etc).

Devolva APENAS a query reescrita, sem JSON, sem markdown, sem
explicação. Apenas o texto da pergunta.
"""

ORACLE_SYSTEM = """\
Você é especialista em linguagem regulatória da ANEEL. Você verá uma
pergunta e o trecho exato do documento que a responde. Reescreva a
pergunta usando os MESMOS termos técnicos do trecho-fonte, de modo a
maximizar a similaridade léxica entre query e documento.

Esta variante é apenas DIAGNÓSTICA — serve para medir o ceiling de
recuperação se a query fosse perfeitamente alinhada ao documento. Não
é proposta de produto.

Devolva APENAS a query reescrita, sem JSON, sem markdown, sem
explicação. Apenas o texto da pergunta.
"""


def parse_chunk_index(chunk_id: str) -> int:
    try:
        return int(chunk_id.rsplit("::", 1)[-1])
    except (ValueError, AttributeError):
        return -1


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


def call_rewriter(
    client, system: str, user: str, model: str = REWRITER_MODEL
) -> str:
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0,
    )
    return (resp.choices[0].message.content or "").strip()


def eval_variant(
    retriever: Retriever,
    query: str,
    source: dict,
    all_doc_chunks: list[dict],
    excerpt: str,
) -> dict:
    """Recupera top-100 e calcula as métricas pedidas."""
    chunks_top = retriever.retrieve(query, top_k=TOP_K_RETRIEVE)
    doc_id = str(source.get("document_id") or "")

    # Rank do primeiro chunk do doc esperado
    primeiro_chunk_doc_rank = None
    for rank, c in enumerate(chunks_top, start=1):
        if str(c.get("document_id") or "") == doc_id:
            primeiro_chunk_doc_rank = rank
            break

    # Rank do primeiro chunk que passa matching (threshold 0.60)
    primeiro_match_rank = None
    for rank, c in enumerate(chunks_top, start=1):
        if str(c.get("document_id") or "") != doc_id:
            continue
        if section_match(c, source):
            primeiro_match_rank = rank
            break
        cov = coverage_chunk(str(c.get("texto") or ""), excerpt)
        if cov >= SUPPORT_EXCERPT_TOKEN_THRESHOLD:
            primeiro_match_rank = rank
            break

    # passage_recall@10: usa source_coverage no top-10
    from src.evaluation.matching import source_coverage
    passage_recall = source_coverage(chunks_top[:TOP_K_EVAL], [source])
    docs_top10_recall = doc_recall_at_k(
        chunks_top[:TOP_K_EVAL], [doc_id], k=TOP_K_EVAL
    )

    # "Chunk perfeito" = chunk de cobertura máxima do doc no índice
    # (computado fora). Aqui só checa se está no top-100 retornado.
    best_overall_chunk = max(
        all_doc_chunks,
        key=lambda c: coverage_chunk(c["texto"], excerpt),
    )
    best_overall_id = best_overall_chunk["chunk_id"]
    best_overall_cov = coverage_chunk(best_overall_chunk["texto"], excerpt)
    chunk_perfeito_rank = None
    for rank, c in enumerate(chunks_top, start=1):
        if str(c.get("chunk_id") or "") == str(best_overall_id):
            chunk_perfeito_rank = rank
            break

    return {
        "passage_recall_at_10": round(passage_recall, 3),
        "doc_recall_at_10": round(docs_top10_recall, 3),
        "primeiro_chunk_doc_rank_top100": primeiro_chunk_doc_rank,
        "primeiro_match_rank_top100": primeiro_match_rank,
        "chunk_perfeito_id": best_overall_id,
        "chunk_perfeito_cov": round(best_overall_cov, 3),
        "chunk_perfeito_rank_no_top100": chunk_perfeito_rank,
    }


def main() -> None:
    print("Carregando ground truth ...", file=sys.stderr)
    todas = load_ground_truth_hub()
    foco = [q for q in todas if str(q.get("question_id")) in PERGUNTAS_FOCO]
    print(f"  {len(foco)} perguntas de foco.", file=sys.stderr)

    print("Carregando metadata.parquet (melhor config) ...", file=sys.stderr)
    prefix = hub_prefix(
        provider="openai",
        model="text-embedding-3-large",
        chunk_strategy="fixed-size",
        metodo_extracao="markdown",
    )
    local = hf_hub_download(
        repo_id=HF_DATASET_REPO,
        filename=f"{prefix}/{METADATA_FILENAME}",
        repo_type="dataset",
    )
    df_all = pd.read_parquet(local, engine="pyarrow")
    df_all["index"] = df_all["chunk_id"].apply(parse_chunk_index)

    retriever = Retriever(
        provider="openai",
        model="text-embedding-3-large",
        chunk_strategy="fixed-size",
        metodo_extracao="markdown",
        mode="flat",
    )

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai obrigatório") from exc
    client = OpenAI(api_key=get_openai_api_key())

    resultados: list[dict] = []
    for q in foco:
        qid = str(q.get("question_id"))
        pergunta = str(q.get("question") or "")
        sources = list(q.get("relevant_sources") or [])
        src = sources[0]
        doc_id = str(src.get("document_id") or "")
        excerpt = str(src.get("support_excerpt") or "")

        print(f"\n=== {qid} ===", file=sys.stderr)

        doc_chunks = df_all[df_all["document_id"] == doc_id].sort_values(
            "index"
        )
        all_doc_chunks = [
            {
                "index": int(row["index"]),
                "chunk_id": row["chunk_id"],
                "texto": str(row.get("texto") or ""),
            }
            for _, row in doc_chunks.iterrows()
        ]

        # Gerar variantes
        print("  Gerando generic_expansion ...", file=sys.stderr)
        generic_q = call_rewriter(
            client,
            system=GENERIC_SYSTEM,
            user=f"Pergunta original:\n{pergunta}",
        )
        print("  Gerando oracle_expansion ...", file=sys.stderr)
        oracle_q = call_rewriter(
            client,
            system=ORACLE_SYSTEM,
            user=(
                f"Pergunta original:\n{pergunta}\n\n"
                f"Trecho-fonte do documento (use estes termos):\n{excerpt}"
            ),
        )

        variantes = {
            "ORIGINAL": pergunta,
            "GENERIC_EXPANSION": generic_q,
            "ORACLE_EXPANSION": oracle_q,
        }

        eval_por_variante: dict[str, dict] = {}
        for nome, q_texto in variantes.items():
            print(f"  Avaliando {nome} ...", file=sys.stderr)
            eval_por_variante[nome] = eval_variant(
                retriever=retriever,
                query=q_texto,
                source=src,
                all_doc_chunks=all_doc_chunks,
                excerpt=excerpt,
            )
            eval_por_variante[nome]["query"] = q_texto

        resultados.append(
            {
                "question_id": qid,
                "pergunta_original": pergunta,
                "document_id": doc_id,
                "support_excerpt": excerpt,
                "variantes": eval_por_variante,
            }
        )

    # Renderização
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# 1.3-alt — Query expansion contra gap de vocabulário (H6)\n")
    lines.append(
        "Teste de 3 variantes de query (ORIGINAL, GENERIC_EXPANSION, "
        "ORACLE_EXPANSION) nas 3 perguntas com gap formal-vs-informal "
        "(gt-0005, gt-0025, gt-0027).\n"
    )
    lines.append(
        f"Config: text-embedding-3-large + fixed-size + markdown + flat. "
        f"Top-{TOP_K_RETRIEVE} recuperados; passage_recall e doc_recall "
        f"medidos em top-{TOP_K_EVAL}. Matching threshold inalterado "
        f"({SUPPORT_EXCERPT_TOKEN_THRESHOLD}).\n"
    )
    lines.append(
        "**Reescrita por:** " + REWRITER_MODEL + " (temperatura 0).\n"
    )
    lines.append(
        "**Importante:** ORACLE_EXPANSION usa termos do documento "
        "esperado — é DIAGNÓSTICO (ceiling), não proposta de produto. "
        "Apenas GENERIC_EXPANSION é realístico para produção.\n"
    )

    # Tabela-resumo
    lines.append("\n## Resumo agregado\n")
    lines.append(
        "| qid | variante | passage_recall@10 | doc_recall@10 | "
        "primeiro chunk doc | primeiro match | chunk perfeito (rank/cov) |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---|")
    for r in resultados:
        for nome in ("ORIGINAL", "GENERIC_EXPANSION", "ORACLE_EXPANSION"):
            ev = r["variantes"][nome]
            chunk_perfeito_str = (
                f"rank {ev['chunk_perfeito_rank_no_top100']} / "
                f"cov {ev['chunk_perfeito_cov']}"
                if ev["chunk_perfeito_rank_no_top100"] is not None
                else f"fora pool / cov {ev['chunk_perfeito_cov']}"
            )
            lines.append(
                f"| {r['question_id']} | {nome} "
                f"| {ev['passage_recall_at_10']} "
                f"| {ev['doc_recall_at_10']} "
                f"| {ev['primeiro_chunk_doc_rank_top100']} "
                f"| {ev['primeiro_match_rank_top100']} "
                f"| {chunk_perfeito_str} |"
            )

    # Detalhe por pergunta
    for r in resultados:
        lines.append(f"\n---\n\n## {r['question_id']}\n")
        lines.append(f"**Doc esperado:** `{r['document_id']}`\n")
        lines.append(f"**Support excerpt:** > {r['support_excerpt']}\n")
        for nome in ("ORIGINAL", "GENERIC_EXPANSION", "ORACLE_EXPANSION"):
            ev = r["variantes"][nome]
            lines.append(f"\n### {nome}\n")
            lines.append(f"**Query:** {ev['query']}\n")
            lines.append(
                f"- passage_recall@10 = **{ev['passage_recall_at_10']}**"
            )
            lines.append(
                f"- doc_recall@10 = **{ev['doc_recall_at_10']}**"
            )
            lines.append(
                f"- primeiro chunk do doc no top-100: rank "
                f"`{ev['primeiro_chunk_doc_rank_top100']}`"
            )
            lines.append(
                f"- primeiro chunk passando matching: rank "
                f"`{ev['primeiro_match_rank_top100']}`"
            )
            rank_perf = ev["chunk_perfeito_rank_no_top100"]
            if rank_perf is None:
                lines.append(
                    f"- chunk perfeito (cov {ev['chunk_perfeito_cov']}): "
                    f"**não entrou no top-{TOP_K_RETRIEVE}**"
                )
            else:
                lines.append(
                    f"- chunk perfeito (cov {ev['chunk_perfeito_cov']}): "
                    f"rank `{rank_perf}` no top-{TOP_K_RETRIEVE}"
                )

    # Comparação antes/depois
    lines.append("\n---\n\n## Comparação antes/depois\n")
    lines.append(
        "Sobe ↑ ou desce ↓ no chunk perfeito (rank) vs ORIGINAL:\n"
    )
    lines.append(
        "| qid | ORIGINAL rank | GENERIC rank | ORACLE rank |"
    )
    lines.append("|---|---|---|---|")
    for r in resultados:
        orig = r["variantes"]["ORIGINAL"]["chunk_perfeito_rank_no_top100"]
        gen = r["variantes"]["GENERIC_EXPANSION"]["chunk_perfeito_rank_no_top100"]
        ora = r["variantes"]["ORACLE_EXPANSION"]["chunk_perfeito_rank_no_top100"]

        def fmt(v):
            return f"{v}" if v is not None else "fora_pool"

        def setinha(a, b):
            if a is None and b is None:
                return ""
            if b is None:
                return " ↓"
            if a is None:
                return " ↑↑"
            if b < a:
                return f" ↑ ({a - b})"
            if b > a:
                return f" ↓ ({b - a})"
            return " ="

        lines.append(
            f"| {r['question_id']} | {fmt(orig)} "
            f"| {fmt(gen)}{setinha(orig, gen)} "
            f"| {fmt(ora)}{setinha(orig, ora)} |"
        )

    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Resumo terminal
    print()
    print("=== Resumo ===")
    for r in resultados:
        print(f"\n{r['question_id']}:")
        for nome in ("ORIGINAL", "GENERIC_EXPANSION", "ORACLE_EXPANSION"):
            ev = r["variantes"][nome]
            rank_perf = ev["chunk_perfeito_rank_no_top100"]
            print(
                f"  {nome:20s}: passage={ev['passage_recall_at_10']:.2f}, "
                f"doc={ev['doc_recall_at_10']:.2f}, "
                f"primeiro_chunk_doc={ev['primeiro_chunk_doc_rank_top100']}, "
                f"chunk_perfeito_rank={rank_perf}, "
                f"primeiro_match={ev['primeiro_match_rank_top100']}"
            )
    print(f"\nDetalhe completo: {OUT_PATH}")


if __name__ == "__main__":
    main()
