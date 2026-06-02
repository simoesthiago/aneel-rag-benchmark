"""
uploader.py — Publicação e carregamento do corpus no HuggingFace Hub.

Por que este módulo existe?
---------------------------
Depois que os scrapers coletam os documentos, precisamos:
1. Validar o schema (delegado a schema.py)
2. Salvar como Parquet particionado por tipo + metodo_extracao
3. Fazer upload para o HuggingFace Hub

Onde roda:
    Máquina local ou qualquer ambiente com HF_TOKEN configurado

Como usar:
    from src.ingestion.uploader import carregar_corpus_hub, publicar_corpus

    df = carregar_corpus_hub()
    url = publicar_corpus(df_novos, mesclar_com_hub=True)
"""

import os
import re
import tempfile
from datetime import datetime, timezone

import pandas as pd
from huggingface_hub import HfApi

from src.config.settings import HF_DATASET_REPO, get_hf_token
from src.ingestion.schema import (
    _CHAVE_UNICA,
    _SCHEMA_COLUNAS,
    validar_schema,
)


def carregar_corpus_hub(repo_id: str | None = None) -> pd.DataFrame:
    """
    Carrega o corpus publicado no HuggingFace Hub.

    Lê os Parquets particionados e restaura as colunas `tipo` e `metodo_extracao`
    a partir dos nomes dos diretórios (particionamento Hive-style).
    """
    from huggingface_hub import hf_hub_download

    if repo_id is None:
        repo_id = HF_DATASET_REPO

    print(f"  Carregando corpus existente de {repo_id}...")
    api = HfApi()
    arquivos = api.list_repo_files(repo_id, repo_type="dataset")
    parquets = sorted(f for f in arquivos if f.endswith(".parquet"))

    if not parquets:
        raise RuntimeError(f"Nenhum Parquet encontrado em {repo_id}")

    partes: list[pd.DataFrame] = []
    for path in parquets:
        tipo_match = re.search(r"tipo=([^/]+)/", path)
        metodo_match = re.search(r"metodo_extracao=([^/]+)/", path)
        tipo = tipo_match.group(1) if tipo_match else "desconhecido"
        # Corpus legado (antes do refactor) não tem partição metodo_extracao.
        # Nesse caso inferimos "pymupdf" — todos os docs foram extraídos com PyMuPDF.
        metodo = metodo_match.group(1) if metodo_match else "pymupdf"

        local = hf_hub_download(
            repo_id=repo_id, filename=path, repo_type="dataset"
        )
        df_part = pd.read_parquet(local, engine="pyarrow")
        df_part["tipo"] = tipo
        if "metodo_extracao" not in df_part.columns:
            df_part["metodo_extracao"] = metodo
        partes.append(df_part)

    df = pd.concat(partes, ignore_index=True)
    print(f"  {len(df)} documentos no Hub")
    return df


def mesclar_corpus(df_existente: pd.DataFrame, df_novo: pd.DataFrame) -> pd.DataFrame:
    """
    Une dois DataFrames pela chave `(id, metodo_extracao)`, mantendo o registro
    mais recente em conflito (compara `scraped_at`).
    """
    if df_existente.empty:
        return df_novo.copy()
    if df_novo.empty:
        return df_existente.copy()

    for col in _SCHEMA_COLUNAS:
        if col not in df_existente.columns:
            df_existente[col] = None
        if col not in df_novo.columns:
            df_novo[col] = None

    combinado = pd.concat(
        [df_existente[_SCHEMA_COLUNAS], df_novo[_SCHEMA_COLUNAS]],
        ignore_index=True,
    )

    def _parse_ts(val: object) -> datetime:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return datetime.min.replace(tzinfo=timezone.utc)
        s = str(val).replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            return datetime.min.replace(tzinfo=timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    combinado["_ts"] = combinado["scraped_at"].map(_parse_ts)
    combinado = combinado.sort_values("_ts").drop_duplicates(
        subset=_CHAVE_UNICA, keep="last"
    )
    return combinado.drop(columns=["_ts"]).reset_index(drop=True)


def publicar_corpus(
    df: pd.DataFrame,
    repo_id: str | None = None,
    mesclar_com_hub: bool = False,
    limpar_estrutura: bool = False,
) -> str:
    """
    Salva o DataFrame como Parquet particionado e faz upload ao HF Hub.

    Particionamento: `data/documents/tipo=X/metodo_extracao=Y/part-0.parquet`.
    Queries como "todos os procedimentos extraídos com pymupdf4llm" não lêem o
    dataset inteiro.

    Args:
        df: documentos novos ou corpus completo
        repo_id: repositório no HF Hub. Default: settings.HF_DATASET_REPO
        mesclar_com_hub: se True, carrega o Hub e faz merge antes do upload
        limpar_estrutura: se True, apaga `data/` no Hub antes do upload.
            Usar apenas na migração de estrutura (ex.: adição de nova partição).
            Em uploads incrementais normais, deixar False.

    Returns:
        URL do dataset no HF Hub
    """
    if repo_id is None:
        repo_id = HF_DATASET_REPO

    if mesclar_com_hub:
        try:
            df_hub = carregar_corpus_hub(repo_id)
            df = mesclar_corpus(df_hub, df)
            print(f"  Após merge: {len(df)} documentos no total")
        except Exception as e:
            raise RuntimeError(
                f"Falha ao mesclar com corpus existente em {repo_id}: {e}"
            ) from e

    token = get_hf_token()
    api = HfApi(token=token)

    validar_schema(df)
    df = df[_SCHEMA_COLUNAS]

    with tempfile.TemporaryDirectory() as tmpdir:
        for (tipo, metodo), df_part in df.groupby(["tipo", "metodo_extracao"]):
            part_dir = os.path.join(
                tmpdir, f"data/documents/tipo={tipo}/metodo_extracao={metodo}"
            )
            os.makedirs(part_dir, exist_ok=True)
            path = os.path.join(part_dir, "part-0.parquet")
            # Remove as colunas de particionamento — inferidas do path.
            df_part.drop(columns=["tipo", "metodo_extracao"]).to_parquet(
                path, index=False, engine="pyarrow"
            )
            print(f"  📦 tipo={tipo} / metodo={metodo}: {len(df_part)} documentos")

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        commit_msg = f"Atualização do corpus: {len(df)} documentos ({timestamp})"

        print(f"\n  Fazendo upload para {repo_id}...")
        api.upload_folder(
            folder_path=tmpdir,
            repo_id=repo_id,
            repo_type="dataset",
            commit_message=commit_msg,
            delete_patterns=["data/"] if limpar_estrutura else None,
        )

    url = f"https://huggingface.co/datasets/{repo_id}"
    print(f"  ✅ Upload concluído! {url}")
    return url
