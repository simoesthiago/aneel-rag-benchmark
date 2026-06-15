import pandas as pd
import pytest


def _documento(
    texto: str,
    *,
    id: str = "ren-2021-1000",
    metodo_extracao: str = "markdown",
) -> dict:
    return {
        "id": id,
        "tipo": "ato_normativo",
        "subtipo": "ren",
        "numero": "1000",
        "ano": 2021,
        "titulo": "REN 1000/2021",
        "assunto": "Direitos do consumidor",
        "situacao": "vigente",
        "fonte": "cedoc",
        "url_original": "https://www2.aneel.gov.br/cedoc/ren20211000.pdf",
        "url_consolidado": "https://www2.aneel.gov.br/cedoc/bren20211000.pdf",
        "formato_original": "pdf",
        "texto_bruto": texto,
        "metodo_extracao": metodo_extracao,
        "extrator": "pymupdf4llm",
        "qualidade_extracao": 1.0,
    }


def _documents_df(*documents: dict) -> pd.DataFrame:
    return pd.DataFrame(documents)


def test_fixed_size_preserva_ordem_overlap_e_ids_com_metodo_extracao():
    from src.chunking.fixed_size import chunk_fixed_size

    doc = _documento("um dois tres quatro cinco seis sete oito nove dez")

    chunks = chunk_fixed_size(doc, chunk_size=4, overlap=1)

    assert [chunk["chunk_id"] for chunk in chunks] == [
        "ren-2021-1000::markdown::fixed-size::0000",
        "ren-2021-1000::markdown::fixed-size::0001",
        "ren-2021-1000::markdown::fixed-size::0002",
    ]
    assert [chunk["texto"] for chunk in chunks] == [
        "um dois tres quatro",
        "quatro cinco seis sete",
        "sete oito nove dez",
    ]
    assert chunks[0]["document_id"] == "ren-2021-1000"
    assert chunks[0]["metodo_extracao"] == "markdown"
    assert chunks[0]["extrator"] == "pymupdf4llm"
    assert chunks[0]["chunk_strategy"] == "fixed-size"
    assert chunks[0]["situacao"] == "vigente"


def test_fixed_size_rejeita_overlap_maior_ou_igual_chunk_size():
    from src.chunking.fixed_size import chunk_fixed_size

    with pytest.raises(ValueError, match="overlap"):
        chunk_fixed_size(_documento("um dois tres"), chunk_size=2, overlap=2)


def test_article_aware_identifica_estrutura_normativa_e_citacao():
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
    assert chunks[0]["chunk_id"] == (
        "ren-2021-1000::markdown::article-aware::0000"
    )
    assert chunks[0]["secao"] == "CAPITULO I"
    assert chunks[0]["artigo"] == "Art. 1o"
    assert chunks[0]["paragrafo"] == "§ 1o"
    assert chunks[0]["inciso"] == "I"
    assert chunks[0]["citation_label"] == (
        "REN 1000/2021, Art. 1o, § 1o, inciso I"
    )
    assert chunks[1]["artigo"] == "Art. 2o"


def test_article_aware_nao_fragmenta_referencia_cruzada_no_meio_do_texto():
    from src.chunking.article_aware import chunk_article_aware

    doc = _documento(
        "Art. 1o A Resolucao estabelece regras gerais e altera o "
        "art. 5o da Resolucao Normativa no 547, de 2013.\n"
        "Art. 2o A ANEEL fiscalizara o cumprimento."
    )

    chunks = chunk_article_aware(doc)

    assert len(chunks) == 2
    assert chunks[0]["artigo"] == "Art. 1o"
    assert "art. 5o da Resolucao" in chunks[0]["texto"]
    assert chunks[1]["artigo"] == "Art. 2o"


def test_article_aware_aceita_cabecalho_markdown_de_artigo():
    from src.chunking.article_aware import chunk_article_aware

    doc = _documento(
        "## **Art. 1o**\n"
        "Esta Resolucao estabelece regras gerais.\n"
        "## **Art. 2o**\n"
        "A ANEEL fiscalizara o cumprimento."
    )

    chunks = chunk_article_aware(doc)

    assert len(chunks) == 2
    assert chunks[0]["artigo"] == "Art. 1o"
    assert chunks[1]["artigo"] == "Art. 2o"


def test_article_aware_usa_fallback_por_paragrafo_quando_nao_ha_artigos():
    from src.chunking.article_aware import chunk_article_aware

    doc = _documento("Primeiro bloco sem artigo.\n\nSegundo bloco sem artigo.")

    chunks = chunk_article_aware(doc)

    assert len(chunks) == 2
    assert chunks[0]["chunk_level"] == "paragraph"
    assert chunks[0]["artigo"] is None
    assert chunks[0]["texto"] == "Primeiro bloco sem artigo."


def test_article_aware_quebra_bloco_estrutural_muito_longo():
    from src.chunking.article_aware import chunk_article_aware

    texto_longo = " ".join(f"palavra{i}" for i in range(900))
    doc = _documento(f"Art. 1o {texto_longo}")

    chunks = chunk_article_aware(doc)

    assert len(chunks) == 2
    assert all(chunk["artigo"] == "Art. 1o" for chunk in chunks)
    assert all(len(chunk["texto"].split()) <= 800 for chunk in chunks)


def test_hierarchical_herda_parser_que_nao_fragmenta_referencia_cruzada():
    from src.chunking.hierarchical import chunk_parent_child

    doc = _documento(
        "Art. 1o A Resolucao estabelece regras gerais e altera o "
        "art. 5o da Resolucao Normativa no 547, de 2013.\n"
        "Art. 2o A ANEEL fiscalizara o cumprimento."
    )

    chunks = chunk_parent_child(doc, child_size=40, overlap=5)
    parents = [
        chunk for chunk in chunks if chunk["chunk_strategy"] == "hierarchical"
    ]

    assert len(parents) == 2
    assert "art. 5o da Resolucao" in parents[0]["texto"]
    assert parents[1]["artigo"] == "Art. 2o"


def test_hierarchical_cria_pais_e_filhos_com_parent_chunk_id_real():
    from src.chunking.hierarchical import chunk_parent_child

    doc = _documento(
        "Art. 1o um dois tres quatro cinco seis sete oito nove dez.\n"
        "§ 1o onze doze treze quatorze quinze."
    )

    chunks = chunk_parent_child(doc, child_size=5, overlap=1)
    parents = [
        chunk for chunk in chunks if chunk["chunk_strategy"] == "hierarchical"
    ]
    children = [
        chunk
        for chunk in chunks
        if chunk["chunk_strategy"] == "hierarchical-child"
    ]
    parent_ids = {parent["chunk_id"] for parent in parents}

    assert len(parents) == 1
    assert len(children) > 1
    assert all(child["parent_chunk_id"] in parent_ids for child in children)
    assert parents[0]["chunk_id"] == (
        "ren-2021-1000::markdown::hierarchical::0000"
    )
    assert children[0]["chunk_id"] == (
        "ren-2021-1000::markdown::hierarchical-child::0000"
    )


def test_validar_chunks_aceita_chunks_validos():
    from src.chunking.common import validar_chunks
    from src.chunking.fixed_size import chunk_fixed_size

    doc = _documento("um dois tres quatro cinco seis")
    chunks = pd.DataFrame(chunk_fixed_size(doc, chunk_size=3, overlap=1))

    validar_chunks(chunks, _documents_df(doc))


def test_validar_chunks_rejeita_chunk_id_duplicado():
    from src.chunking.common import validar_chunks
    from src.chunking.fixed_size import chunk_fixed_size

    doc = _documento("um dois tres quatro cinco seis")
    chunks = pd.DataFrame(chunk_fixed_size(doc, chunk_size=3, overlap=1))
    chunks = pd.concat([chunks, chunks.iloc[[0]]], ignore_index=True)

    with pytest.raises(RuntimeError, match="chunk_id duplicado"):
        validar_chunks(chunks, _documents_df(doc))


def test_validar_chunks_rejeita_texto_vazio():
    from src.chunking.common import validar_chunks
    from src.chunking.fixed_size import chunk_fixed_size

    doc = _documento("um dois tres quatro cinco seis")
    chunks = pd.DataFrame(chunk_fixed_size(doc, chunk_size=3, overlap=1))
    chunks.loc[0, "texto"] = ""

    with pytest.raises(RuntimeError, match="texto vazio"):
        validar_chunks(chunks, _documents_df(doc))


def test_validar_chunks_rejeita_documento_inexistente():
    from src.chunking.common import validar_chunks
    from src.chunking.fixed_size import chunk_fixed_size

    doc = _documento("um dois tres quatro cinco seis")
    chunks = pd.DataFrame(chunk_fixed_size(doc, chunk_size=3, overlap=1))
    chunks.loc[0, "document_id"] = "ren-1999-0001"

    with pytest.raises(RuntimeError, match="documentos inexistentes"):
        validar_chunks(chunks, _documents_df(doc))


def test_validar_chunks_rejeita_parent_chunk_id_inexistente():
    from src.chunking.common import validar_chunks
    from src.chunking.hierarchical import chunk_parent_child

    doc = _documento("Art. 1o um dois tres quatro cinco seis sete oito.")
    chunks = pd.DataFrame(chunk_parent_child(doc, child_size=4, overlap=1))
    child_index = chunks[
        chunks["chunk_strategy"] == "hierarchical-child"
    ].index[0]
    chunks.loc[child_index, "parent_chunk_id"] = "chunk-inexistente"

    with pytest.raises(RuntimeError, match="parent_chunk_id inexistente"):
        validar_chunks(chunks, _documents_df(doc))
