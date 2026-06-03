"""Contrato compartilhado para gerar e validar chunks do corpus ANEEL."""

from __future__ import annotations

from typing import Any

import pandas as pd

CHUNK_STRATEGIES_VALIDAS = {
    "fixed-size",
    "article-aware",
    "hierarchical",
    "hierarchical-child",
}

CHUNK_SCHEMA_COLUMNS = [
    "chunk_id",
    "document_id",
    "metodo_extracao",
    "extrator",
    "parent_chunk_id",
    "chunk_strategy",
    "chunk_level",
    "chunk_index",
    "texto",
    "secao",
    "artigo",
    "paragrafo",
    "inciso",
    "alinea",
    "citation_label",
    "tipo",
    "subtipo",
    "numero",
    "ano",
    "titulo",
    "assunto",
    "situacao",
    "fonte",
    "formato_original",
    "qualidade_extracao",
    "url_original",
    "url_consolidado",
]

CHUNK_NOT_NULL_COLUMNS = [
    "chunk_id",
    "document_id",
    "metodo_extracao",
    "extrator",
    "chunk_strategy",
    "chunk_level",
    "chunk_index",
    "texto",
    "citation_label",
    "tipo",
    "titulo",
    "fonte",
    "formato_original",
    "url_original",
]

INHERITED_FIELDS = [
    "metodo_extracao",
    "extrator",
    "tipo",
    "subtipo",
    "numero",
    "ano",
    "titulo",
    "assunto",
    "situacao",
    "fonte",
    "formato_original",
    "qualidade_extracao",
    "url_original",
    "url_consolidado",
]


def document_text(document: dict[str, Any]) -> str:
    """Retorna o texto bruto de um documento no formato do schema."""
    text = document.get("texto_bruto") or document.get("texto") or ""
    return str(text).strip()


def split_text_by_words(
    text: str, *, max_words: int, overlap: int
) -> list[str]:
    """Divide texto em janelas de palavras com overlap controlado."""
    if max_words <= 0:
        raise ValueError("max_words deve ser maior que zero")
    if overlap < 0:
        raise ValueError("overlap nao pode ser negativo")
    if overlap >= max_words:
        raise ValueError("overlap deve ser menor que max_words")

    words = text.split()
    if not words:
        return []

    parts: list[str] = []
    step = max_words - overlap
    for start in range(0, len(words), step):
        window = words[start:start + max_words]
        if not window:
            break
        parts.append(" ".join(window))
        if start + max_words >= len(words):
            break
    return parts


def build_chunk(
    document: dict[str, Any],
    *,
    strategy: str,
    level: str,
    index: int,
    text: str,
    parent_chunk_id: str | None = None,
    secao: str | None = None,
    artigo: str | None = None,
    paragrafo: str | None = None,
    inciso: str | None = None,
    alinea: str | None = None,
) -> dict[str, Any]:
    """Monta um chunk com metadados herdados e campos de citacao."""
    if strategy not in CHUNK_STRATEGIES_VALIDAS:
        raise ValueError(f"chunk_strategy invalida: {strategy}")

    document_id = str(document["id"])
    metodo_extracao = document.get("metodo_extracao")
    if not metodo_extracao:
        raise RuntimeError(
            f"Documento {document_id} sem metodo_extracao; "
            "na Camada 2 o chunk_id precisa distinguir texto e markdown."
        )

    text = text.strip()
    if not text:
        raise ValueError("texto do chunk nao pode ser vazio")

    chunk_id = f"{document_id}::{metodo_extracao}::{strategy}::{index:04d}"
    chunk = {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "metodo_extracao": metodo_extracao,
        "extrator": document.get("extrator"),
        "parent_chunk_id": parent_chunk_id,
        "chunk_strategy": strategy,
        "chunk_level": level,
        "chunk_index": index,
        "texto": text,
        "secao": secao,
        "artigo": artigo,
        "paragrafo": paragrafo,
        "inciso": inciso,
        "alinea": alinea,
    }
    for field in INHERITED_FIELDS:
        chunk[field] = document.get(field)
    chunk["citation_label"] = format_citation_label(chunk)
    return chunk


def format_citation_label(chunk: dict[str, Any]) -> str:
    """Cria rotulo curto de citacao a partir de documento e estrutura legal."""
    pieces = [str(chunk.get("titulo") or chunk.get("document_id"))]
    if chunk.get("artigo"):
        pieces.append(str(chunk["artigo"]))
    if chunk.get("paragrafo"):
        pieces.append(str(chunk["paragrafo"]))
    if chunk.get("inciso"):
        pieces.append(f"inciso {chunk['inciso']}")
    if chunk.get("alinea"):
        pieces.append(f"alinea {chunk['alinea']}")
    if len(pieces) == 1 and chunk.get("chunk_index") is not None:
        pieces.append(f"chunk {chunk['chunk_index']}")
    return ", ".join(pieces)


def validar_chunks(
    df_chunks: pd.DataFrame, df_documents: pd.DataFrame
) -> None:
    """
    Valida o contrato derivado de chunks antes de publicar ou indexar.

    A Camada 2 deriva dados da Camada 1. Por isso a validacao cruza os chunks
    contra `(id, metodo_extracao)` do corpus original, em vez de confiar apenas
    no formato do `chunk_id`.
    """
    _validar_colunas_chunks(df_chunks)
    _validar_colunas_documentos(df_documents)

    duplicados = df_chunks[
        df_chunks.duplicated(subset=["chunk_id"], keep=False)
    ]
    if len(duplicados) > 0:
        ids = duplicados["chunk_id"].drop_duplicates().tolist()[:10]
        raise RuntimeError(f"chunk_id duplicado: {ids}")

    textos_vazios = (
        df_chunks["texto"].fillna("").astype(str).str.strip().eq("")
    )
    if textos_vazios.any():
        ids = df_chunks.loc[textos_vazios, "chunk_id"].tolist()[:10]
        raise RuntimeError(f"Chunks com texto vazio: {ids}")

    estrategias_invalidas = (
        set(df_chunks["chunk_strategy"].dropna().astype(str).unique())
        - CHUNK_STRATEGIES_VALIDAS
    )
    if estrategias_invalidas:
        raise RuntimeError(
            "chunk_strategy com valores invalidos: "
            f"{sorted(estrategias_invalidas)}"
        )

    _validar_fks_documentos(df_chunks, df_documents)
    _validar_hierarquia(df_chunks)


def _validar_colunas_chunks(df_chunks: pd.DataFrame) -> None:
    colunas_faltando = set(CHUNK_SCHEMA_COLUMNS) - set(df_chunks.columns)
    if colunas_faltando:
        raise RuntimeError(
            f"Colunas faltando em chunks: {sorted(colunas_faltando)}"
        )

    for col in CHUNK_NOT_NULL_COLUMNS:
        nulos = df_chunks[col].isna()
        if nulos.any():
            ids = df_chunks.loc[nulos, "chunk_id"].tolist()[:10]
            raise RuntimeError(
                f"Coluna obrigatoria '{col}' tem nulos: {ids}"
            )


def _validar_colunas_documentos(df_documents: pd.DataFrame) -> None:
    colunas_faltando = {"id", "metodo_extracao"} - set(df_documents.columns)
    if colunas_faltando:
        raise RuntimeError(
            "Corpus original sem colunas para FK de chunks: "
            f"{sorted(colunas_faltando)}"
        )


def _validar_fks_documentos(
    df_chunks: pd.DataFrame, df_documents: pd.DataFrame
) -> None:
    docs_validos = set(
        zip(
            df_documents["id"].astype(str),
            df_documents["metodo_extracao"].astype(str),
        )
    )
    pares_chunks = set(
        zip(
            df_chunks["document_id"].astype(str),
            df_chunks["metodo_extracao"].astype(str),
        )
    )
    pares_invalidos = sorted(pares_chunks - docs_validos)
    if pares_invalidos:
        raise RuntimeError(
            "Chunks referenciam documentos inexistentes: "
            f"{pares_invalidos[:10]}"
        )


def _validar_hierarquia(df_chunks: pd.DataFrame) -> None:
    by_id = df_chunks.set_index("chunk_id")["chunk_strategy"].to_dict()
    parent_series = df_chunks["parent_chunk_id"]
    tem_parent = (
        parent_series.notna()
        & parent_series.astype(str).str.strip().ne("")
    )
    pais_inexistentes = sorted(
        set(parent_series[tem_parent].astype(str)) - set(by_id)
    )
    if pais_inexistentes:
        raise RuntimeError(
            f"parent_chunk_id inexistente: {pais_inexistentes[:10]}"
        )

    filhos = df_chunks[df_chunks["chunk_strategy"] == "hierarchical-child"]
    filhos_sem_parent = filhos[
        filhos["parent_chunk_id"].isna()
        | filhos["parent_chunk_id"].astype(str).str.strip().eq("")
    ]
    if len(filhos_sem_parent) > 0:
        ids = filhos_sem_parent["chunk_id"].tolist()[:10]
        raise RuntimeError(f"hierarchical-child sem parent_chunk_id: {ids}")

    pais_invalidos = []
    for _, child in filhos.iterrows():
        parent_id = str(child["parent_chunk_id"])
        if by_id.get(parent_id) != "hierarchical":
            pais_invalidos.append((child["chunk_id"], parent_id))
    if pais_invalidos:
        raise RuntimeError(
            "hierarchical-child aponta para pai nao-hierarchical: "
            f"{pais_invalidos[:10]}"
        )
