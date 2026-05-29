def test_metricas_de_retrieval_deterministicas():
    from src.evaluation.metrics import mrr_at_k, precision_at_k, recall_at_k

    retrieved = ["doc-a", "doc-b", "doc-c"]
    expected = ["doc-b", "doc-d"]

    assert recall_at_k(retrieved, expected, k=3) == 0.5
    assert precision_at_k(retrieved, expected, k=3) == 1 / 3
    assert mrr_at_k(retrieved, expected, k=3) == 0.5


def test_article_hit_valida_documento_e_artigo():
    from src.evaluation.metrics import article_hit_at_k

    contexts = [
        {"document_id": "ren-2021-1000", "artigo": "Art. 1o"},
        {"document_id": "ren-2021-1000", "artigo": "Art. 2o"},
    ]

    assert article_hit_at_k(contexts, ["ren-2021-1000::Art. 2o"], k=2) == 1.0
    assert article_hit_at_k(contexts, ["ren-2021-1000::Art. 3o"], k=2) == 0.0


def test_citation_accuracy_valida_citacao_esperada():
    from src.evaluation.metrics import citation_accuracy

    citations = ["REN 1000/2021, Art. 1o", "PRODIST Modulo 8"]

    assert citation_accuracy(citations, ["Art. 1o"]) == 1.0
    assert citation_accuracy(citations, ["Art. 2o"]) == 0.0


def test_status_accuracy_detecta_norma_revogada():
    from src.evaluation.metrics import status_accuracy

    contexts = [
        {"document_id": "ren-2005-200", "situacao": "revogada"},
        {"document_id": "ren-2021-1000", "situacao": "vigente"},
    ]

    assert status_accuracy(contexts, expected_status="vigente") == 0.5


def test_metricas_llm_sao_puladas_sem_chave(monkeypatch):
    from src.evaluation.metrics import optional_llm_metrics

    monkeypatch.delenv("LLM_API_KEY", raising=False)

    resultado = optional_llm_metrics(answer="x", contexts=[], reference="y")

    assert resultado == {
        "faithfulness": None,
        "answer_correctness": None,
        "llm_status": "skipped_no_llm_key",
    }


def test_metricas_llm_executam_quando_ha_chave(monkeypatch):
    import src.evaluation.metrics as metrics

    monkeypatch.setenv("LLM_API_KEY", "fake-key")
    monkeypatch.setattr(
        metrics,
        "_run_openai_judge",
        lambda answer, contexts, reference: {
            "faithfulness": 0.8,
            "answer_correctness": 0.6,
            "llm_status": "ok",
        },
    )

    resultado = metrics.optional_llm_metrics(
        answer="resposta",
        contexts=[{"texto": "base"}],
        reference="referencia",
    )

    assert resultado == {
        "faithfulness": 0.8,
        "answer_correctness": 0.6,
        "llm_status": "ok",
    }
