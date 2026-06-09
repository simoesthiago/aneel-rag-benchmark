"""Testes do QueryExpander sem chamadas reais de API."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from src.rag.query_expander import QueryExpander, extract_identifiers


class _FakeChatCompletions:
    def __init__(self, content: str):
        self.content = content
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


class _FakeClient:
    def __init__(self, content: str):
        self.chat = SimpleNamespace(completions=_FakeChatCompletions(content))


def test_expand_sem_chave_devolve_passthrough(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    out = QueryExpander().expand("O que é REN 1095/2024?")

    assert out["status"] == "skipped_no_key"
    assert out["expanded_query"] == "O que é REN 1095/2024?"
    assert out["added_terms"] == []


def test_expand_com_client_fake_retorna_expanded():
    client = _FakeClient(
        '{"expanded_query": "Qual obrigação cadastral foi padronizada pela '
        'REN 1095/2024, considerando número de identificação da unidade '
        'consumidora?", '
        '"added_terms": ["número de identificação", "unidade consumidora"]}'
    )

    out = QueryExpander(client=client, model="modelo-teste").expand(
        "O que a REN 1095/2024 mudou no cadastro?"
    )

    assert out["status"] == "ok"
    assert "REN 1095/2024" in out["expanded_query"]
    assert "número de identificação" in out["added_terms"]
    call = client.chat.completions.calls[0]
    assert call["model"] == "modelo-teste"
    assert call["response_format"] == {"type": "json_object"}


def test_expand_json_malformado_retorna_status_error_e_passthrough():
    client = _FakeClient("nao e json")

    out = QueryExpander(client=client, model="modelo-teste").expand("pergunta x")

    assert out["status"] == "error"
    assert out["expanded_query"] == "pergunta x"
    assert out["error"].startswith("json_decode:")


def test_expand_preserva_identificador_de_documento():
    client = _FakeClient(
        '{"expanded_query": "Qual o objeto regulatório central da REN 905/2020 '
        'sobre regras de serviços de transmissão de energia elétrica?", '
        '"added_terms": ["serviços de transmissão", "regras de transmissão"]}'
    )

    out = QueryExpander(client=client, model="modelo-teste").expand(
        "Qual é o objeto regulatório central da REN 905/2020?"
    )

    assert out["status"] == "ok"
    assert "REN 905/2020" in out["expanded_query"]


def test_expand_detecta_drift_de_identificador():
    # mock devolve expansão com REN errada
    client = _FakeClient(
        '{"expanded_query": "Qual a obrigação cadastral da REN 1000/2021?", '
        '"added_terms": ["cadastro"]}'
    )

    out = QueryExpander(client=client, model="modelo-teste").expand(
        "Que obrigação a REN 1095/2024 padronizou?"
    )

    assert out["status"] == "identifier_drift"
    assert out["expanded_query"] == "Que obrigação a REN 1095/2024 padronizou?"
    assert "missing_identifiers" in out["error"]


def test_expand_temperatura_zero_e_json_response_format():
    client = _FakeClient(
        '{"expanded_query": "Q expandida", "added_terms": []}'
    )

    QueryExpander(client=client, model="m").expand("Q original")

    call = client.chat.completions.calls[0]
    assert call["temperature"] == 0.0
    assert call["response_format"] == {"type": "json_object"}


def test_expand_query_vazia_passthrough():
    out = QueryExpander().expand("")
    assert out["status"] == "ok"
    assert out["expanded_query"] == ""


def test_extract_identifiers_padroes_comuns():
    text = (
        "REN 1095/2024, PRORET Submódulo 2.3, PRODIST Módulo 7, "
        "Lei 9.074/1995, Despacho 1234/2020"
    )
    ids = extract_identifiers(text)
    assert any("ren 1095/2024" in i for i in ids)
    assert any("proret submódulo 2.3" in i or "proret submodulo 2.3" in i for i in ids)
    assert any("prodist módulo 7" in i or "prodist modulo 7" in i for i in ids)
    assert any("lei 9.074/1995" in i for i in ids)
    assert any("despacho 1234/2020" in i for i in ids)
