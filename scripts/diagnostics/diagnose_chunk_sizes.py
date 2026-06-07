"""A.1 - Histograma de comprimento de chunks por estratégia.

Lê metadata.parquet (e parents.parquet quando aplicável) de cada uma das 12
vector stores publicadas no HuggingFace Hub e mostra distribuição de tamanho
em palavras. Serve para:

1. Descartar formalmente a hipótese de truncamento por limite de tokens
   do embedder (text-embedding-3-large = 8191 tokens, ~6300 palavras PT).
2. Servir de base para interpretar matching/recall por estratégia.

Hipóteses cobertas: B1 (truncamento), parcialmente H2/H8.
Saída: data/evaluation/results/diagnostic/chunk_size_histogram.md

NOTA: usa `huggingface_hub.hf_hub_download`, que materializa em
~/.cache/huggingface/hub/. Exceção explícita à regra Hub-first do projeto
— vale apenas para diagnóstico pontual. Ver seção Troubleshooting do
README.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402
from huggingface_hub import hf_hub_download  # noqa: E402

from src.config.settings import HF_DATASET_REPO  # noqa: E402
from src.vectorstore.hub import hub_prefix  # noqa: E402
from src.vectorstore.metadata import (  # noqa: E402
    METADATA_FILENAME,
    PARENTS_FILENAME,
)


def read_parquet_from_hub(repo_id: str, path: str) -> pd.DataFrame:
    """Wrapper que usa hf_hub_download (com retry/Xet integrados)."""
    local = hf_hub_download(repo_id=repo_id, filename=path, repo_type="dataset")
    return pd.read_parquet(local, engine="pyarrow")

PROVIDER = "openai"
MODELS = ("text-embedding-3-large", "text-embedding-3-small")
STRATEGIES = ("fixed-size", "article-aware", "hierarchical-child")
METODOS = ("markdown", "texto")
OUT_PATH = Path(
    "data/evaluation/results/diagnostic/chunk_size_histogram.md"
)

# Limite prático: ~6300 palavras PT ≈ 8000 tokens BPE
# (margem de segurança vs 8191 tokens do text-embedding-3-large/small)
WORDS_THRESHOLD_TOKEN_RISK = 6000


def describe_words(words: pd.Series) -> dict[str, int]:
    return {
        "n": int(len(words)),
        "min": int(words.min()),
        "p50": int(words.quantile(0.5)),
        "p95": int(words.quantile(0.95)),
        "p99": int(words.quantile(0.99)),
        "max": int(words.max()),
        "above_6000_words": int((words > WORDS_THRESHOLD_TOKEN_RISK).sum()),
    }


def main() -> None:
    rows: list[dict[str, object]] = []
    for model in MODELS:
        for strategy in STRATEGIES:
            for metodo in METODOS:
                prefix = hub_prefix(
                    provider=PROVIDER,
                    model=model,
                    chunk_strategy=strategy,
                    metodo_extracao=metodo,
                )
                meta_path = f"{prefix}/{METADATA_FILENAME}"
                print(f"Lendo {meta_path} ...", file=sys.stderr)
                df = read_parquet_from_hub(HF_DATASET_REPO, meta_path)
                words = df["texto"].astype(str).str.split().map(len)
                rows.append(
                    {
                        "model": model,
                        "strategy": strategy,
                        "metodo": metodo,
                        "kind": "chunks (filhos)",
                        **describe_words(words),
                    }
                )

                # Parents são idênticos entre modelos (mesmo texto, embedding
                # diferente). Lemos uma vez por (estratégia, método) usando
                # o "large" como ancora.
                if (
                    strategy == "hierarchical-child"
                    and model == "text-embedding-3-large"
                ):
                    parents_path = f"{prefix}/{PARENTS_FILENAME}"
                    print(
                        f"Lendo {parents_path} ...", file=sys.stderr
                    )
                    parents_df = read_parquet_from_hub(
                        HF_DATASET_REPO, parents_path
                    )
                    pwords = (
                        parents_df["texto"].astype(str).str.split().map(len)
                    )
                    rows.append(
                        {
                            "model": "(shared)",
                            "strategy": strategy,
                            "metodo": metodo,
                            "kind": "parents",
                            **describe_words(pwords),
                        }
                    )

    out_df = pd.DataFrame(rows)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        "# Histograma de comprimento de chunks (palavras)\n\n"
        f"Limite de risco de truncamento: {WORDS_THRESHOLD_TOKEN_RISK} "
        "palavras (~8000 tokens BPE, abaixo de 8191 do embedder OpenAI)\n\n"
        + out_df.to_markdown(index=False)
        + "\n",
        encoding="utf-8",
    )

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 200)
    print()
    print(out_df.to_string(index=False))

    total_oversized = int(out_df["above_6000_words"].sum())
    print()
    if total_oversized == 0:
        print(
            "✓ Hipótese B1 (truncamento) REFUTADA: nenhum chunk excede "
            f"{WORDS_THRESHOLD_TOKEN_RISK} palavras."
        )
    else:
        print(
            f"⚠ Hipótese B1 PARCIALMENTE CONFIRMADA: {total_oversized} "
            "chunks acima do limite de risco. Investigar quais estratégias."
        )
    print(f"\nTabela salva em: {OUT_PATH}")


if __name__ == "__main__":
    main()
