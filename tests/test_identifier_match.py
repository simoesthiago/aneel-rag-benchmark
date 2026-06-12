"""Testes do match exato de identificador de submódulo (Fase 5)."""

from __future__ import annotations

from src.rag.identifier_match import doc_matches_submodulo, query_submodulo_id


def test_query_submodulo_id_extrai_identificador():
    assert query_submodulo_id("finalidade do PRORET Submódulo 2.4 na revisão") == "2-4"
    assert query_submodulo_id("No PRORET Submódulo 2.1, como...") == "2-1"
    assert query_submodulo_id("Tarifas no Submódulo 7.2?") == "7-2"
    assert query_submodulo_id("coberta pelo Submódulo 2.10-RQ") == "2-10-rq"
    assert query_submodulo_id("Segundo o Submódulo 5.1-OP, como...") == "5-1-op"
    assert query_submodulo_id("Submódulo 2.1A trata de...") == "2-1a"


def test_query_submodulo_id_sem_submodulo_devolve_none():
    assert query_submodulo_id("o que são bandeiras tarifárias?") is None
    assert query_submodulo_id("") is None


def test_doc_matches_2_1_nao_casa_2_1a_nem_2_10():
    ident = query_submodulo_id("PRORET Submódulo 2.1, Parcela A")  # "2-1"
    assert doc_matches_submodulo(
        "proret-modulo02-subm2-1-proret-submod-2-1-v-2-5", ident
    )
    # 2.1A (RI) — NÃO pode casar
    assert not doc_matches_submodulo(
        "proret-modulo02-subm2-1a-proret-submod-2-1a", ident
    )
    # 2.10 — NÃO pode casar
    assert not doc_matches_submodulo("proc-rede-2-10-rq", ident)


def test_doc_matches_2_10_casa_proc_rede():
    ident = query_submodulo_id("Submódulo 2.10-RQ")  # "2-10"
    assert doc_matches_submodulo("proc-rede-2-10-rq", ident)
    assert not doc_matches_submodulo("proret-modulo02-subm2-1-proret-submod-2-1", ident)


def test_doc_matches_submodulo_op_casa_procedimento_de_rede_sem_casar_proret():
    ident = query_submodulo_id("Segundo o Submódulo 5.1-OP")
    assert ident == "5-1-op"
    assert doc_matches_submodulo("proc-rede-s-bmodulo-5-1-op-2022-08", ident)
    assert not doc_matches_submodulo(
        "proret-modulo05-subm5-1-proret-submod-5-1-v-1-0c-aren20221003",
        ident,
    )


def test_doc_matches_2_4_e_7_2():
    assert doc_matches_submodulo(
        "proret-modulo02-subm2-4-proret-submod-2-4-v-4-1c-aren20221003",
        query_submodulo_id("Submódulo 2.4"),
    )
    assert doc_matches_submodulo(
        "proret-modulo07-subm7-2-proret-submod-7-2-v-2-5-aren20231060",
        query_submodulo_id("Submódulo 7.2"),
    )


def test_doc_matches_nao_confunde_string_de_versao():
    # "Submódulo 2.5" não deve casar um doc cuja ÚNICA ocorrência de 2-5 é a
    # versão "-v-2-5-" (a do subm 2.1).
    ident = query_submodulo_id("Submódulo 2.5")  # "2-5"
    assert ident == "2-5"
    assert not doc_matches_submodulo(
        "proret-modulo02-subm2-1-proret-submod-2-1-v-2-5-aren20251114", ident
    )


def test_doc_matches_identificador_vazio_e_falso():
    assert not doc_matches_submodulo("proret-modulo02-subm2-4-x", None)
    assert not doc_matches_submodulo("proret-modulo02-subm2-4-x", "")
