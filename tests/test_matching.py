"""Testes do matching entre chunks recuperados e fontes do ground truth."""

from __future__ import annotations

from src.evaluation.matching import (
    build_relevance_vector,
    is_relevant,
    section_signature_from_chunk,
    section_signature_from_label,
)


def _chunk(
    *,
    document_id: str,
    texto: str = "",
    artigo: str | None = None,
    paragrafo: str | None = None,
    inciso: str | None = None,
    alinea: str | None = None,
) -> dict:
    return {
        "document_id": document_id,
        "texto": texto,
        "artigo": artigo,
        "paragrafo": paragrafo,
        "inciso": inciso,
        "alinea": alinea,
    }


def _source(
    *,
    document_id: str,
    section_label: str = "",
    relevance: int = 3,
    support_excerpt: str = "",
) -> dict:
    return {
        "document_id": document_id,
        "section_label": section_label,
        "relevance": relevance,
        "support_excerpt": support_excerpt,
    }


def test_section_signature_from_chunk_reduz_a_tokens_canonicos():
    chunk = _chunk(
        document_id="x",
        artigo="Art. 1º",
        paragrafo="§1º",
        inciso="II",
        alinea="a",
    )
    assert section_signature_from_chunk(chunk) == "art1.par1.incii.alia"


def test_section_signature_from_label_parsea_formato_humano():
    assert (
        section_signature_from_label("Art. 1º, §1º, inciso II, alínea a")
        == "art1.par1.incii.alia"
    )
    assert section_signature_from_label("Art. 5º") == "art5"
    assert section_signature_from_label("") == ""


def test_is_relevant_doc_e_secao_exatos_devolvem_relevance_da_fonte():
    chunk = _chunk(
        document_id="ren-2021-1000",
        artigo="Art. 1º",
        paragrafo="§1º",
    )
    fontes = [
        _source(
            document_id="ren-2021-1000",
            section_label="Art. 1º, §1º",
            relevance=3,
        )
    ]
    assert is_relevant(chunk, fontes) == 3


def test_is_relevant_chunk_mais_amplo_que_fonte_ainda_casa():
    """Chunk article-aware (Art. 1º) cobre fonte que pede Art. 1º §1º."""
    chunk = _chunk(document_id="ren-2021-1000", artigo="Art. 1º")
    fontes = [
        _source(
            document_id="ren-2021-1000",
            section_label="Art. 1º, §1º",
            relevance=2,
        )
    ]
    assert is_relevant(chunk, fontes) == 2


def test_is_relevant_chunk_mais_especifico_que_fonte_ainda_casa():
    """Chunk hierarchical-child de §2º casa com fonte que pede Art. 1º."""
    chunk = _chunk(
        document_id="ren-2021-1000", artigo="Art. 1º", paragrafo="§2º"
    )
    fontes = [_source(document_id="ren-2021-1000", section_label="Art. 1º")]
    assert is_relevant(chunk, fontes) == 3


def test_is_relevant_fonte_sem_secao_nao_casa_qualquer_chunk_do_doc():
    chunk = _chunk(
        document_id="ren-2021-1000",
        artigo="Art. 99º",
        texto="texto completamente alheio ao trecho esperado",
    )
    fontes = [
        _source(
            document_id="ren-2021-1000",
            section_label="",
            support_excerpt=(
                "direito continuidade servico publico distribuicao"
            ),
        )
    ]
    assert is_relevant(chunk, fontes) == 0


def test_is_relevant_secao_nao_parseavel_depende_do_support_excerpt():
    chunk = _chunk(
        document_id="prodist-modulo-08",
        texto=(
            "A distribuidora deve apurar indicadores DEC e FEC para avaliar "
            "a continuidade do fornecimento de energia eletrica."
        ),
    )
    fontes = [
        _source(
            document_id="prodist-modulo-08",
            section_label="Módulo 8 - Qualidade do Fornecimento",
            support_excerpt=(
                "indicadores DEC FEC continuidade fornecimento energia"
            ),
            relevance=2,
        )
    ]
    assert is_relevant(chunk, fontes) == 2


def test_is_relevant_secao_nao_parseavel_com_texto_irrelevante_retorna_zero():
    chunk = _chunk(
        document_id="ren-2022-1031",
        artigo="Art. 99º",
        texto="texto irrelevante sobre outro assunto regulatorio",
    )
    fontes = [
        _source(
            document_id="ren-2022-1031",
            section_label="Ementa",
            support_excerpt=(
                "microgeracao minigeracao distribuida compensacao energia"
            ),
            relevance=3,
        )
    ]
    assert is_relevant(chunk, fontes) == 0


def test_is_relevant_documento_errado_nunca_casa():
    chunk = _chunk(document_id="ren-2021-1000", artigo="Art. 1º")
    fontes = [
        _source(
            document_id="prodist-modulo-08",
            section_label="Art. 1º",
            relevance=3,
        )
    ]
    assert is_relevant(chunk, fontes) == 0


def test_is_relevant_artigo_diferente_no_mesmo_doc_nao_casa():
    chunk = _chunk(document_id="ren-2021-1000", artigo="Art. 2º")
    fontes = [_source(document_id="ren-2021-1000", section_label="Art. 1º")]
    assert is_relevant(chunk, fontes) == 0


def test_is_relevant_fallback_para_texto_quando_chunk_nao_tem_estrutura():
    """Em fixed-size, o chunk não tem artigo/paragrafo — recorre ao texto."""
    chunk = _chunk(
        document_id="ren-2021-1000",
        texto=(
            "O consumidor possui direito à continuidade do serviço público "
            "de distribuição conforme indicadores DEC e FEC apurados pela "
            "distribuidora competente, com prazos máximos definidos."
        ),
    )
    fontes = [
        _source(
            document_id="ren-2021-1000",
            section_label="Art. 5º",
            support_excerpt=(
                "consumidor direito continuidade serviço público "
                "distribuição indicadores DEC FEC"
            ),
            relevance=2,
        )
    ]
    assert is_relevant(chunk, fontes) == 2


def test_is_relevant_retorna_maior_nota_quando_varias_fontes_casam():
    chunk = _chunk(document_id="ren-2021-1000", artigo="Art. 1º")
    fontes = [
        _source(
            document_id="ren-2021-1000",
            section_label="Art. 1º, §1º",
            relevance=1,
        ),
        _source(
            document_id="ren-2021-1000",
            section_label="Art. 1º",
            relevance=3,
        ),
    ]
    assert is_relevant(chunk, fontes) == 3


def test_build_relevance_vector_preserva_ordem_do_ranking():
    chunks = [
        _chunk(document_id="ren-2021-1000", artigo="Art. 1º"),
        _chunk(document_id="ren-2021-1000", artigo="Art. 2º"),
        _chunk(document_id="ren-2021-1000", artigo="Art. 1º", paragrafo="§1º"),
    ]
    fontes = [
        _source(
            document_id="ren-2021-1000",
            section_label="Art. 1º",
            relevance=3,
        )
    ]
    assert build_relevance_vector(chunks, fontes) == [3, 0, 3]
