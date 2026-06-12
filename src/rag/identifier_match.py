"""Match exato de identificador de submódulo (Fase 5 do roadmap).

O retriever denso confunde documentos com identificadores quase idênticos —
Submódulo 2.1 vs 2.1A vs 2.10, ou 2.1 vs 2.4. Este módulo extrai o
identificador de submódulo citado na pergunta e testa, com **fronteira exata**,
se um `document_id` corresponde — para um boost de metadados (não semântico)
que garante que os chunks do doc certo entrem no pool de rerank.

Discriminação central (a razão de existir deste módulo):
- `2.1`  casa `...subm2-1-...` mas NÃO `...subm2-1a...` (2.1A) nem `...subm2-10...`
- `2.10` casa `...rede-2-10-rq` mas NÃO `...subm2-1-...`
- versões nos ids (ex.: `...-v-2-5-...`) NÃO são confundidas com submódulos,
  pois o match exige o prefixo `subm`/`rede-`.
"""

from __future__ import annotations

import re

# "Submódulo 2.4", "Subm. 2.1A", "submodulo 2.10", com ou sem acento.
_SUBMODULO_RE = re.compile(r"subm[óo]dulo\s+(\d+)\.(\d+)([a-z]?)", re.IGNORECASE)


def query_submodulo_id(query: str) -> str | None:
    """Extrai o identificador de submódulo da pergunta.

    Devolve no formato usado nos `document_id` (ex.: `2-4`, `2-1`, `2-1a`,
    `2-10`), ou `None` se a pergunta não cita um submódulo.
    """
    match = _SUBMODULO_RE.search(query or "")
    if not match:
        return None
    modulo, sub, sufixo = match.group(1), match.group(2), match.group(3).lower()
    return f"{modulo}-{sub}{sufixo}"


def doc_matches_submodulo(document_id: str, identificador: str) -> bool:
    """True se `document_id` corresponde ao submódulo com fronteira exata.

    O identificador precisa vir logo após o marcador de submódulo (`subm` em
    PRORET, `rede-` em Procedimentos de Rede) e ser seguido por um caractere
    que não seja letra/dígito — assim `2-1` não casa `2-10` nem `2-1a`, e
    strings de versão (`-v-2-5-`) não são confundidas com submódulos.
    """
    if not identificador:
        return False
    padrao = rf"(?:subm|rede-){re.escape(identificador)}(?![0-9a-z])"
    return re.search(padrao, str(document_id).lower()) is not None


__all__ = ["query_submodulo_id", "doc_matches_submodulo"]
