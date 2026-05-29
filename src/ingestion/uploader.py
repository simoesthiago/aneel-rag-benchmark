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
    Google Colab (precisa de HF_TOKEN para upload)

Como usar:
    from src.ingestion.uploader import validar_schema, publicar_corpus

    validar_schema(df)  # levanta RuntimeError se inválido
    url = publicar_corpus(df)
    print(f"Publicado em: {url}")
"""

import os
import tempfile

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


def publicar_corpus(df: pd.DataFrame, repo_id: str | None = None) -> str:
    """
    Salva o DataFrame como Parquet particionado e faz upload ao HF Hub.

    O Parquet é particionado por `tipo` (ato_normativo, procedimento, lei, manual)
    para que queries como "todos os procedimentos" não precisem ler o dataset inteiro.

    Args:
        df: DataFrame validado (chame validar_schema antes!)
        repo_id: nome do repositório no HF Hub. Default: settings.HF_DATASET_REPO

    Returns:
        URL do dataset no HF Hub
    """
    if repo_id is None:
        repo_id = HF_DATASET_REPO

    token = get_hf_token()
    api = HfApi(token=token)

    # Valida antes de fazer upload (proteção extra)
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

        # Upload
        from datetime import datetime, timezone

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
