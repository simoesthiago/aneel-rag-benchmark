"""
uploader.py — Validação e publicação do corpus no HuggingFace Hub.

Por que este módulo existe?
---------------------------
Depois que os scrapers coletam os documentos, precisamos:
1. Validar que o DataFrame segue o schema (docs/schema.md)
2. Salvar como Parquet particionado por tipo
3. Fazer upload para o HuggingFace Hub

Esse módulo garante que dados malformados nunca cheguem ao Hub — falha cedo
com mensagem clara se alguma coluna estiver faltando ou se houver IDs duplicados.

Onde roda:
    Máquina local ou qualquer ambiente com HF_TOKEN configurado

Como usar:
    from src.ingestion.uploader import validar_schema, publicar_corpus

    validar_schema(df)  # levanta RuntimeError se inválido
    url = publicar_corpus(df)
    print(f"Publicado em: {url}")
"""

import os
import tempfile
from datetime import datetime, timezone

import pandas as pd
from huggingface_hub import HfApi

from src.config.settings import HF_DATASET_REPO, get_hf_token

# Colunas obrigatórias do schema (ver docs/schema.md)
_SCHEMA_COLUNAS = [
    "id",
    "tipo",
    "subtipo",
    "numero",
    "ano",
    "titulo",
    "assunto",
    "situacao",
    "data_publicacao",
    "fonte",
    "url_original",
    "url_consolidado",
    "formato_original",
    "texto_bruto",
    "num_paginas",
    "metodo_extracao",
    "qualidade_extracao",
    "hf_path",
    "scraped_at",
]

# Colunas que NUNCA devem ser nulas
_COLUNAS_NOT_NULL = [
    "id",
    "tipo",
    "titulo",
    "fonte",
    "url_original",
    "formato_original",
    "texto_bruto",
    "metodo_extracao",
    "scraped_at",
]


def validar_schema(df: pd.DataFrame) -> None:
    """
    Valida que o DataFrame segue o schema do corpus.

    Verifica:
    1. Todas as colunas obrigatórias estão presentes
    2. Nenhuma coluna NOT NULL contém nulos
    3. Não há IDs duplicados
    4. texto_bruto não está vazio em nenhum documento

    Args:
        df: DataFrame com os documentos

    Raises:
        RuntimeError: se alguma validação falhar (mensagem explica o problema)
    """
    # 1. Colunas presentes
    colunas_faltando = set(_SCHEMA_COLUNAS) - set(df.columns)
    if colunas_faltando:
        raise RuntimeError(
            f"Colunas faltando no DataFrame: {colunas_faltando}. "
            f"O schema exige: {_SCHEMA_COLUNAS}"
        )

    # 2. Colunas NOT NULL
    for col in _COLUNAS_NOT_NULL:
        nulos = df[df[col].isna()]
        if len(nulos) > 0:
            ids_nulos = nulos["id"].tolist()[:5]
            raise RuntimeError(
                f"Coluna obrigatória '{col}' tem {len(nulos)} valores nulos. "
                f"IDs afetados (primeiros 5): {ids_nulos}"
            )

    # 3. IDs únicos
    duplicados = df[df["id"].duplicated(keep=False)]
    if len(duplicados) > 0:
        ids_dup = duplicados["id"].unique().tolist()
        raise RuntimeError(
            f"IDs duplicados encontrados: {ids_dup}. "
            f"Cada documento precisa ter um ID único."
        )

    # 4. texto_bruto não vazio
    vazios = df[df["texto_bruto"].str.len() < 100]
    if len(vazios) > 0:
        ids_vazios = vazios["id"].tolist()
        raise RuntimeError(
            f"{len(vazios)} documentos com texto_bruto < 100 chars: {ids_vazios}. "
            f"Extração de texto provavelmente falhou."
        )


def carregar_corpus_hub(repo_id: str | None = None) -> pd.DataFrame:
    """
    Carrega o corpus já publicado no HuggingFace Hub.

    Lê os Parquets particionados (`tipo=.../part-0.parquet`) e restaura a coluna
    `tipo`, removida no upload para o particionamento Hive.
    """
    import re

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
        match = re.search(r"tipo=([^/]+)/", path)
        tipo = match.group(1) if match else "desconhecido"
        local = hf_hub_download(
            repo_id=repo_id, filename=path, repo_type="dataset"
        )
        df_part = pd.read_parquet(local, engine="pyarrow")
        df_part["tipo"] = tipo
        partes.append(df_part)

    df = pd.concat(partes, ignore_index=True)
    print(f"  {len(df)} documentos no Hub")
    return df


def mesclar_corpus(df_existente: pd.DataFrame, df_novo: pd.DataFrame) -> pd.DataFrame:
    """
    Une dois DataFrames pelo `id`, mantendo o registro mais recente em conflito.

    Compara `scraped_at` (ISO 8601). Se ausente, o registro novo prevalece.
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

    combinado = pd.concat([df_existente[_SCHEMA_COLUNAS], df_novo[_SCHEMA_COLUNAS]], ignore_index=True)

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
    combinado = combinado.sort_values("_ts").drop_duplicates(subset=["id"], keep="last")
    combinado = combinado.drop(columns=["_ts"])
    return combinado.reset_index(drop=True)


def publicar_corpus(
    df: pd.DataFrame,
    repo_id: str | None = None,
    mesclar_com_hub: bool = False,
) -> str:
    """
    Salva o DataFrame como Parquet particionado e faz upload ao HF Hub.

    O Parquet é particionado por `tipo` (ato_normativo, procedimento, lei, manual)
    para que queries como "todos os procedimentos" não precisem ler o dataset inteiro.

    Args:
        df: DataFrame com documentos novos ou corpus completo
        repo_id: nome do repositório no HF Hub. Default: settings.HF_DATASET_REPO
        mesclar_com_hub: se True, carrega o Hub e faz merge por `id` antes do upload

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

    # Reordena colunas conforme schema
    df = df[_SCHEMA_COLUNAS]

    with tempfile.TemporaryDirectory() as tmpdir:
        # Salvar um Parquet por tipo (particionamento manual)
        # O Hive-style partitioning espera: data/documents/tipo=X/part-0.parquet
        for tipo in df["tipo"].unique():
            df_tipo = df[df["tipo"] == tipo]
            part_dir = os.path.join(tmpdir, f"data/documents/tipo={tipo}")
            os.makedirs(part_dir, exist_ok=True)
            path = os.path.join(part_dir, "part-0.parquet")
            # Remove a coluna "tipo" do Parquet — ela é inferida do particionamento
            df_tipo.drop(columns=["tipo"]).to_parquet(
                path, index=False, engine="pyarrow"
            )
            print(f"  📦 tipo={tipo}: {len(df_tipo)} documentos")

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        commit_msg = f"Atualização do corpus: {len(df)} documentos ({timestamp})"

        print(f"\n  Fazendo upload para {repo_id}...")
        api.upload_folder(
            folder_path=tmpdir,
            repo_id=repo_id,
            repo_type="dataset",
            commit_message=commit_msg,
        )

    url = f"https://huggingface.co/datasets/{repo_id}"
    print(f"  ✅ Upload concluído! {url}")
    return url
