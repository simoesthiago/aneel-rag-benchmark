"""Interface comum para estrategias RAG."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

RagResponse = dict[str, Any]


class BaseRAG(ABC):
    """Contrato minimo: query(pergunta) -> resposta estruturada."""

    strategy: str

    @abstractmethod
    def query(self, pergunta: str, top_k: int = 5) -> RagResponse:
        raise NotImplementedError
