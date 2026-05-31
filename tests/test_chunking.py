import pytest


def _documento(texto: str) -> dict:
    return {
        "id": "ren-2021-1000",
        "tipo": "ato_normativo",
        "subtipo": "ren",
        "numero": "1000",
        "ano": 2021,
        "titulo": "REN 1000/2021",
        "situacao": "vigente",
        "url_original": "https://www2.aneel.gov.br/cedoc/ren20211000.pdf",
        "url_consolidado": "https://www2.aneel.gov.br/cedoc/bren20211000.pdf",
        "texto_bruto": texto,
    }


def test_fixed_size_preserva_ordem_e_ids_estaveis():
    from src.chunking.fixed_size import chunk_fixed_size

    doc = _documento("um dois tres quatro cinco seis sete oito nove dez")

    chunks = chunk_fixed_size(doc, chunk_size=4, overlap=1)

    assert [chunk["chunk_id"] for chunk in chunks] == [
        "ren-2021-1000::fixed-size::0000",
        "ren-2021-1000::fixed-size::0001",
        "ren-2021-1000::fixed-size::0002",
    ]
    assert [chunk["texto"] for chunk in chunks] == [
        "um dois tres quatro",
        "quatro cinco seis sete",
        "sete oito nove dez",
    ]
    assert chunks[0]["document_id"] == "ren-2021-1000"
    assert chunks[0]["chunk_strategy"] == "fixed-size"
    assert chunks[0]["situacao"] == "vigente"


def test_fixed_size_rejeita_overlap_maior_ou_igual_chunk_size():
    from src.chunking.fixed_size import chunk_fixed_size

    with pytest.raises(ValueError, match="overlap"):
        chunk_fixed_size(_documento("um dois tres"), chunk_size=2, overlap=2)


def test_article_aware_identifica_artigo_paragrafo_inciso_e_citacao():
    from src.chunking.article_aware import chunk_article_aware

    doc = _documento(
        "CAPITULO I\n"
        "Art. 1o Esta Resolucao estabelece regras gerais.\n"
        "§ 1o A distribuidora deve atender o consumidor.\n"
        "I - o atendimento deve observar prazos.\n"
        "Art. 2o A ANEEL fiscalizara o cumprimento."
    )

    chunks = chunk_article_aware(doc)

    assert len(chunks) == 2
    assert chunks[0]["chunk_id"] == "ren-2021-1000::article-aware::0000"
    assert chunks[0]["artigo"] == "Art. 1o"
    assert chunks[0]["paragrafo"] == "§ 1o"
    assert chunks[0]["inciso"] == "I"
    assert chunks[0]["citation_label"] == "REN 1000/2021, Art. 1o, § 1o, inciso I"
    assert chunks[1]["artigo"] == "Art. 2o"


def test_article_aware_usa_fallback_por_paragrafo_quando_nao_ha_artigos():
    from src.chunking.article_aware import chunk_article_aware

    doc = _documento("Primeiro bloco sem artigo.\n\nSegundo bloco sem artigo.")

    chunks = chunk_article_aware(doc)

    assert len(chunks) == 2
    assert chunks[0]["chunk_level"] == "paragraph"
    assert chunks[0]["artigo"] is None
    assert chunks[0]["texto"] == "Primeiro bloco sem artigo."
