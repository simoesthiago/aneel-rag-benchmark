"""GraphRAG fica fora do caminho critico do MVP."""


class GraphRAGDeferred:
    def query(self, pergunta: str, top_k: int = 5):
        raise NotImplementedError(
            "GraphRAG foi adiado para uma fase posterior. "
            "Implemente BM25, dense, hybrid e hierarchical antes."
        )
