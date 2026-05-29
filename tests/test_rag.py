def _chunk(chunk_id: str, texto: str, artigo: str | None = None) -> dict:
    return {
        "chunk_id": chunk_id,
        "document_id": chunk_id.split("::")[0],
        "texto": texto,
        "citation_label": artigo or chunk_id,
        "artigo": artigo,
        "situacao": "vigente",
    }


def test_bm25_ranqueia_match_exato_acima_de_irrelevante():
    from src.rag.retriever import BM25Retriever

    chunks = [
        _chunk("ren-2021-1000::article-aware::0000", "REN 1000 direitos do consumidor"),
        _chunk(
            "prodist-modulo-08::article-aware::0000", "qualidade do servico DEC FEC"
        ),
    ]

    retriever = BM25Retriever(chunks)
    resultados = retriever.retrieve("REN 1000 consumidor", top_k=2)

    assert resultados[0]["chunk_id"] == "ren-2021-1000::article-aware::0000"
    assert resultados[0]["score"] > resultados[1]["score"]


def test_hybrid_preserva_resultado_forte_em_um_retriever():
    from src.rag.retriever import ReciprocalRankFusionHybridRetriever

    class FakeRetriever:
        def __init__(self, ids):
            self.ids = ids

        def retrieve(self, query, top_k=5):
            return [
                _chunk(chunk_id, f"texto {idx}") | {"score": 10 - idx, "rank": idx + 1}
                for idx, chunk_id in enumerate(self.ids[:top_k])
            ]

    hybrid = ReciprocalRankFusionHybridRetriever(
        [
            FakeRetriever(["a::0", "b::0", "c::0"]),
            FakeRetriever(["b::0", "a::0", "d::0"]),
        ]
    )

    resultados = hybrid.retrieve("consulta", top_k=3)

    assert resultados[0]["chunk_id"] == "a::0"
    assert {item["chunk_id"] for item in resultados[:3]} == {"a::0", "b::0", "c::0"}
    assert resultados[0]["score"] >= resultados[1]["score"]


def test_faiss_import_lazy_com_mensagem_clara(monkeypatch):
    from src.vectorstore.store import FaissVectorStore

    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "faiss":
            raise ImportError("no faiss")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    try:
        store = FaissVectorStore(dimension=3)
        store.add([[1.0, 0.0, 0.0]], [{"chunk_id": "a"}])
    except RuntimeError as exc:
        assert "faiss-cpu" in str(exc)
    else:
        raise AssertionError("FaissVectorStore deveria exigir faiss-cpu ao usar add")


def test_base_rag_retorna_interface_comum():
    from src.rag.naive import NaiveRAG

    class FakeRetriever:
        def retrieve(self, query, top_k=5):
            return [
                _chunk(
                    "ren-2021-1000::article-aware::0000", "texto recuperado", "Art. 1o"
                )
                | {"score": 1.0, "rank": 1}
            ]

    rag = NaiveRAG(FakeRetriever(), strategy="bm25")
    resposta = rag.query("pergunta", top_k=5)

    assert set(resposta) == {
        "answer",
        "citations",
        "contexts",
        "latency_ms",
        "strategy",
    }
    assert resposta["strategy"] == "bm25"
    assert resposta["citations"] == ["Art. 1o"]
    assert resposta["latency_ms"] >= 0
