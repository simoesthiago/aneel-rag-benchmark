"""1.2b — Diagnóstico rigoroso do balde 2 após refutação de H8.

Foco: gt-0005, gt-0017, gt-0025, gt-0034. Para cada pergunta, gera:

1. rank do primeiro chunk do documento esperado no top-100;
2. rank do primeiro chunk que passa no matching atual (threshold 0.60);
3. melhor cobertura de support_excerpt entre TODOS os chunks do doc
   (não só os recuperados — lê metadata.parquet completo);
4. se support_excerpt aparece inteiro em chunk único, partido entre
   adjacentes, ou não aparece;
5. veredito LLM (gpt-4o-mini) sobre o melhor chunk recuperado.

Classifica em 6 categorias predefinidas. Não altera threshold, chunker
ou rerank.

Saída: data/evaluation/results/diagnostic/bucket2_diagnostic.md

NOTA: usa `huggingface_hub.hf_hub_download`, que materializa em
~/.cache/huggingface/hub/. Exceção explícita à regra Hub-first do projeto
— vale apenas para diagnóstico pontual. Ver Troubleshooting no README.md.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402
from huggingface_hub import hf_hub_download  # noqa: E402

from src.config.settings import HF_DATASET_REPO, get_openai_api_key  # noqa: E402
from src.evaluation.ground_truth import (  # noqa: E402
    informative_tokens,
    load_ground_truth_hub,
    normalize_text,
)
from src.evaluation.matching import (  # noqa: E402
    SUPPORT_EXCERPT_TOKEN_THRESHOLD,
    section_signature_from_chunk,
    section_signature_from_label,
)
from src.rag.retriever import Retriever  # noqa: E402
from src.vectorstore.hub import hub_prefix  # noqa: E402
from src.vectorstore.metadata import METADATA_FILENAME  # noqa: E402

PERGUNTAS_FOCO = ["gt-0005", "gt-0017", "gt-0025", "gt-0034"]
TOP_K_RETRIEVE = 100
JUDGE_MODEL = "gpt-4o-mini"

OUT_PATH = Path(
    "data/evaluation/results/diagnostic/bucket2_diagnostic.md"
)

JUDGE_SYSTEM = """\
Você é um avaliador especialista em direito regulatório brasileiro (ANEEL).
Decida se o chunk recuperado sustenta a resposta à pergunta, dado o trecho
esperado pelo gabarito.

- SIM: chunk contém a mesma informação essencial do support_excerpt.
- NAO: chunk apenas compartilha vocabulário; informação central ausente.
- PARCIAL: chunk traz parte da informação, insuficiente para responder.

Responda APENAS em JSON: {"veredito":"SIM"|"NAO"|"PARCIAL","justificativa":"..."}
"""


def parse_chunk_index(chunk_id: str) -> int:
    """Extrai o índice numérico do chunk_id (último segmento ::0000)."""
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


def coverage_chunk(chunk_text: str, excerpt: str) -> tuple[float, int, int]:
    excerpt_tokens = informative_tokens(excerpt)
    if not excerpt_tokens:
        return 0.0, 0, 0
    chunk_tokens = set(informative_tokens(chunk_text))
    hits = sum(1 for t in excerpt_tokens if t in chunk_tokens)
    return hits / len(excerpt_tokens), hits, len(excerpt_tokens)


def excerpt_position(chunks_sorted: list[dict], excerpt: str) -> dict:
    """Decide se o excerpt aparece em chunk único, partido ou ausente.

    Retorna {kind, evidencia}:
      kind = "single" (substring em 1 chunk), "split" (substring quando
      concatena 2 adjacentes), "concat3" (3 adjacentes), ou "ausente".
    """
    excerpt_n = normalize_text(excerpt)
    if not excerpt_n:
        return {"kind": "ausente", "evidencia": "excerpt vazio"}

    # 1. Single chunk
    for c in chunks_sorted:
        if excerpt_n in normalize_text(c["texto"]):
            return {
                "kind": "single",
                "evidencia": f"chunk index {c['index']}",
            }

    # 2. Split between adjacent pair
    for i in range(len(chunks_sorted) - 1):
        a, b = chunks_sorted[i], chunks_sorted[i + 1]
        # Apenas pares com índices realmente adjacentes
        if b["index"] != a["index"] + 1:
            continue
        joined = normalize_text(a["texto"] + " " + b["texto"])
        if excerpt_n in joined:
            return {
                "kind": "split",
                "evidencia": (
                    f"chunks adjacentes {a['index']}+{b['index']}"
                ),
            }

    # 3. Span 3 adjacentes (raro, mas ocorre se excerpt for longo)
    for i in range(len(chunks_sorted) - 2):
        a, b, c = (
            chunks_sorted[i],
            chunks_sorted[i + 1],
            chunks_sorted[i + 2],
        )
        if b["index"] != a["index"] + 1 or c["index"] != b["index"] + 1:
            continue
        joined = normalize_text(
            a["texto"] + " " + b["texto"] + " " + c["texto"]
        )
        if excerpt_n in joined:
            return {
                "kind": "concat3",
                "evidencia": (
                    f"chunks {a['index']}+{b['index']}+{c['index']}"
                ),
            }

    return {"kind": "ausente", "evidencia": "não bate como substring"}


def call_judge(client, pergunta, expected, excerpt, chunk_text):
    user_msg = (
        f"PERGUNTA: {pergunta}\n\n"
        f"RESPOSTA ESPERADA: {expected}\n\n"
        f"SUPPORT_EXCERPT ESPERADO:\n{excerpt}\n\n"
        f"CHUNK RECUPERADO:\n{chunk_text}\n"
    )
    try:
        resp = client.chat.completions.create(
            model=JUDGE_MODEL,
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        return json.loads(resp.choices[0].message.content or "{}")
    except Exception as exc:
        return {"veredito": "ERRO", "justificativa": str(exc)}


def classify(
    *,
    primeiro_chunk_doc_rank: int | None,
    primeiro_match_rank: int | None,
    best_cov_top10: float,
    best_cov_overall: float,
    best_chunk_overall_rank: int | None,
    excerpt_pos: dict,
    judge_verdict_best_top10: str,
) -> tuple[str, str]:
    """Aplica a árvore de decisão e retorna (categoria, justificativa).

    Ordem dos sinais (mais forte primeiro):

    1. Existe chunk com cov ≥ 0.60 em algum lugar? Se sim, é problema de
       ranking ou pool, não de excerpt/GT.
    2. Se cov geral nunca atinge 0.60, é excerpt parafraseado/sintético
       (gt_ou_excerpt_problematico) OU semântica fraca dependendo do
       veredito do juiz.
    """
    # Caso 0: documento nem aparece no top-100
    if primeiro_chunk_doc_rank is None:
        return (
            "fora_do_pool",
            "Nenhum chunk do documento esperado entre os 100 recuperados.",
        )

    # Sinal forte: existe chunk com cobertura suficiente em algum lugar
    if best_cov_overall >= SUPPORT_EXCERPT_TOKEN_THRESHOLD:
        # Existe chunk que passaria no matching. Onde está?
        if best_chunk_overall_rank is None:
            return (
                "fora_do_pool",
                f"Chunk com cobertura {best_cov_overall:.2f} (≥0.60) "
                f"EXISTE no índice mas NÃO foi recuperado nem no top-100. "
                f"Retrieval semântico não o priorizou.",
            )
        if best_chunk_overall_rank > 10:
            return (
                "fora_do_top10",
                f"Chunk com cobertura {best_cov_overall:.2f} (≥0.60) "
                f"existe em rank {best_chunk_overall_rank} (fora do "
                f"top-10). Retrieval o encontrou, mas mal rankeado.",
            )
        # best_chunk_overall_rank ≤ 10
        # Se está no top-10 e cov ≥ 0.60, matching deveria ter passado.
        # Se não passou (primeiro_match_rank None), há bug no matching.
        if primeiro_match_rank is None:
            return (
                "matching_falso_negativo",
                f"Chunk com cobertura {best_cov_overall:.2f} está em rank "
                f"{best_chunk_overall_rank} (top-10), mas primeiro_match_rank "
                f"é None. Inconsistência no código de matching.",
            )

    # best_cov_overall < 0.60. Excerpt não tem chunk "limpo" para casar.
    # Diferenciar:
    #   - split_chunk: excerpt aparece como substring concatenando adjacentes
    #   - matching_falso_negativo: cov no top-10 < 0.60 mas LLM diz SIM
    #   - retrieval_semantico_fraco: LLM diz NÃO em todos top-10
    #   - gt_ou_excerpt_problematico: excerpt nem como substring aparece
    if excerpt_pos["kind"] in ("split", "concat3"):
        return (
            "split_chunk",
            f"Support_excerpt aparece como substring apenas concatenando "
            f"chunks adjacentes ({excerpt_pos['evidencia']}). Chunking "
            f"partiu o trecho — nenhum chunk único atinge cov ≥ 0.60.",
        )

    if (
        best_cov_top10 < SUPPORT_EXCERPT_TOKEN_THRESHOLD
        and judge_verdict_best_top10 == "SIM"
    ):
        return (
            "matching_falso_negativo",
            f"Melhor chunk top-10 cov={best_cov_top10:.2f} (<0.60), mas "
            f"LLM diz que sustenta. Cobertura geral max={best_cov_overall:.2f} "
            f"também <0.60 — excerpt não bate por substring nem por "
            f"tokens, mas semanticamente está lá.",
        )

    if judge_verdict_best_top10 in ("NAO", "PARCIAL"):
        # Cov geral <0.60 e LLM rejeita os top-10. Distinguir:
        # - excerpt ausente como substring em todo o doc → mais provável GT/paráfrase
        # - excerpt aparece em algum chunk único → retrieval fraco
        if excerpt_pos["kind"] == "single":
            return (
                "retrieval_semantico_fraco",
                f"Excerpt está em chunk único do doc ({excerpt_pos['evidencia']}), "
                f"mas o retriever priorizou outros chunks que LLM rejeita. "
                f"Cov geral max={best_cov_overall:.2f}.",
            )
        return (
            "gt_ou_excerpt_problematico",
            f"Excerpt nem aparece como substring no doc (cov geral max="
            f"{best_cov_overall:.2f}), e o melhor chunk recuperado não "
            f"sustenta a resposta. Provável paráfrase ou síntese conceitual.",
        )

    # Fallback
    return (
        "matching_falso_negativo",
        f"Caso ambíguo. cov_top10={best_cov_top10:.2f}, "
        f"cov_overall={best_cov_overall:.2f}, juiz={judge_verdict_best_top10}, "
        f"excerpt={excerpt_pos['kind']}.",
    )


def main() -> None:
    print("Carregando ground truth ...", file=sys.stderr)
    todas = load_ground_truth_hub()
    foco = [q for q in todas if str(q.get("question_id")) in PERGUNTAS_FOCO]
    print(f"  {len(foco)} perguntas de foco.", file=sys.stderr)

    print(
        "Carregando metadata.parquet completo (melhor config) ...",
        file=sys.stderr,
    )
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
    print(f"  {len(df_all)} chunks no índice.", file=sys.stderr)

    print("Carregando retriever ...", file=sys.stderr)
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
        expected = str(q.get("expected_answer") or "")
        sources = list(q.get("relevant_sources") or [])
        # Balde 2 tem 1 fonte por pergunta (validado em A.4)
        src = sources[0]
        doc_id = str(src.get("document_id") or "")
        excerpt = str(src.get("support_excerpt") or "")

        print(f"\n=== {qid} (doc={doc_id}) ===", file=sys.stderr)

        # 1. Recuperação top-100
        chunks_top = retriever.retrieve(pergunta, top_k=TOP_K_RETRIEVE)

        # 2. Rank do primeiro chunk do doc esperado
        primeiro_chunk_doc_rank = None
        for rank, c in enumerate(chunks_top, start=1):
            if str(c.get("document_id") or "") == doc_id:
                primeiro_chunk_doc_rank = rank
                break

        # 3. Rank do primeiro chunk que passaria no matching atual
        primeiro_match_rank = None
        for rank, c in enumerate(chunks_top, start=1):
            if str(c.get("document_id") or "") != doc_id:
                continue
            if section_match(c, src):
                primeiro_match_rank = rank
                break
            cov, _, _ = coverage_chunk(str(c.get("texto") or ""), excerpt)
            if cov >= SUPPORT_EXCERPT_TOKEN_THRESHOLD:
                primeiro_match_rank = rank
                break

        # 4. Melhor cobertura entre TODOS os chunks do doc esperado
        doc_chunks = df_all[df_all["document_id"] == doc_id].sort_values(
            "index"
        )
        all_doc_chunks_list = [
            {
                "index": int(row["index"]),
                "chunk_id": row["chunk_id"],
                "texto": str(row.get("texto") or ""),
            }
            for _, row in doc_chunks.iterrows()
        ]
        best_cov_overall = 0.0
        best_chunk_overall = None
        for c in all_doc_chunks_list:
            cov, _, _ = coverage_chunk(c["texto"], excerpt)
            if cov > best_cov_overall:
                best_cov_overall = cov
                best_chunk_overall = c

        # 5. Melhor cobertura entre chunks do doc no top-10
        best_cov_top10 = 0.0
        best_chunk_top10 = None
        for rank, c in enumerate(chunks_top[:10], start=1):
            if str(c.get("document_id") or "") != doc_id:
                continue
            cov, _, _ = coverage_chunk(str(c.get("texto") or ""), excerpt)
            if cov > best_cov_top10:
                best_cov_top10 = cov
                best_chunk_top10 = {
                    "rank": rank,
                    "chunk_id": c.get("chunk_id"),
                    "texto": str(c.get("texto") or ""),
                    "coverage": cov,
                }

        # 6. Posição do excerpt: single / split / ausente
        excerpt_pos = excerpt_position(all_doc_chunks_list, excerpt)

        # 6b. Onde está o best_chunk_overall no ranking do top-100?
        best_chunk_overall_rank = None
        if best_chunk_overall is not None:
            target_chunk_id = best_chunk_overall["chunk_id"]
            for rank, c in enumerate(chunks_top, start=1):
                if str(c.get("chunk_id") or "") == str(target_chunk_id):
                    best_chunk_overall_rank = rank
                    break

        # 7. LLM judge do melhor chunk do top-10 (se houver)
        if best_chunk_top10 is not None:
            judgment = call_judge(
                client,
                pergunta=pergunta,
                expected=expected,
                excerpt=excerpt,
                chunk_text=best_chunk_top10["texto"],
            )
        else:
            judgment = {
                "veredito": "N/A",
                "justificativa": "Nenhum chunk do doc esperado no top-10.",
            }

        # 8. Classificação
        categoria, justificativa = classify(
            primeiro_chunk_doc_rank=primeiro_chunk_doc_rank,
            primeiro_match_rank=primeiro_match_rank,
            best_cov_top10=best_cov_top10,
            best_cov_overall=best_cov_overall,
            best_chunk_overall_rank=best_chunk_overall_rank,
            excerpt_pos=excerpt_pos,
            judge_verdict_best_top10=str(judgment.get("veredito", "")),
        )

        resultados.append(
            {
                "question_id": qid,
                "pergunta": pergunta,
                "expected_answer": expected,
                "document_id": doc_id,
                "section_label": str(src.get("section_label") or ""),
                "support_excerpt": excerpt,
                "primeiro_chunk_doc_rank_top100": primeiro_chunk_doc_rank,
                "primeiro_match_rank_top100": primeiro_match_rank,
                "best_coverage_overall": round(best_cov_overall, 3),
                "best_chunk_overall_index": (
                    best_chunk_overall["index"]
                    if best_chunk_overall is not None
                    else None
                ),
                "best_chunk_overall_rank_no_top100": best_chunk_overall_rank,
                "best_coverage_top10": round(best_cov_top10, 3),
                "best_chunk_top10": best_chunk_top10,
                "excerpt_position": excerpt_pos,
                "judge_verdict": judgment,
                "categoria": categoria,
                "categoria_justificativa": justificativa,
                "n_chunks_do_doc_no_indice": len(all_doc_chunks_list),
            }
        )

    # Renderização
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# 1.2b — Diagnóstico do balde 2 (gt-0005/17/25/34)\n")
    lines.append(
        "Após refutação de H8 em 1.2 (threshold 0.30 → 89% falsos "
        "positivos), o balde 2 voltou a ser falha real. Este documento "
        "explica caso a caso usando 6 categorias predefinidas.\n"
    )
    lines.append(
        "Config: text-embedding-3-large + fixed-size + markdown + flat. "
        "Top-100 recuperados. Threshold de matching inalterado (0.60). "
        f"Juiz: {JUDGE_MODEL}.\n"
    )

    # Tabela-resumo
    lines.append("## Resumo\n")
    lines.append(
        "| qid | doc rank top-100 | match rank | best cov top-10 | "
        "best cov geral | excerpt pos | juiz | **categoria** |"
    )
    lines.append("|---|---:|---:|---:|---:|---|---|---|")
    for r in resultados:
        lines.append(
            f"| {r['question_id']} "
            f"| {r['primeiro_chunk_doc_rank_top100']} "
            f"| {r['primeiro_match_rank_top100']} "
            f"| {r['best_coverage_top10']} "
            f"| {r['best_coverage_overall']} "
            f"| {r['excerpt_position']['kind']} "
            f"| {r['judge_verdict'].get('veredito', '')} "
            f"| **{r['categoria']}** |"
        )

    # Detalhe por pergunta
    for r in resultados:
        lines.append(f"\n---\n\n## {r['question_id']}\n")
        lines.append(f"**Pergunta:** {r['pergunta']}\n")
        lines.append(f"**Resposta esperada:** {r['expected_answer']}\n")
        lines.append(f"**Doc esperado:** `{r['document_id']}` "
                     f"({r['n_chunks_do_doc_no_indice']} chunks no índice)")
        lines.append(f"**Section label:** `{r['section_label']}`")
        lines.append(f"**Support excerpt:** > {r['support_excerpt']}\n")

        lines.append("**Métricas:**")
        lines.append(
            f"- Primeiro chunk do doc em rank "
            f"`{r['primeiro_chunk_doc_rank_top100']}` (top-100)"
        )
        lines.append(
            f"- Primeiro chunk passando matching (threshold 0.60) em rank "
            f"`{r['primeiro_match_rank_top100']}`"
        )
        lines.append(
            f"- Melhor cobertura no top-10: **{r['best_coverage_top10']}**"
        )
        lines.append(
            f"- Melhor cobertura considerando TODOS os chunks do doc: "
            f"**{r['best_coverage_overall']}** "
            f"(chunk index {r['best_chunk_overall_index']}, "
            f"rank no top-100: {r['best_chunk_overall_rank_no_top100']})"
        )
        lines.append(
            f"- Position do excerpt: **{r['excerpt_position']['kind']}** "
            f"({r['excerpt_position']['evidencia']})"
        )

        if r["best_chunk_top10"]:
            bt = r["best_chunk_top10"]
            texto_short = bt["texto"][:400].replace("|", "\\|")
            lines.append(
                f"\n**Melhor chunk top-10** (rank {bt['rank']}, "
                f"cov {bt['coverage']:.3f}):\n"
                f"> {texto_short}"
            )
        lines.append(
            f"\n**Juiz LLM**: {r['judge_verdict'].get('veredito')} — "
            f"{r['judge_verdict'].get('justificativa', '')}\n"
        )
        lines.append(f"**Categoria atribuída: `{r['categoria']}`**")
        lines.append(f"{r['categoria_justificativa']}")

    # Agregado
    lines.append("\n---\n\n## Distribuição por categoria\n")
    from collections import Counter
    cats = Counter(r["categoria"] for r in resultados)
    lines.append("| categoria | n |")
    lines.append("|---|---:|")
    for cat, n in cats.most_common():
        lines.append(f"| `{cat}` | {n} |")

    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print()
    print("=== Resumo ===")
    for r in resultados:
        print(
            f"  {r['question_id']}: cat=`{r['categoria']}` "
            f"(doc_rank={r['primeiro_chunk_doc_rank_top100']}, "
            f"match_rank={r['primeiro_match_rank_top100']}, "
            f"best_cov_top10={r['best_coverage_top10']:.2f}, "
            f"excerpt={r['excerpt_position']['kind']}, "
            f"juiz={r['judge_verdict'].get('veredito')})"
        )
    print(f"\nDetalhe completo: {OUT_PATH}")


if __name__ == "__main__":
    main()
