"""Compara o parser `article-aware` publicado contra o protótipo local.

Este script mede apenas shape textual dos chunks. Ele não publica dados, não
gera embeddings e não avalia ranking semântico. O objetivo é responder: "se o
parser parar de cortar referências cruzadas, a fragmentação cai sem piorar a
cobertura dos excertos do ground truth nos documentos-alvo?"
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402
from huggingface_hub import hf_hub_download  # noqa: E402

from src.chunking.article_aware import chunk_article_aware  # noqa: E402
from src.chunking.hierarchical import chunk_parent_child  # noqa: E402
from src.config.settings import HF_DATASET_REPO  # noqa: E402
from src.evaluation.ground_truth import (  # noqa: E402
    informative_tokens,
    load_ground_truth_jsonl,
)
from src.evaluation.matching import SUPPORT_EXCERPT_TOKEN_THRESHOLD  # noqa: E402
from src.ingestion.uploader import carregar_corpus_hub  # noqa: E402
from src.vectorstore.hub import hub_prefix  # noqa: E402
from src.vectorstore.metadata import (  # noqa: E402
    METADATA_FILENAME,
    PARENTS_FILENAME,
)

PROVIDER = "openai"
MODEL = "text-embedding-3-large"
METODOS = ("markdown", "texto")
TARGET_DOCUMENT_IDS = (
    "ren-2021-1000",
    "ren-2015-694",
    "ren-2011-456",
    "proret-modulo02-subm2-1-proret-submod-2-1-v-2-3-aren2020874",
    "proret-modulo02-subm2-4-proret-submod-2-4-v-2-1-aren2018807",
    "prodist-modulo-10",
    "proc-rede-8-3-pr",
    "manual-air-modelo-de-air-srm-leilao-ee-roraima",
)
GT_PATH = Path("data/evaluation/ground_truth/aneel_retrieval_50.jsonl")
OUT_JSON = Path(
    "data/evaluation/results/diagnostic/article_parser_prototype.json"
)
OUT_MD = Path("data/evaluation/results/diagnostic/article_parser_prototype.md")
TINY_WORDS = 10
SMALL_WORDS = 30


def main() -> None:
    """Gera comparação local entre baseline publicado e parser prototipado."""
    documents = _load_target_documents()
    gt_sources = _load_relevant_sources()
    published = _load_published_target_chunks()
    prototype = _build_prototype_chunks(documents)

    rows = _compare_shapes(published, prototype)
    coverage_rows = _compare_support_coverage(published, prototype, gt_sources)
    recommendation = _recommend(rows, coverage_rows)

    payload = {
        "target_document_ids": list(TARGET_DOCUMENT_IDS),
        "support_threshold": SUPPORT_EXCERPT_TOKEN_THRESHOLD,
        "shape_comparison": rows,
        "support_coverage": coverage_rows,
        "recommendation": recommendation,
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    OUT_MD.write_text(_render_markdown(payload), encoding="utf-8")
    print(f"JSON: {OUT_JSON}")
    print(f"Markdown: {OUT_MD}")


def _load_target_documents() -> pd.DataFrame:
    df = carregar_corpus_hub()
    selected = df[
        df["id"].astype(str).isin(TARGET_DOCUMENT_IDS)
        & df["metodo_extracao"].astype(str).isin(METODOS)
    ].copy()
    expected = len(TARGET_DOCUMENT_IDS) * len(METODOS)
    if len(selected) != expected:
        found = sorted(
            f"{row.id}|{row.metodo_extracao}"
            for row in selected[["id", "metodo_extracao"]].itertuples()
        )
        raise RuntimeError(
            f"Esperados {expected} documentos-alvo texto/markdown; "
            f"encontrados {len(selected)}: {found}"
        )
    return selected.reset_index(drop=True)


def _load_relevant_sources() -> list[dict[str, Any]]:
    rows = load_ground_truth_jsonl(GT_PATH)
    sources: list[dict[str, Any]] = []
    for question in rows:
        if question.get("answerability") != "corpus_supported":
            continue
        for source in question.get("relevant_sources") or []:
            if str(source.get("document_id")) in TARGET_DOCUMENT_IDS:
                sources.append(
                    {
                        "question_id": question["question_id"],
                        "question": question["question"],
                        **source,
                    }
                )
    return sources


def _load_published_target_chunks() -> dict[tuple[str, str, str], pd.DataFrame]:
    result: dict[tuple[str, str, str], pd.DataFrame] = {}
    for metodo in METODOS:
        article = _read_published("article-aware", metodo, METADATA_FILENAME)
        result[("article-aware", metodo, "chunks")] = _filter_targets(article)

        children = _read_published(
            "hierarchical-child",
            metodo,
            METADATA_FILENAME,
        )
        result[("hierarchical-child", metodo, "chunks")] = _filter_targets(children)

        parents = _read_published(
            "hierarchical-child",
            metodo,
            PARENTS_FILENAME,
        )
        result[("hierarchical-child", metodo, "parents")] = _filter_targets(parents)
    return result


def _read_published(strategy: str, metodo: str, filename: str) -> pd.DataFrame:
    prefix = hub_prefix(
        provider=PROVIDER,
        model=MODEL,
        chunk_strategy=strategy,
        metodo_extracao=metodo,
    )
    local = hf_hub_download(
        repo_id=HF_DATASET_REPO,
        filename=f"{prefix}/{filename}",
        repo_type="dataset",
    )
    return pd.read_parquet(local, engine="pyarrow")


def _filter_targets(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["document_id"].astype(str).isin(TARGET_DOCUMENT_IDS)].copy()


def _build_prototype_chunks(
    documents: pd.DataFrame,
) -> dict[tuple[str, str, str], pd.DataFrame]:
    result: dict[tuple[str, str, str], pd.DataFrame] = {}
    for metodo in METODOS:
        docs = documents[documents["metodo_extracao"].astype(str) == metodo]

        article_records: list[dict[str, Any]] = []
        hierarchical_records: list[dict[str, Any]] = []
        for document in docs.to_dict("records"):
            article_records.extend(chunk_article_aware(document))
            hierarchical_records.extend(chunk_parent_child(document))

        article = pd.DataFrame(article_records)
        hierarchical = pd.DataFrame(hierarchical_records)
        children = hierarchical[
            hierarchical["chunk_strategy"] == "hierarchical-child"
        ].copy()
        parents = hierarchical[
            hierarchical["chunk_strategy"] == "hierarchical"
        ].copy()

        result[("article-aware", metodo, "chunks")] = article
        result[("hierarchical-child", metodo, "chunks")] = children
        result[("hierarchical-child", metodo, "parents")] = parents
    return result


def _compare_shapes(
    published: dict[tuple[str, str, str], pd.DataFrame],
    prototype: dict[tuple[str, str, str], pd.DataFrame],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in sorted(published):
        before = _shape_summary(published[key])
        after = _shape_summary(prototype[key])
        rows.append(
            {
                "strategy": key[0],
                "metodo_extracao": key[1],
                "kind": key[2],
                "published": before,
                "prototype": after,
                "delta_chunks": after["n_chunks"] - before["n_chunks"],
                "delta_small_lt_30": after["small_lt_30"] - before["small_lt_30"],
            }
        )
    return rows


def _shape_summary(df: pd.DataFrame) -> dict[str, Any]:
    words = _word_count(df)
    total = int(len(words))
    tiny = int((words < TINY_WORDS).sum())
    small = int((words < SMALL_WORDS).sum())
    return {
        "n_chunks": total,
        "tiny_lt_10": tiny,
        "tiny_lt_10_pct": round(tiny / total, 4) if total else 0.0,
        "small_lt_30": small,
        "small_lt_30_pct": round(small / total, 4) if total else 0.0,
        "p50_words": int(words.quantile(0.5)) if total else 0,
        "p95_words": int(words.quantile(0.95)) if total else 0,
    }


def _word_count(df: pd.DataFrame) -> pd.Series:
    return df["texto"].fillna("").astype(str).str.split().map(len)


def _compare_support_coverage(
    published: dict[tuple[str, str, str], pd.DataFrame],
    prototype: dict[tuple[str, str, str], pd.DataFrame],
    sources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in sorted(published):
        if key[2] != "chunks" and key[0] != "hierarchical-child":
            continue
        before = published[key]
        after = prototype[key]
        for source in sources:
            doc_id = str(source.get("document_id"))
            before_doc = _sort_doc_chunks(before, doc_id)
            after_doc = _sort_doc_chunks(after, doc_id)
            if before_doc.empty and after_doc.empty:
                continue
            before_cov = _best_coverage(before_doc, source)
            after_cov = _best_coverage(after_doc, source)
            rows.append(
                {
                    "strategy": key[0],
                    "metodo_extracao": key[1],
                    "kind": key[2],
                    "question_id": source["question_id"],
                    "document_id": doc_id,
                    "published_best_coverage": before_cov["coverage"],
                    "prototype_best_coverage": after_cov["coverage"],
                    "published_best_chunk": before_cov["chunk_id"],
                    "prototype_best_chunk": after_cov["chunk_id"],
                    "published_fragmentation": _fragmentation_kind(
                        before_doc, source
                    ),
                    "prototype_fragmentation": _fragmentation_kind(
                        after_doc, source
                    ),
                }
            )
    return rows


def _sort_doc_chunks(df: pd.DataFrame, doc_id: str) -> pd.DataFrame:
    doc = df[df["document_id"].astype(str) == doc_id].copy()
    if doc.empty:
        return doc
    doc["sort_index"] = doc["chunk_id"].astype(str).map(_chunk_index)
    return doc.sort_values("sort_index").reset_index(drop=True)


def _chunk_index(chunk_id: str) -> int:
    try:
        return int(str(chunk_id).rsplit("::", 1)[-1])
    except ValueError:
        return -1


def _best_coverage(df: pd.DataFrame, source: dict[str, Any]) -> dict[str, Any]:
    best = {"coverage": 0.0, "chunk_id": None}
    for _, row in df.iterrows():
        coverage = _coverage(str(row.get("texto") or ""), source)
        if coverage > best["coverage"]:
            best = {
                "coverage": round(coverage, 4),
                "chunk_id": str(row.get("chunk_id") or ""),
            }
    return best


def _coverage(text: str, source: dict[str, Any]) -> float:
    excerpt_tokens = informative_tokens(str(source.get("support_excerpt") or ""))
    if not excerpt_tokens:
        return 0.0
    chunk_tokens = set(informative_tokens(text))
    hits = sum(1 for token in excerpt_tokens if token in chunk_tokens)
    return hits / len(excerpt_tokens)


def _fragmentation_kind(df: pd.DataFrame, source: dict[str, Any]) -> str:
    if df.empty:
        return "doc_ausente"
    threshold = SUPPORT_EXCERPT_TOKEN_THRESHOLD
    coverages = [
        _coverage(str(row.get("texto") or ""), source)
        for _, row in df.iterrows()
    ]
    if coverages and max(coverages) >= threshold:
        return "chunk_unico_cobre"
    texts = df["texto"].fillna("").astype(str).tolist()
    for window in (2, 3):
        for index in range(0, max(0, len(texts) - window + 1)):
            joined = " ".join(texts[index : index + window])
            if _coverage(joined, source) >= threshold:
                return f"partido_em_{window}_chunks_adjacentes"
    return "sem_cobertura_suficiente"


def _recommend(
    rows: list[dict[str, Any]],
    coverage_rows: list[dict[str, Any]],
) -> str:
    chunk_rows = [row for row in rows if row["kind"] == "chunks"]
    reductions: dict[str, float] = {}
    for metodo in METODOS:
        metodo_rows = [
            row for row in chunk_rows if row["metodo_extracao"] == metodo
        ]
        before_small = sum(row["published"]["small_lt_30"] for row in metodo_rows)
        after_small = sum(row["prototype"]["small_lt_30"] for row in metodo_rows)
        reductions[metodo] = (
            (before_small - after_small) / before_small if before_small else 0.0
        )

    regressions = [
        row
        for row in coverage_rows
        if row["prototype_best_coverage"] + 0.001
        < row["published_best_coverage"]
    ]
    if min(reductions.values()) >= 0.25 and not regressions:
        return (
            "Protótipo reduz fragmentação de forma material sem perda de "
            "cobertura textual nos documentos-alvo. Recomendar fase posterior "
            "de rebuild oficial das estratégias estruturais."
        )
    if reductions.get("markdown", 0.0) < 0.25 and not regressions:
        return (
            "Protótipo reduz bem a fragmentação em texto, mas ainda reduz "
            "pouco em markdown, onde H12 era mais grave. Não recomendar "
            "re-embedding ainda; documentar e investigar limpeza/sectioning "
            "de markdown antes de rebuild oficial."
        )
    return (
        "Protótipo reduz fragmentação, mas há perda de cobertura textual em "
        "alguns excertos. Revisar manualmente antes de qualquer rebuild."
    )


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Protótipo local do parser article-aware",
        "",
        "Este relatório compara metadados publicados contra chunks gerados "
        "localmente com o parser atual da branch.",
        "",
        f"Recomendação: {payload['recommendation']}",
        "",
        "## Shape dos chunks",
        "",
        "| strategy | método | kind | n pub | n proto | <30 pub | <30 proto | p50 pub | p50 proto |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["shape_comparison"]:
        pub = row["published"]
        proto = row["prototype"]
        lines.append(
            f"| {row['strategy']} | {row['metodo_extracao']} | "
            f"{row['kind']} | {pub['n_chunks']} | {proto['n_chunks']} | "
            f"{pub['small_lt_30']} | {proto['small_lt_30']} | "
            f"{pub['p50_words']} | {proto['p50_words']} |"
        )

    lines.extend(["", "## Cobertura de support_excerpt", ""])
    lines.append(
        "| strategy | método | kind | qid | doc | cov pub | cov proto | frag pub | frag proto |"
    )
    lines.append("|---|---|---|---|---|---:|---:|---|---|")
    for row in payload["support_coverage"]:
        lines.append(
            f"| {row['strategy']} | {row['metodo_extracao']} | "
            f"{row['kind']} | {row['question_id']} | "
            f"{row['document_id']} | "
            f"{row['published_best_coverage']:.3f} | "
            f"{row['prototype_best_coverage']:.3f} | "
            f"{row['published_fragmentation']} | "
            f"{row['prototype_fragmentation']} |"
        )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
