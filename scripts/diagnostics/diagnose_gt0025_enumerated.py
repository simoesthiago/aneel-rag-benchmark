"""B — Diagnóstico de gt-0025: excerpt enumerado com condições a/b/c/d.

Verifica se as 4 condições enumeradas (a, b, c, d) do support_excerpt
aparecem juntas em um chunk único ou partidas entre chunks por estratégia
de chunking. Compara fixed-size, article-aware e hierarchical.

Classifica em uma de 4 categorias:
- excerpt_longo_em_um_chunk_mas_mal_ranqueado
- excerpt_partido_entre_chunks
- matching_exigente_demais
- retrieval_semantico_fraco

Sem rerank, sem mudança em código de produção.

Saída: data/evaluation/results/diagnostic/gt0025_enumerated_excerpt.md

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
            time.sleep(5 * (tentativa + 1))
    raise last_exc if last_exc else RuntimeError("download falhou")


_hub._read_hub_file_bytes = _patched_read_hub_file_bytes

import pandas as pd  # noqa: E402

from src.config.settings import HF_DATASET_REPO  # noqa: E402
from src.evaluation.ground_truth import (  # noqa: E402
    informative_tokens,
    load_ground_truth_hub,
)
from src.evaluation.matching import (  # noqa: E402
    SUPPORT_EXCERPT_TOKEN_THRESHOLD,
)
from src.rag.retriever import Retriever  # noqa: E402
from src.vectorstore.hub import hub_prefix  # noqa: E402
from src.vectorstore.metadata import (  # noqa: E402
    METADATA_FILENAME,
    PARENTS_FILENAME,
)

QID = "gt-0025"

# Frases-âncora distintivas de cada condição (escolhidas para minimizar
# falsos positivos em outras partes do PRORET)
CONDICOES = {
    "a": "imóvel elegível",
    "b": "registrado na contabilidade",
    "c": "documentação que comprove a aquisição",
    "d": "processo de regularização",
}

CONFIGS: list[tuple[str, str, str, str, str]] = [
    ("text-embedding-3-large", "fixed-size", "markdown", "flat", "fixed/md/flat"),
    ("text-embedding-3-large", "fixed-size", "texto", "flat", "fixed/tx/flat"),
    ("text-embedding-3-large", "article-aware", "markdown", "flat", "article/md/flat"),
    ("text-embedding-3-large", "article-aware", "texto", "flat", "article/tx/flat"),
    ("text-embedding-3-large", "hierarchical-child", "markdown", "hierarchical", "hier/md/hier"),
    ("text-embedding-3-large", "hierarchical-child", "texto", "hierarchical", "hier/tx/hier"),
]

TOP_K = 100

OUT_PATH = Path(
    "data/evaluation/results/diagnostic/gt0025_enumerated_excerpt.md"
)


def parse_chunk_index(chunk_id: str) -> int:
    try:
        return int(chunk_id.rsplit("::", 1)[-1])
    except (ValueError, AttributeError):
        return -1


def normalize_lower(text: str) -> str:
    """Lower + remove duplicate spaces, para busca de frases curtas."""
    return " ".join(str(text).lower().split())


def coverage_chunk(chunk_text: str, excerpt: str) -> float:
    excerpt_tokens = informative_tokens(excerpt)
    if not excerpt_tokens:
        return 0.0
    chunk_tokens = set(informative_tokens(chunk_text))
    hits = sum(1 for t in excerpt_tokens if t in chunk_tokens)
    return hits / len(excerpt_tokens)


def find_condicoes_in_chunks(
    chunks_list: list[dict], condicoes: dict[str, str]
) -> dict[str, list[int]]:
    """Para cada condição, devolve a lista de chunk_index onde aparece."""
    pos: dict[str, list[int]] = {k: [] for k in condicoes}
    for c in chunks_list:
        texto_norm = normalize_lower(c["texto"])
        for k, anchor in condicoes.items():
            if anchor.lower() in texto_norm:
                pos[k].append(c["index"])
    return pos


def classificar(
    *,
    condicoes_chunks_doc_completo: dict[str, list[int]],
    best_cov_overall: float,
    best_cov_top10: float,
    chunk_doc_no_top10: bool,
) -> tuple[str, str]:
    """Aplica regras de classificação."""
    # 1. Excerpt todo em um chunk único?
    chunks_com_todas = set.intersection(
        *(set(v) for v in condicoes_chunks_doc_completo.values())
    ) if all(condicoes_chunks_doc_completo.values()) else set()

    if chunks_com_todas:
        if best_cov_top10 < SUPPORT_EXCERPT_TOKEN_THRESHOLD and chunk_doc_no_top10:
            return (
                "matching_exigente_demais",
                f"As 4 condições estão num único chunk (índice "
                f"{sorted(chunks_com_todas)}). Esse chunk está no top-10 "
                f"mas cov={best_cov_top10:.2f} < {SUPPORT_EXCERPT_TOKEN_THRESHOLD}. "
                "Excerpt é tão longo que mesmo presença completa não dá "
                "cobertura de tokens informativos suficiente.",
            )
        if not chunk_doc_no_top10:
            return (
                "excerpt_longo_em_um_chunk_mas_mal_ranqueado",
                f"As 4 condições estão num chunk único (índice "
                f"{sorted(chunks_com_todas)}), mas esse chunk não está "
                "no top-10. Retrieval não o priorizou.",
            )

    # 2. Cada condição em chunks diferentes?
    all_chunks = []
    for v in condicoes_chunks_doc_completo.values():
        all_chunks.extend(v)
    if all_chunks and len(set(all_chunks)) > 1:
        return (
            "excerpt_partido_entre_chunks",
            f"Condições aparecem em chunks distintos: "
            f"{condicoes_chunks_doc_completo}. Chunking partiu o excerpt.",
        )

    # 3. Excerpt nem aparece (provável paráfrase ou extração diferente)
    if not all_chunks:
        return (
            "retrieval_semantico_fraco",
            "Nenhuma das âncoras a/b/c/d encontradas em chunks do doc — "
            "excerpt pode estar parafraseado ou extraído de outra fonte. "
            "Reabre H3 parcialmente.",
        )

    return (
        "retrieval_semantico_fraco",
        f"Caso ambíguo. Cov_overall={best_cov_overall:.2f}, "
        f"cov_top10={best_cov_top10:.2f}. Condições: "
        f"{condicoes_chunks_doc_completo}",
    )


def main() -> None:
    print("Carregando ground truth ...", file=sys.stderr)
    todas = load_ground_truth_hub()
    q_obj = next(q for q in todas if str(q.get("question_id")) == QID)
    pergunta = str(q_obj.get("question") or "")
    src = list(q_obj.get("relevant_sources") or [])[0]
    doc_id = str(src.get("document_id") or "")
    excerpt = str(src.get("support_excerpt") or "")

    resultados: list[dict] = []
    for cfg in CONFIGS:
        model, strategy, metodo, mode, label = cfg
        print(f"\n=== Config: {label} ===", file=sys.stderr)

        # Decide qual parquet ler: para hierarchical_mode, usamos parents.parquet
        # (são os chunks devolvidos no retrieval). Para outras, metadata.parquet.
        prefix = hub_prefix(
            provider="openai",
            model=model,
            chunk_strategy=strategy,
            metodo_extracao=metodo,
        )
        if strategy == "hierarchical-child" and mode == "hierarchical":
            chunks_filename = PARENTS_FILENAME
        else:
            chunks_filename = METADATA_FILENAME

        local = hf_hub_download(
            repo_id=HF_DATASET_REPO,
            filename=f"{prefix}/{chunks_filename}",
            repo_type="dataset",
        )
        df = pd.read_parquet(local, engine="pyarrow")
        df["index"] = df["chunk_id"].apply(parse_chunk_index)
        doc_df = df[df["document_id"] == doc_id].sort_values("index")
        doc_chunks_list = [
            {
                "index": int(row["index"]),
                "chunk_id": row["chunk_id"],
                "texto": str(row.get("texto") or ""),
            }
            for _, row in doc_df.iterrows()
        ]
        n_chunks_doc = len(doc_chunks_list)

        # Localiza as 4 condições nos chunks do doc
        condicoes_pos = find_condicoes_in_chunks(doc_chunks_list, CONDICOES)
        # Cobertura geral
        best_cov_overall = 0.0
        best_overall_idx = None
        for c in doc_chunks_list:
            cov = coverage_chunk(c["texto"], excerpt)
            if cov > best_cov_overall:
                best_cov_overall = cov
                best_overall_idx = c["index"]

        # Retrieval para checar top-10
        retriever = Retriever(
            provider="openai",
            model=model,
            chunk_strategy=strategy,
            metodo_extracao=metodo,
            mode=mode,
        )
        chunks_top = retriever.retrieve(pergunta, top_k=TOP_K)
        chunks_top_doc_ids = [
            str(c.get("chunk_id") or "") for c in chunks_top[:10]
        ]
        chunks_top_doc_indices_top10 = [
            parse_chunk_index(cid) for cid in chunks_top_doc_ids
        ]
        # Filtra os do doc certo
        top10_doc_chunks = [
            i for i, c in enumerate(chunks_top[:10])
            if str(c.get("document_id") or "") == doc_id
        ]
        chunk_doc_no_top10 = len(top10_doc_chunks) > 0
        best_cov_top10 = 0.0
        for c in chunks_top[:10]:
            if str(c.get("document_id") or "") != doc_id:
                continue
            cov = coverage_chunk(str(c.get("texto") or ""), excerpt)
            if cov > best_cov_top10:
                best_cov_top10 = cov

        categoria, justificativa = classificar(
            condicoes_chunks_doc_completo=condicoes_pos,
            best_cov_overall=best_cov_overall,
            best_cov_top10=best_cov_top10,
            chunk_doc_no_top10=chunk_doc_no_top10,
        )

        resultados.append(
            {
                "config_label": label,
                "n_chunks_doc": n_chunks_doc,
                "condicoes_pos": condicoes_pos,
                "best_cov_overall": round(best_cov_overall, 3),
                "best_overall_idx": best_overall_idx,
                "best_cov_top10": round(best_cov_top10, 3),
                "chunk_doc_no_top10": chunk_doc_no_top10,
                "n_chunks_doc_top10": len(top10_doc_chunks),
                "categoria": categoria,
                "justificativa": justificativa,
            }
        )

    # Render
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append(f"# gt-0025 — diagnóstico de excerpt enumerado\n")
    lines.append(
        "Verifica se as 4 condições (a, b, c, d) do support_excerpt "
        "aparecem juntas ou partidas entre chunks, por estratégia de "
        "chunking.\n"
    )
    lines.append(f"**Pergunta:** {pergunta}")
    lines.append(f"**Doc esperado:** `{doc_id}`")
    lines.append(f"**Support excerpt:** > {excerpt}\n")
    lines.append("**Âncoras procuradas:**")
    for k, v in CONDICOES.items():
        lines.append(f"- ({k}) `{v}`")
    lines.append("")

    lines.append("## Resultados por config\n")
    lines.append(
        "| config | n_chunks doc | a (chunks) | b | c | d | "
        "best_cov_overall | best_cov_top10 | **categoria** |"
    )
    lines.append("|---|---:|---|---|---|---|---:|---:|---|")
    for r in resultados:
        cp = r["condicoes_pos"]
        a = ",".join(str(x) for x in cp.get("a", [])) or "—"
        b = ",".join(str(x) for x in cp.get("b", [])) or "—"
        c = ",".join(str(x) for x in cp.get("c", [])) or "—"
        d = ",".join(str(x) for x in cp.get("d", [])) or "—"
        lines.append(
            f"| {r['config_label']} | {r['n_chunks_doc']} "
            f"| {a} | {b} | {c} | {d} "
            f"| {r['best_cov_overall']} "
            f"| {r['best_cov_top10']} "
            f"| **`{r['categoria']}`** |"
        )

    lines.append("\n## Justificativas\n")
    for r in resultados:
        lines.append(f"- **{r['config_label']}** → `{r['categoria']}`")
        lines.append(f"  - {r['justificativa']}")

    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print()
    print("=== Resumo gt-0025 por config ===")
    for r in resultados:
        cp = r["condicoes_pos"]
        all_chunks = set()
        for v in cp.values():
            all_chunks.update(v)
        all_set = sorted(all_chunks)
        print(
            f"  {r['config_label']:25s} | chunks doc: "
            f"{r['n_chunks_doc']:5d} | cond_indices: {all_set} | "
            f"best_cov_overall: {r['best_cov_overall']:.2f} | "
            f"cat: {r['categoria']}"
        )
    print(f"\nSaída: {OUT_PATH}")


if __name__ == "__main__":
    main()
