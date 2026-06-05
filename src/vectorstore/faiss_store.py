"""Wrapper FAISS para a vector store persistente da Camada 2.3.

Decisão: começamos com `IndexFlatIP` sobre vetores L2-normalizados. Sobre
vetores unitários, inner product equivale a cosine similarity — então este é
o índice mais simples, exato e auditável para servir de baseline antes de
qualquer índice aproximado (IVF, HNSW, PQ).

A classe `FAISSVectorStore` encapsula somente o índice + dimensão. Os
metadados ficam num DataFrame separado, em arquivo Parquet co-localizado.
Ordem dos vetores adicionados ↔ ordem das linhas de metadata é invariante.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:  # pragma: no cover - apenas para tipagem
    import faiss  # type: ignore

INDEX_FILENAME = "index.faiss"
DEFAULT_TOP_K = 5


def _load_faiss():
    """Importa o módulo `faiss` com mensagem amigável se faltar a dependência."""
    try:
        import faiss
    except ImportError as exc:  # pragma: no cover - falha de instalação
        raise RuntimeError(
            "faiss-cpu é necessário para a vector store FAISS. "
            "Instale as dependências com `make install` "
            "(verifique requirements.txt)."
        ) from exc
    return faiss


def _to_float32_2d(vectors: np.ndarray | list[list[float]]) -> np.ndarray:
    """Converte para `np.ndarray float32 2D contíguo` que o FAISS aceita."""
    array = np.asarray(vectors, dtype="float32")
    if array.ndim != 2:
        raise ValueError(
            f"Esperado array 2D (N, dim); recebido shape={array.shape}."
        )
    if not array.flags["C_CONTIGUOUS"]:
        array = np.ascontiguousarray(array)
    return array


def normalize(vectors: np.ndarray | list[list[float]]) -> np.ndarray:
    """Aplica `faiss.normalize_L2` em uma cópia float32 contígua."""
    array = _to_float32_2d(vectors).copy()
    faiss = _load_faiss()
    faiss.normalize_L2(array)
    return array


class FAISSVectorStore:
    """Vector store FAISS exata (IndexFlatIP) com persistência em disco."""

    def __init__(self, dimension: int):
        if dimension <= 0:
            raise ValueError(f"dimension inválida: {dimension}")
        self.dimension = int(dimension)
        self._index: "faiss.Index" | None = None

    @property
    def index(self) -> "faiss.Index":
        if self._index is None:
            raise RuntimeError(
                "FAISS index ainda não foi construído. "
                "Chame build(vectors) ou load(dir)."
            )
        return self._index

    @property
    def ntotal(self) -> int:
        return int(self.index.ntotal)

    def build(self, vectors: np.ndarray | list[list[float]]) -> "FAISSVectorStore":
        """Normaliza e indexa os vetores em um `IndexFlatIP` novo."""
        array = _to_float32_2d(vectors)
        if array.shape[1] != self.dimension:
            raise ValueError(
                "Dimensão dos vetores não bate com o índice: "
                f"esperado {self.dimension}, recebido {array.shape[1]}."
            )
        if array.shape[0] == 0:
            raise ValueError("Não é possível indexar zero vetores.")

        faiss = _load_faiss()
        normalized = array.copy()
        faiss.normalize_L2(normalized)

        index = faiss.IndexFlatIP(self.dimension)
        index.add(normalized)
        if int(index.ntotal) != array.shape[0]:
            raise RuntimeError(
                f"FAISS ntotal={index.ntotal} != esperado {array.shape[0]}."
            )
        self._index = index
        return self

    def save(self, directory: str | Path) -> Path:
        """Persiste `index.faiss` em `directory`."""
        faiss = _load_faiss()
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / INDEX_FILENAME
        faiss.write_index(self.index, str(path))
        return path

    def to_bytes(self) -> bytes:
        """Serializa o índice FAISS em memória, sem criar arquivo local."""
        faiss = _load_faiss()
        return faiss.serialize_index(self.index).tobytes()

    @classmethod
    def load(cls, directory: str | Path) -> "FAISSVectorStore":
        """Carrega `index.faiss` de `directory` e devolve a vector store."""
        faiss = _load_faiss()
        path = Path(directory) / INDEX_FILENAME
        if not path.exists():
            raise FileNotFoundError(
                f"index.faiss não encontrado em {directory}."
            )
        index = faiss.read_index(str(path))
        store = cls(dimension=int(index.d))
        store._index = index
        return store

    def search(
        self,
        query_vector: np.ndarray | list[float],
        top_k: int = DEFAULT_TOP_K,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Busca top-k. Normaliza o vetor de consulta antes do inner product.

        Retorna `(scores, indices)` ambos com shape `(1, top_k)`.
        """
        if top_k <= 0:
            raise ValueError(f"top_k deve ser > 0, recebido {top_k}")
        if top_k > self.ntotal:
            top_k = self.ntotal

        array = np.asarray(query_vector, dtype="float32")
        if array.ndim == 1:
            array = array.reshape(1, -1)
        if array.shape[1] != self.dimension:
            raise ValueError(
                "Dimensão da consulta não bate com o índice: "
                f"esperado {self.dimension}, recebido {array.shape[1]}."
            )

        faiss = _load_faiss()
        normalized = np.ascontiguousarray(array.copy())
        faiss.normalize_L2(normalized)
        scores, indices = self.index.search(normalized, top_k)
        return scores, indices
