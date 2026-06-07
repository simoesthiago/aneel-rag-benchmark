"""1.1 — Inspeção de chunks tiny em article-aware markdown (H12 causa).

Hipótese H12: o chunking article-aware em markdown gera ~84k chunks com
p50=21 palavras (vs 34k chunks p50=52 em texto). Suspeita: regex ARTICLE_RE
em src/chunking/article_aware.py:13-15 está pegando cabeçalhos markdown
(`## Art. 1`, `**Art. 1º**`) como múltiplos matches, fragmentando demais.

Este script lê metadata.parquet do Hub para article-aware/markdown e
imprime amostras de chunks pequenos para inspeção visual da causa.

Sem fix automático. Apenas diagnóstico.

Saída: data/evaluation/results/diagnostic/h12_tiny_chunks_sample.md

NOTA: usa `huggingface_hub.hf_hub_download`, que materializa em
~/.cache/huggingface/hub/. Exceção explícita à regra Hub-first do projeto
— vale apenas para diagnóstico pontual. Ver Troubleshooting no README.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd  # noqa: E402
from huggingface_hub import hf_hub_download  # noqa: E402

from src.config.settings import HF_DATASET_REPO  # noqa: E402
from src.vectorstore.hub import hub_prefix  # noqa: E402
from src.vectorstore.metadata import METADATA_FILENAME  # noqa: E402

TARGET_STRATEGY = "article-aware"
TARGET_METODO = "markdown"
TARGET_MODEL = "text-embedding-3-large"  # chunks são iguais entre modelos
TINY_THRESHOLD_WORDS = 30
SAMPLE_PER_BUCKET = 15

OUT_PATH = Path(
    "data/evaluation/results/diagnostic/h12_tiny_chunks_sample.md"
)


def main() -> None:
    prefix = hub_prefix(
        provider="openai",
        model=TARGET_MODEL,
        chunk_strategy=TARGET_STRATEGY,
        metodo_extracao=TARGET_METODO,
    )
    path = f"{prefix}/{METADATA_FILENAME}"
    print(f"Baixando {path} ...", file=sys.stderr)
    local = hf_hub_download(
        repo_id=HF_DATASET_REPO, filename=path, repo_type="dataset"
    )
    df = pd.read_parquet(local, engine="pyarrow")
    df["n_words"] = df["texto"].astype(str).str.split().map(len)

    total = len(df)
    tiny = df[df["n_words"] < TINY_THRESHOLD_WORDS]
    print(
        f"  Total: {total} chunks; tiny (<{TINY_THRESHOLD_WORDS} pal): "
        f"{len(tiny)} ({len(tiny)/total*100:.1f}%)",
        file=sys.stderr,
    )

    # Buckets: muito tiny (<10), tiny (10-19), pequeno-medio (20-29)
    buckets = [
        ("muito_tiny (<10 palavras)", df[df["n_words"] < 10]),
        ("tiny (10-19 palavras)", df[(df["n_words"] >= 10) & (df["n_words"] < 20)]),
        ("pequeno (20-29 palavras)", df[(df["n_words"] >= 20) & (df["n_words"] < 30)]),
    ]

    lines: list[str] = []
    lines.append("# H12 — amostra de chunks tiny em article-aware/markdown\n")
    lines.append(
        f"Stats globais: {total} chunks total, {len(tiny)} "
        f"(<{TINY_THRESHOLD_WORDS} palavras) = {len(tiny)/total*100:.1f}%\n"
    )
    lines.append(
        "Para cada bucket, amostra aleatória com `chunk_id`, `artigo`, "
        "`secao` e texto bruto. **O que procurar**: se o `texto` é só um "
        "cabeçalho (`## Art. 1`, `**Art. 1º**`) ou fragmento isolado de "
        "marcação, confirma que o regex ARTICLE_RE está fragmentando "
        "cabeçalhos. Se o `texto` parece um artigo legítimo curto, a "
        "causa é outra (ex: documento real tem muitos artigos breves).\n"
    )

    for nome, bucket in buckets:
        n = len(bucket)
        lines.append(f"\n## Bucket: {nome} — {n} chunks\n")
        if n == 0:
            lines.append("_vazio_\n")
            continue
        amostra = bucket.sample(
            n=min(SAMPLE_PER_BUCKET, n), random_state=42
        )
        for i, (_, row) in enumerate(amostra.iterrows(), start=1):
            lines.append(
                f"### Amostra {i} — `{row.get('chunk_id', '')}` "
                f"({row['n_words']} palavras)\n"
            )
            lines.append(f"- `document_id`: `{row.get('document_id', '')}`")
            lines.append(f"- `artigo`: `{row.get('artigo')}`")
            lines.append(f"- `secao`: `{row.get('secao')}`")
            lines.append(f"- `paragrafo`: `{row.get('paragrafo')}`")
            texto = str(row.get("texto") or "").replace("\n", " \\n ")
            lines.append(f"- `texto`: > {texto}")
            lines.append("")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")

    # Resumo no terminal
    print()
    print("=== Distribuição por bucket ===")
    for nome, bucket in buckets:
        print(f"  {nome:30s} {len(bucket):>8d} chunks")

    print()
    print("=== Primeiras 5 amostras muito_tiny (<10 palavras) ===")
    if len(buckets[0][1]):
        for _, row in buckets[0][1].head(5).iterrows():
            texto = str(row.get("texto") or "").replace("\n", " ")[:120]
            print(f"  [{row['n_words']:>2d}w] {texto}")

    print(f"\nDetalhe completo em: {OUT_PATH}")


if __name__ == "__main__":
    main()
