"""Testes do gerador LLM da Camada 3.5 sem chamadas reais de API."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from src.rag.generator import generate_llm_answer


def _context(
    idx: int,
    *,
    document_id: str = "ren-2021-1000",
    citation_label: str | None = None,
) -> dict[str, Any]:
    return {
        "chunk_id": f"{document_id}::markdown::fixed-size::{idx}",
        "document_id": document_id,
        "citation_label": citation_label or f"REN 1000/2021, Art. {idx}",
        "texto": f"Texto normativo do contexto {idx}.",
    }


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


def test_generate_llm_answer_sem_chave_usa_fallback(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = generate_llm_answer("pergunta", [_context(1)])

    assert result["llm_status"] == "skipped_no_llm_key"
    assert result["citations_used"] == []
    assert "Texto normativo do contexto 1" in result["answer"]


def test_generate_llm_answer_parseia_json_e_filtra_indices_invalidos():
    client = _FakeClient(
        '{"resposta": "A resposta esta no contexto [1].", '
        '"indices_citados": [1, 99, "2", 2, 1, "x"]}'
    )

    result = generate_llm_answer(
        "pergunta",
        [_context(1), _context(2)],
        client=client,
        model="modelo-teste",
    )

    assert result["llm_status"] == "ok"
    assert result["citations_used"] == [1, 2]
    assert "| [1] | REN 1000/2021, Art. 1 | ren-2021-1000 |" in result["answer"]
    assert "| [2] | REN 1000/2021, Art. 2 | ren-2021-1000 |" in result["answer"]
    call = client.chat.completions.calls[0]
    assert call["model"] == "modelo-teste"
    assert call["response_format"] == {"type": "json_object"}


def test_generate_llm_answer_usa_max_completion_tokens_para_gpt5():
    client = _FakeClient(
        '{"resposta": "A resposta esta no contexto [1].", ' '"indices_citados": [1]}'
    )

    result = generate_llm_answer(
        "pergunta",
        [_context(1)],
        client=client,
        model="gpt-5.4-mini",
        max_tokens=123,
    )

    assert result["llm_status"] == "ok"
    call = client.chat.completions.calls[0]
    assert call["max_completion_tokens"] == 123
    assert "max_tokens" not in call


def test_generate_llm_answer_usa_max_tokens_para_modelos_chat_legados():
    client = _FakeClient(
        '{"resposta": "A resposta esta no contexto [1].", ' '"indices_citados": [1]}'
    )

    result = generate_llm_answer(
        "pergunta",
        [_context(1)],
        client=client,
        model="gpt-4o-mini",
        max_tokens=123,
    )

    assert result["llm_status"] == "ok"
    call = client.chat.completions.calls[0]
    assert call["max_tokens"] == 123
    assert "max_completion_tokens" not in call


def test_generate_llm_answer_define_timeout_do_request():
    client = _FakeClient(
        '{"resposta": "A resposta esta no contexto [1].", ' '"indices_citados": [1]}'
    )

    result = generate_llm_answer(
        "pergunta",
        [_context(1)],
        client=client,
        model="gpt-5.4-mini",
        timeout_seconds=12,
    )

    assert result["llm_status"] == "ok"
    call = client.chat.completions.calls[0]
    assert call["timeout"] == 12


def test_generate_llm_answer_json_malformado_retorna_fallback_com_raw():
    client = _FakeClient("nao e json")

    result = generate_llm_answer(
        "pergunta",
        [_context(1)],
        client=client,
        model="modelo-teste",
    )

    assert result["llm_status"] == "error"
    assert result["raw"] == "nao e json"
    assert result["llm_error"].startswith("json_decode:")
    assert "Texto normativo do contexto 1" in result["answer"]
