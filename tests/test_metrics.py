def test_metricas_de_retrieval_deterministicas():
    from src.evaluation.metrics import mrr_at_k, precision_at_k, recall_at_k

    retrieved = ["doc-a", "doc-b", "doc-c"]
    expected = ["doc-b", "doc-d"]

    assert recall_at_k(retrieved, expected, k=3) == 0.5
    assert precision_at_k(retrieved, expected, k=3) == 1 / 3
    assert mrr_at_k(retrieved, expected, k=3) == 0.5


def test_ndcg_at_k_ranking_perfeito_eh_um():
    from src.evaluation.metrics import ndcg_at_k

    assert ndcg_at_k([3, 2, 1, 0], k=4) == 1.0


def test_ndcg_at_k_ranking_invertido_eh_menor_que_perfeito():
    from src.evaluation.metrics import ndcg_at_k

    perfeito = ndcg_at_k([3, 2, 1], k=3)
    invertido = ndcg_at_k([1, 2, 3], k=3)
    assert perfeito == 1.0
    assert 0.0 < invertido < perfeito


def test_ndcg_at_k_sem_relevantes_devolve_zero():
    from src.evaluation.metrics import ndcg_at_k

    assert ndcg_at_k([0, 0, 0, 0], k=4) == 0.0


def test_ndcg_at_k_respeita_corte_em_k():
    from src.evaluation.metrics import ndcg_at_k

    # Truncar em k=2 ignora o item relevante na posição 3.
    assert ndcg_at_k([3, 3, 0], k=2) == 1.0
    assert ndcg_at_k([0, 0, 3], k=2) == 0.0


def test_doc_recall_at_k_ignora_section_label():
    from src.evaluation.metrics import doc_recall_at_k

    # Chunks de 2 docs distintos: a métrica não olha artigo/seção,
    # só `document_id`.
    contexts = [
        {"document_id": "ren-2021-1000", "artigo": "Art. 1o"},
        {"document_id": "ren-2021-1000", "artigo": "Art. 99o"},
        {"document_id": "outro-doc", "artigo": "Art. 1o"},
    ]
    expected = ["ren-2021-1000", "doc-ausente"]

    # ren-2021-1000 está no top-3, doc-ausente não — recall = 1/2.
    assert doc_recall_at_k(contexts, expected, k=3) == 0.5
    # Sem documentos esperados, retorno = 0.0 (consistente com recall_at_k).
    assert doc_recall_at_k(contexts, [], k=3) == 0.0
    # Corte por k: se k=1, só pega o primeiro chunk, ainda cobre o doc.
    assert doc_recall_at_k(contexts, ["ren-2021-1000"], k=1) == 1.0
    # k=1 e doc esperado é o último chunk → recall = 0.
    assert doc_recall_at_k(contexts, ["outro-doc"], k=1) == 0.0


def test_doc_recall_at_k_any_of_credita_grupo_alternativo():
    from src.evaluation.metrics import doc_recall_at_k

    contexts = [
        {"document_id": "ren-2023-1059", "artigo": "Art. 1o"},
    ]
    # Grupo any_of {REN 1000, REN 1059}: só REN 1059 recuperado.
    grupos = [["ren-2021-1000", "ren-2023-1059"]]
    # any_of -> grupo coberto -> recall 1.0 (não 0.5 como na semântica AND).
    assert doc_recall_at_k(contexts, [], k=3, groups=grupos) == 1.0
    # Sem `groups`, os 2 docs são obrigatórios e só 1 foi coberto -> 0.5.
    assert (
        doc_recall_at_k(contexts, ["ren-2021-1000", "ren-2023-1059"], k=3) == 0.5
    )
    # Dois grupos, só um coberto -> 0.5 (AND entre grupos).
    grupos_2 = [["ren-2021-1000", "ren-2023-1059"], ["doc-ausente"]]
    assert doc_recall_at_k(contexts, [], k=3, groups=grupos_2) == 0.5


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


def test_evaluate_response_nomeia_metricas_com_k_informado(monkeypatch):
    from src.evaluation.metrics import evaluate_response

    monkeypatch.delenv("LLM_API_KEY", raising=False)

    resultado = evaluate_response(
        {
            "contexts": [{"document_id": "doc-a", "artigo": "Art. 1o"}],
            "citations": ["Art. 1o"],
            "latency_ms": 12.0,
        },
        {
            "expected_document_ids": ["doc-a"],
            "expected_article_refs": ["doc-a::Art. 1o"],
        },
        k=10,
    )

    assert "recall@10" in resultado
    assert "precision@10" in resultado
    assert "mrr@10" in resultado
    assert "article_hit@10" in resultado
    assert "recall@5" not in resultado
