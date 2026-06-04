"""Vector stores do projeto.

`store.py` (legado) — wrapper in-process usado pelo placeholder de RAG.
`faiss_store.py` + `metadata.py` + `manifest.py` + `hub.py` — vector store
persistente da Camada 2.3, publicada no HuggingFace Hub.
"""

from src.vectorstore.faiss_store import FAISSVectorStore
from src.vectorstore.store import (
    FaissVectorStore,
    InMemoryVectorStore,
    cosine_similarity,
)

__all__ = [
    "FAISSVectorStore",
    "FaissVectorStore",
    "InMemoryVectorStore",
    "cosine_similarity",
]
