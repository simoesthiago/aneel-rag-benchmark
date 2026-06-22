"""Geradores de resposta para a Camada 3.5.

Dois caminhos:

- `generate_extractive_answer(contexts)`: baseline determinístico offline.
  Concatena os primeiros snippets. Não cita, não chama API.

- `generate_llm_answer(query, contexts, ...)`: gerador real via OpenAI.
  Recebe a pergunta e os contextos do retriever, pede ao modelo um JSON
  estruturado `{resposta, indices_citados}`, valida os índices, e renderiza
  uma resposta em Markdown com tabela de fontes. Sem `LLM_API_KEY`, devolve
  `skipped_no_llm_key` e cai no fallback extrativo (mesmo padrão de
  `optional_llm_metrics`).

O contrato de retorno padroniza:

    {
        "answer": str,                 # Markdown final (resposta + tabela)
        "citations_used": list[int],   # indices 1-based citados (já filtrados)
        "raw": str,                    # JSON cru devolvido pelo LLM (debug)
        "llm_status": str,             # "ok" | "skipped_no_llm_key" | ...
        "llm_error": str | None,       # detalhe quando llm_status != "ok"
    }
"""

from __future__ import annotations

import json
import os
from typing import Any, Iterable

from src.rag.prompt_builder import format_contexts

SYSTEM_PROMPT = (
    "Você responde dúvidas regulatórias da ANEEL usando exclusivamente o "
    "contexto fornecido. Cite cada afirmação com [N], onde N é o índice do "
    "bloco no contexto. Nunca cite um índice que não esteja no contexto. "
    "Cite com PARCIMÔNIA: para cada afirmação, cite apenas o bloco — ou os "
    "poucos blocos — que a sustentam diretamente. Não cite blocos redundantes, "
    "nem vários trechos do mesmo documento quando um só já basta. Prefira o "
    "menor conjunto de citações que justifica a resposta. "
    "Se o contexto não trouxer base para responder, diga explicitamente que "
    "não há base suficiente no corpus."
)

SYSTEM_PROMPT_V3 = (
    SYSTEM_PROMPT
    + " Antes de responder, faca uma checagem interna: identifique o tipo da "
    "pergunta (definicao, obrigacao, criterio, excecao, prazo ou calculo), "
    "selecione apenas os contextos diretamente necessarios e verifique se cada "
    "afirmacao normativa esta sustentada por uma citacao. Nao cite bloco que "
    "apenas menciona o tema; cite somente quando o trecho sustentar a frase. "
    "Se a evidencia estiver parcial, responda apenas o que o contexto permite "
    "e deixe explicito o que nao tem base suficiente."
)

PROMPT_VARIANT_ENV = "RAG_PROMPT_VARIANT"
SYSTEM_PROMPTS = {
    "default": SYSTEM_PROMPT,
    "v1": SYSTEM_PROMPT,
    "v3": SYSTEM_PROMPT_V3,
}

USER_PROMPT_TEMPLATE = (
    "Pergunta:\n{query}\n\n"
    "Contextos disponíveis (cite apenas estes índices, 1 a {n}):\n{contexts}\n\n"
    "Responda em JSON com as chaves:\n"
    '  - "resposta": string em PT-BR, com citações [N] inline.\n'
    '  - "indices_citados": lista mínima de inteiros (1-based) — só os blocos '
    "que sustentam diretamente a resposta, sem redundância.\n"
    "Se não houver base, devolva resposta justificando e indices_citados=[]."
)


def _system_prompt_from_env() -> str:
    """Seleciona a variante de prompt sem promover v3 por padrão."""
    variant = os.environ.get(PROMPT_VARIANT_ENV, "default").strip().lower()
    try:
        return SYSTEM_PROMPTS[variant]
    except KeyError as exc:
        valid = ", ".join(sorted(SYSTEM_PROMPTS))
        raise ValueError(
            f"{PROMPT_VARIANT_ENV} inválido: {variant!r}. Use um de: {valid}."
        ) from exc


def generate_extractive_answer(contexts: list[dict[str, Any]]) -> str:
    if not contexts:
        return "Nao encontrei base suficiente no corpus para responder."
    snippets = []
    for context in contexts[:3]:
        text = " ".join(str(context.get("texto", "")).split())
        snippets.append(text[:500])
    return "\n\n".join(snippets)


def generate_llm_answer(
    query: str,
    contexts: list[dict[str, Any]],
    *,
    client: Any | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    """Gera resposta com LLM ancorada nos contextos do retriever.

    `client` e `model` são injetáveis para testes; em produção, o cliente
    OpenAI é instanciado a partir de `LLM_API_KEY` e o modelo vem de
    `settings.LLM_MODEL`.
    """
    if not contexts:
        return {
            "answer": "Nao encontrei base suficiente no corpus para responder.",
            "citations_used": [],
            "raw": "",
            "llm_status": "empty_contexts",
            "llm_error": None,
        }

    if client is None and not (
        os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
    ):
        return _fallback(contexts, status="skipped_no_llm_key", error=None)

    if client is None:
        try:
            from openai import OpenAI
        except ImportError:
            return _fallback(contexts, status="skipped_missing_openai", error=None)
        from src.config.settings import get_llm_api_key

        client = OpenAI(api_key=get_llm_api_key())

    if (
        model is None
        or temperature is None
        or max_tokens is None
        or timeout_seconds is None
    ):
        from src.config.settings import (
            LLM_GENERATION_MAX_TOKENS,
            LLM_GENERATION_TEMPERATURE,
            LLM_MODEL,
            LLM_REQUEST_TIMEOUT_SECONDS,
        )

        model = model or LLM_MODEL
        temperature = LLM_GENERATION_TEMPERATURE if temperature is None else temperature
        max_tokens = LLM_GENERATION_MAX_TOKENS if max_tokens is None else max_tokens
        timeout_seconds = (
            LLM_REQUEST_TIMEOUT_SECONDS if timeout_seconds is None else timeout_seconds
        )

    user_prompt = USER_PROMPT_TEMPLATE.format(
        query=query,
        n=len(contexts),
        contexts=format_contexts(contexts),
    )

    try:
        response = client.chat.completions.create(
            model=model,
            temperature=temperature,
            **_token_limit_kwargs(model, max_tokens),
            timeout=timeout_seconds,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _system_prompt_from_env()},
                {"role": "user", "content": user_prompt},
            ],
        )
        raw = response.choices[0].message.content or "{}"
    except Exception as exc:
        return _fallback(contexts, status="error", error=str(exc))

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        return _fallback(contexts, status="error", error=f"json_decode: {exc}", raw=raw)

    resposta = str(parsed.get("resposta") or "").strip()
    indices = _coerce_indices(parsed.get("indices_citados"), n=len(contexts))

    if not resposta:
        return _fallback(contexts, status="error", error="resposta_vazia", raw=raw)

    answer_md = _render_answer(resposta, indices, contexts)
    return {
        "answer": answer_md,
        "citations_used": indices,
        "raw": raw,
        "llm_status": "ok",
        "llm_error": None,
    }


def _coerce_indices(raw: Any, *, n: int) -> list[int]:
    """Filtra índices para 1..n, remove duplicados e ordena pela ordem original."""
    if not isinstance(raw, Iterable) or isinstance(raw, (str, bytes)):
        return []
    vistos: set[int] = set()
    out: list[int] = []
    for item in raw:
        try:
            idx = int(item)
        except (TypeError, ValueError):
            continue
        if 1 <= idx <= n and idx not in vistos:
            vistos.add(idx)
            out.append(idx)
    return out


def _token_limit_kwargs(model: str, max_tokens: int) -> dict[str, int]:
    """Parâmetro correto de teto de tokens por família de modelo.

    Modelos GPT-5.x na API de Chat Completions rejeitam `max_tokens` e exigem
    `max_completion_tokens`. Modelos chat legados, como `gpt-4o-mini`, seguem
    aceitando `max_tokens`.
    """
    if str(model).lower().startswith("gpt-5"):
        return {"max_completion_tokens": max_tokens}
    return {"max_tokens": max_tokens}


def _render_answer(
    resposta: str,
    indices: list[int],
    contexts: list[dict[str, Any]],
) -> str:
    """Renderiza Markdown: resposta + tabela de fontes para os índices citados."""
    if not indices:
        return resposta
    linhas = [
        "| # | Citação | Documento |",
        "|---|---------|-----------|",
    ]
    for idx in indices:
        ctx = contexts[idx - 1]
        citation = str(ctx.get("citation_label") or ctx.get("chunk_id") or "")
        doc_id = str(ctx.get("document_id") or "")
        linhas.append(f"| [{idx}] | {citation} | {doc_id} |")
    return resposta + "\n\n**Fontes citadas**\n\n" + "\n".join(linhas)


def _fallback(
    contexts: list[dict[str, Any]],
    *,
    status: str,
    error: str | None,
    raw: str = "",
) -> dict[str, Any]:
    return {
        "answer": generate_extractive_answer(contexts),
        "citations_used": [],
        "raw": raw,
        "llm_status": status,
        "llm_error": error,
    }
