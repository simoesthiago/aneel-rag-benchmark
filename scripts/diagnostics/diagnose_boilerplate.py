"""A.5 - Boilerplate normativo inflacionando similaridade.

Hipótese H10: documentos da ANEEL compartilham boilerplate ("A Diretora...,
no uso..., considerando que..., resolve:") que infla similaridade coseno
entre embeddings de RENs diferentes, dificultando o retrieval distinguir.

Procedimento: pega 5 atos normativos aleatórios do corpus, extrai as
primeiras 200 palavras (zona de boilerplate), embedda com
text-embedding-3-large e calcula matriz de similaridade pairwise.

Critério: se média da similaridade off-diagonal > 0.85, hipótese confirmada.
0.70-0.85: parcial. <0.70: refutada.

Saída: data/evaluation/results/diagnostic/boilerplate_similarity.md

NOTA: usa `huggingface_hub.hf_hub_download`, que materializa em
~/.cache/huggingface/hub/. Exceção explícita à regra Hub-first do projeto
— vale apenas para diagnóstico pontual. Ver Troubleshooting no README.md.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from huggingface_hub import HfApi, hf_hub_download  # noqa: E402

from src.config.settings import HF_DATASET_REPO  # noqa: E402
from src.embeddings.embedder import OpenAIEmbeddingProvider  # noqa: E402

N_DOCS = 5
N_WORDS = 200
TIPO_ALVO = "ato_normativo"  # RENs e similares
SEED = 42

OUT_PATH = Path(
    "data/evaluation/results/diagnostic/boilerplate_similarity.md"
)


def load_atos_normativos() -> pd.DataFrame:
    api = HfApi()
    arquivos = api.list_repo_files(HF_DATASET_REPO, repo_type="dataset")
    parquets = sorted(
        p
        for p in arquivos
        if p.startswith(f"data/documents/tipo={TIPO_ALVO}/")
        and p.endswith(".parquet")
        and "metodo_extracao=texto" in p  # extração texto puro
    )
    if not parquets:
        raise RuntimeError(
            f"Nenhum parquet de tipo={TIPO_ALVO} encontrado."
        )
    partes = []
    for path in parquets:
        local = hf_hub_download(
            repo_id=HF_DATASET_REPO, filename=path, repo_type="dataset"
        )
        partes.append(pd.read_parquet(local, engine="pyarrow"))
    return pd.concat(partes, ignore_index=True)


def cosine_matrix(vecs: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    normed = vecs / np.clip(norms, 1e-12, None)
    return normed @ normed.T


def main() -> None:
    random.seed(SEED)
    print("Carregando atos normativos do Hub ...", file=sys.stderr)
    df = load_atos_normativos()
    print(f"  {len(df)} docs em tipo={TIPO_ALVO}.", file=sys.stderr)

    rens = df[
        df["titulo"].astype(str).str.contains("Resolução", case=False, na=False)
        | df["subtipo"].astype(str).str.contains("ren", case=False, na=False)
    ].reset_index(drop=True)
    print(f"  {len(rens)} parecem ser RENs.", file=sys.stderr)

    if len(rens) < N_DOCS:
        rens = df  # fallback: usar qualquer ato

    sample = rens.sample(n=N_DOCS, random_state=SEED).reset_index(drop=True)
    boilerplates = []
    for _, row in sample.iterrows():
        texto = str(row.get("texto_bruto") or "")
        words = texto.split()
        boilerplate = " ".join(words[:N_WORDS])
        boilerplates.append(boilerplate)

    print(
        f"Embedando {len(boilerplates)} amostras "
        "(text-embedding-3-large) ...",
        file=sys.stderr,
    )
    embedder = OpenAIEmbeddingProvider(model_name="text-embedding-3-large")
    vecs = np.array(embedder.embed_documents(boilerplates))

    sim = cosine_matrix(vecs)
    n = sim.shape[0]
    off_diag = [sim[i, j] for i in range(n) for j in range(n) if i != j]
    mean_off = float(np.mean(off_diag))
    max_off = float(np.max(off_diag))

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    ids = [str(row["id"]) for _, row in sample.iterrows()]
    titulos = [
        str(row.get("titulo") or "")[:60] for _, row in sample.iterrows()
    ]

    lines: list[str] = []
    lines.append("# Boilerplate × Similaridade — H10\n")
    lines.append(
        f"Amostra: {N_DOCS} atos normativos × primeiras {N_WORDS} palavras"
        f" — text-embedding-3-large\n"
    )
    lines.append("## Documentos\n")
    lines.append("| # | document_id | titulo (60 ch) |")
    lines.append("|---|---|---|")
    for i, (doc_id, titulo) in enumerate(zip(ids, titulos)):
        lines.append(f"| {i} | {doc_id} | {titulo} |")

    lines.append("\n## Matriz de similaridade coseno\n")
    header = "|     | " + " | ".join(f"#{i}" for i in range(n)) + " |"
    sep = "|---|" + "---|" * n
    lines.append(header)
    lines.append(sep)
    for i in range(n):
        cells = " | ".join(f"{sim[i, j]:.3f}" for j in range(n))
        lines.append(f"| #{i} | {cells} |")

    lines.append("")
    lines.append(
        f"**Off-diagonal:** média = {mean_off:.3f}, máximo = {max_off:.3f}"
    )
    if mean_off > 0.85:
        ver = "CONFIRMADA"
    elif mean_off > 0.70:
        ver = "PARCIAL"
    else:
        ver = "REFUTADA"
    lines.append(f"\n**Veredito H10:** {ver}")

    OUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n=== Matriz de similaridade ===")
    for i in range(n):
        print(
            " ".join(f"{sim[i, j]:6.3f}" for j in range(n)),
            "  #",
            ids[i],
        )
    print(f"\nOff-diag média: {mean_off:.3f} | máx: {max_off:.3f}")
    print(f"Veredito H10: {ver}")
    print(f"\nTabela salva em: {OUT_PATH}")


if __name__ == "__main__":
    main()
