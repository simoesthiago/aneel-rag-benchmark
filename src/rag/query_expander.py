"""Query expansion (rewriter) para melhorar a recuperação semântica.

Reescreve a pergunta do usuário usando um LLM para incluir termos técnicos
discriminantes do domínio regulatório ANEEL, ANTES de ir ao retriever. O
gerador continua recebendo a pergunta original — query expansion é uma
intervenção restrita ao retrieval.

Padrão de uso (em testes e produção):

    from src.rag.query_expander import QueryExpander
    expander = QueryExpander()
    out = expander.expand("O que é REN 1095/2024?")
    # out["expanded_query"] vai pro retriever; out["status"] indica origem.

Em qualquer status != "ok", `expanded_query == query` (passthrough seguro):
sem chave de API, JSON malformado, drift de identificador, etc.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

SYSTEM_PROMPT = (
    "Você reescreve perguntas de usuário sobre regulação do setor elétrico "
    "brasileiro (ANEEL) para melhorar a recuperação semântica em uma base "
    "documental composta por Resoluções Normativas (REN), PRORET, PRODIST, "
    "Procedimentos de Rede, leis e despachos.\n\n"
    "Sua tarefa NÃO é trocar a pergunta por sinônimos genéricos. É inferir "
    "termos técnicos DISCRIMINANTES que diferenciam o conceito perguntado "
    "de conceitos similares no domínio (ex.: distinguir \"remuneração "
    "regulatória\" de \"tarifa de aplicação\"; \"custo de capital\" de "
    "\"custo operacional\"; \"WACC regulatório\" de \"WACC contábil\"; "
    "\"perdas técnicas\" de \"perdas não técnicas\").\n\n"
    "Regras estritas:\n"
    "1. NUNCA altere identificadores numéricos de documentos. REN N/AAAA, "
    "PRORET Submódulo X.Y, PRODIST Módulo N, Lei N/AAAA, Despacho N/AAAA "
    "devem aparecer EXATAMENTE como na pergunta original (ou ausentes, se "
    "ausentes).\n"
    "2. Preserve o significado. A pergunta expandida deve continuar "
    "respondível pelo MESMO trecho que responderia a original.\n"
    "3. Adicione 2 a 5 termos técnicos formais/jurídicos do setor elétrico "
    "regulado que apareceriam num texto normativo ANEEL sobre o tema.\n"
    "4. Mantenha em português, tom interrogativo.\n"
    "5. Devolva JSON estrito: {\"expanded_query\": string, "
    "\"added_terms\": [string, ...]}"
)

USER_PROMPT_TEMPLATE = "Pergunta original:\n{query}\n\nReescreva-a seguindo as regras."

# Captura identificadores documentais que NÃO podem driftar entre a query
# original e a expandida. Exemplos cobertos:
#   REN 1000/2021, REN 1.095/2024
#   PRORET Submódulo 2.3
#   PRODIST Módulo 7
#   Lei 9.074/1995, Lei 8.987/1995
#   Despacho 1234/2020
_IDENTIFIER_PATTERNS = [
    re.compile(r"REN\s+[\d\.]+/\d{4}", re.IGNORECASE),
    re.compile(r"PRORET\s+Subm[óo]dulo\s+[\d\.]+", re.IGNORECASE),
    re.compile(r"PRODIST\s+M[óo]dulo\s+\d+", re.IGNORECASE),
    re.compile(r"Lei\s+[\d\.]+/\d{4}", re.IGNORECASE),
    re.compile(r"Despacho\s+[\d\.]+/\d{4}", re.IGNORECASE),
]


def extract_identifiers(text: str) -> list[str]:
    """Extrai identificadores documentais normalizados (lower, espaço único)."""
    found: list[str] = []
    for pattern in _IDENTIFIER_PATTERNS:
        for match in pattern.findall(text or ""):
            normalized = re.sub(r"\s+", " ", match.strip().lower())
            if normalized not in found:
                found.append(normalized)
    return found


def _passthrough(query: str, *, status: str, error: str | None = None) -> dict[str, Any]:
    return {
        "expanded_query": query,
        "added_terms": [],
        "status": status,
        "error": error,
    }


class QueryExpander:
    """Reescreve queries via LLM para retrieval mais discriminante."""

    def __init__(
        self,
        *,
        client: Any | None = None,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 400,
    ) -> None:
        self._client = client
        self._model_override = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def expand(self, query: str) -> dict[str, Any]:
        """Retorna dict com expanded_query + status. Passthrough seguro em erro."""
        if not query or not query.strip():
            return _passthrough(query, status="ok")

        if self._client is None and not (
            os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
        ):
            return _passthrough(query, status="skipped_no_key")

        client = self._client
        if client is None:
            try:
                from openai import OpenAI
            except ImportError:
                return _passthrough(query, status="skipped_missing_openai")
            from src.config.settings import get_llm_api_key

            client = OpenAI(api_key=get_llm_api_key())

        model = self._model_override
        if model is None:
            from src.config.settings import LLM_MODEL

            model = LLM_MODEL

        try:
            response = client.chat.completions.create(
                model=model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": USER_PROMPT_TEMPLATE.format(query=query)},
                ],
            )
            raw = response.choices[0].message.content or "{}"
        except Exception as exc:
            return _passthrough(query, status="error", error=str(exc))

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            return _passthrough(query, status="error", error=f"json_decode: {exc}")

        expanded = str(parsed.get("expanded_query") or "").strip()
        added_terms_raw = parsed.get("added_terms") or []
        added_terms = [str(t) for t in added_terms_raw if str(t).strip()]

        if not expanded:
            return _passthrough(query, status="error", error="empty_expanded_query")

        # Validação anti-drift: identificadores documentais presentes na
        # original devem aparecer na expandida (case-insensitive).
        original_ids = extract_identifiers(query)
        expanded_ids = extract_identifiers(expanded)
        missing = [ident for ident in original_ids if ident not in expanded_ids]
        if missing:
            return _passthrough(
                query,
                status="identifier_drift",
                error=f"missing_identifiers: {missing}",
            )

        return {
            "expanded_query": expanded,
            "added_terms": added_terms,
            "status": "ok",
            "error": None,
        }
