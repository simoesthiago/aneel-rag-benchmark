"""Testes da higiene de versão de submódulos PRORET (Fase F1.5)."""

from __future__ import annotations

from src.rag.version_hygiene import (
    is_versioned_submodulo,
    latest_version_by_submodulo,
    non_current_document_ids,
    submodulo_key,
    superseded_document_ids,
    version_tuple,
)

# Amostra real do corpus (subm 2-3, sete versões ao longo de 2011→2022).
SUBM_2_3 = [
    "proret-modulo02-subm2-3-proret-submod-2-3-v-1-0-aren2011457",
    "proret-modulo02-subm2-3-proret-submod-2-3-v-1-1-aren2013544",
    "proret-modulo02-subm2-3-proret-submod-2-3-v-2-0-aren2015686",
    "proret-modulo02-subm2-3-proret-submod-2-3-v-2-0c-aren20221003",
]


def test_submodulo_key_extrai_token():
    assert submodulo_key(SUBM_2_3[0]) == "2-3"
    assert (
        submodulo_key("proret-modulo07-subm7-2-proret-submod-7-2-v-2-5-aren20231060")
        == "7-2"
    )
    assert (
        submodulo_key("proret-modulo10-subm10-6-proret-submod-10-6-v-1-2-aren2024109")
        == "10-6"
    )
    # 2.1A é submódulo distinto de 2.1
    assert submodulo_key("proret-modulo02-subm2-1a-proret-submod-2-1a") == "2-1a"
    # doc sem token de submódulo
    assert submodulo_key("ren-2021-1000") is None


def test_version_tuple_ordena_consolidadas_corretamente():
    # '' < 'c', então v2.0 < v2.0c < v2.1 e v1.9c < v1.10c (por número, não ano)
    assert version_tuple("...-v-2-0-...") == (2, 0, "")
    assert version_tuple("...-v-2-0c-...") == (2, 0, "c")
    assert version_tuple("...-v-1-10c-aren20241084") == (1, 10, "c")
    assert version_tuple("...-v-2-5") == (2, 5, "")
    assert version_tuple("ren-2021-1000") is None
    # ordem central: a consolidada vem DEPOIS da versão crua de mesmo número,
    # mas ANTES da próxima versão menor maior
    assert version_tuple("...-v-2-0-...") < version_tuple("...-v-2-0c-...")
    assert version_tuple("...-v-2-0c-...") < version_tuple("...-v-2-1-...")
    # v1.9c (2022) < v1.10c (2024): por NÚMERO de versão, 9 < 10
    assert version_tuple("...-v-1-9c-aren20221003") < version_tuple(
        "...-v-1-10c-aren20241084"
    )


def test_is_versioned_submodulo():
    assert is_versioned_submodulo(SUBM_2_3[0])
    assert not is_versioned_submodulo("ren-2021-1000")
    assert not is_versioned_submodulo("prodist-modulo-03")


def test_latest_version_por_submodulo():
    latest = latest_version_by_submodulo(SUBM_2_3)
    assert latest == {"2-3": (2, 0, "c")}


def test_superseded_marca_todas_menos_a_mais_recente():
    sup = superseded_document_ids(SUBM_2_3)
    # a v2.0c é a vigente; as outras três são superadas
    assert SUBM_2_3[-1] not in sup
    assert sup == set(SUBM_2_3[:-1])


def test_superseded_nao_toca_docs_sem_versao():
    docs = ["ren-2021-1000", "prodist-modulo-03", *SUBM_2_3]
    sup = superseded_document_ids(docs)
    assert "ren-2021-1000" not in sup
    assert "prodist-modulo-03" not in sup
    assert len(sup) == 3  # só as três versões antigas do 2-3


def test_submodulos_distintos_nao_se_misturam():
    # 2.1 e 2.1A são submódulos diferentes; cada um mantém a sua mais recente.
    docs = [
        "proret-modulo02-subm2-1-proret-submod-2-1-v-2-4-aren20241091",
        "proret-modulo02-subm2-1-proret-submod-2-1-v-2-5-aren20251114",
        "proret-modulo02-subm2-1a-proret-submod-2-1a-v-1-0-aren2020999",
    ]
    sup = superseded_document_ids(docs)
    # só a v2.4 do 2.1 é superada; o 2.1A é único na sua chave → não superado
    assert sup == {"proret-modulo02-subm2-1-proret-submod-2-1-v-2-4-aren20241091"}


def test_artefato_id_duplicado_mesma_versao_nao_e_superado():
    # mesma versão v2.5 em dois formatos de id (modulo2 vs modulo02): ambos
    # são a mais recente → nenhum superado.
    docs = [
        "proret-modulo2-subm2-1-proret-submodulo-2-1-v-2-5",
        "proret-modulo02-subm2-1-proret-submod-2-1-v-2-5-aren20251114",
        "proret-modulo02-subm2-1-proret-submod-2-1-v-2-4-aren20241091",
    ]
    sup = superseded_document_ids(docs)
    assert "proret-modulo2-subm2-1-proret-submodulo-2-1-v-2-5" not in sup
    assert "proret-modulo02-subm2-1-proret-submod-2-1-v-2-5-aren20251114" not in sup
    assert "proret-modulo02-subm2-1-proret-submod-2-1-v-2-4-aren20241091" in sup


def test_non_current_exclui_alias_da_mesma_versao_quando_ha_id_oficial():
    docs = [
        "proret-modulo2-subm2-1-proret-submodulo-2-1-v-2-5",
        "proret-modulo02-subm2-1-proret-submod-2-1-v-2-5-aren20251114",
        "proret-modulo02-subm2-1-proret-submod-2-1-v-2-4-aren20241091",
    ]
    excluidos = non_current_document_ids(docs)
    assert (
        "proret-modulo02-subm2-1-proret-submod-2-1-v-2-5-aren20251114" not in excluidos
    )
    assert "proret-modulo2-subm2-1-proret-submodulo-2-1-v-2-5" in excluidos
    assert "proret-modulo02-subm2-1-proret-submod-2-1-v-2-4-aren20241091" in excluidos


def test_non_current_mantem_aliases_da_ultima_versao_sem_id_oficial():
    docs = [
        "proret-modulo2-subm2-1a-proret-submodulo-2-1a-v-2-2-anexo-xii",
        "proret-modulo02-subm2-1a-proret-submod-2-1a-v-2-2",
        "proret-modulo02-subm2-1a-proret-submod-2-1a-v-2-1-aren20241091",
    ]
    excluidos = non_current_document_ids(docs)
    assert "proret-modulo02-subm2-1a-proret-submod-2-1a-v-2-1-aren20241091" in excluidos
    assert (
        "proret-modulo2-subm2-1a-proret-submodulo-2-1a-v-2-2-anexo-xii" not in excluidos
    )
    assert "proret-modulo02-subm2-1a-proret-submod-2-1a-v-2-2" not in excluidos
