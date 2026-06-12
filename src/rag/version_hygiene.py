"""Higiene de versão para Procedimentos de Rede / PRORET (Fase F1.5).

Extensão da Fase 1 (que filtrou `situacao == 'revogada'`). Muitos submódulos do
PRORET vivem no corpus em **várias versões históricas** do mesmo documento
(ex.: Submódulo 2.3 tem v1.0/2011 … v2.0c/2022), e **nenhuma** está marcada
`situacao` — todas ficam `None`. Elas escapam do filtro da F1, competem no índice
denso e fazem o sistema citar uma versão **superada**.

Este módulo identifica, para cada submódulo, a **versão mais recente** e marca as
demais como *superadas*, para que sejam removidas da busca (igual à F1, mas para
versões não etiquetadas).

Decisões de desenho (validadas no corpus):
- **Ordenação por TUPLA de versão `(maior, menor, sufixo)`, não por ano.** As
  versões consolidadas (sufixo `c`, ex.: `v-2-2c`) são publicadas num ano
  posterior mas representam uma consolidação de uma versão *menor* — ordenar por
  ano as colocaria fora de ordem. `'' < 'c'`, então `v-2-0 < v-2-0c < v-2-1` e
  `v-1-9c < v-1-10c`.
- **Chave de submódulo = token `subm<M>-<N>[letra]`** (ex.: `2-3`, `2-1a`),
  globalmente único (o número do submódulo embute o módulo). `2.1A` é um
  submódulo **distinto** de `2.1` (não são versões um do outro).
- **Só docs com versão parseável** entram na higiene. Documento sem token de
  versão (`-v-X-Y-`) não é candidato e nunca é marcado superado.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

# Token do submódulo: `subm2-3`, `subm2-1a`, `subm10-6` … seguido de `-`.
_SUBMODULO_KEY_RE = re.compile(r"subm(\d+-\d+[a-z]?)(?=-)", re.IGNORECASE)
# Versão no id: `-v-2-0c-`, `-v-1-10c`, `-v-2-5` (sufixo de letra opcional).
_VERSAO_RE = re.compile(r"-v-(\d+)-(\d+)([a-z]?)(?:-|$)", re.IGNORECASE)
_OFFICIAL_SUFFIX_RE = re.compile(r"-(?:aren|adsp)\d+", re.IGNORECASE)


def submodulo_key(document_id: str) -> str | None:
    """Chave do submódulo (ex.: `2-3`, `2-1a`) ou `None` se não houver token."""
    match = _SUBMODULO_KEY_RE.search(str(document_id).lower())
    return match.group(1) if match else None


def version_tuple(document_id: str) -> tuple[int, int, str] | None:
    """Tupla `(maior, menor, sufixo)` da versão, ou `None` se não for versionado.

    `'' < 'c'`, então a comparação de tuplas dá a ordem correta:
    `(2,0,'') < (2,0,'c') < (2,1,'')` e `(1,9,'c') < (1,10,'')`.
    """
    match = _VERSAO_RE.search(str(document_id).lower())
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)), match.group(3).lower())


def is_versioned_submodulo(document_id: str) -> bool:
    """True se o doc é um submódulo versionado (tem chave **e** versão)."""
    return (
        submodulo_key(document_id) is not None
        and version_tuple(document_id) is not None
    )


def latest_version_by_submodulo(
    document_ids: Iterable[str],
) -> dict[str, tuple[int, int, str]]:
    """Mapeia cada submódulo para a **maior** tupla de versão observada."""
    latest: dict[str, tuple[int, int, str]] = {}
    for doc_id in document_ids:
        key = submodulo_key(doc_id)
        ver = version_tuple(doc_id)
        if key is None or ver is None:
            continue
        atual = latest.get(key)
        if atual is None or ver > atual:
            latest[key] = ver
    return latest


def superseded_document_ids(document_ids: Iterable[str]) -> set[str]:
    """Conjunto de `document_id` que são versões **superadas** (não a mais recente).

    Um doc é superado quando é um submódulo versionado e existe, na mesma coleção,
    uma versão **maior** do mesmo submódulo. Docs sem versão nunca são superados.
    """
    ids = list(document_ids)
    latest = latest_version_by_submodulo(ids)
    superados: set[str] = set()
    for doc_id in ids:
        key = submodulo_key(doc_id)
        ver = version_tuple(doc_id)
        if key is None or ver is None:
            continue
        if ver < latest[key]:
            superados.add(doc_id)
    return superados


def non_current_document_ids(document_ids: Iterable[str]) -> set[str]:
    """Ids que não devem competir no índice de submódulos PRORET.

    Inclui:
    - versões antigas do mesmo submódulo;
    - aliases da versão vigente quando existe um id oficial melhor, com
      sufixo normativo (`aren`/`adsp`).

    Se a versão vigente só aparece em aliases sem sufixo oficial, mantém todos
    esses aliases para evitar descarte arbitrário de possível documento único.
    """
    ids = list(document_ids)
    latest = latest_version_by_submodulo(ids)
    by_key: dict[str, list[str]] = {}
    for doc_id in ids:
        key = submodulo_key(doc_id)
        ver = version_tuple(doc_id)
        if key is None or ver is None:
            continue
        if ver == latest[key]:
            by_key.setdefault(key, []).append(doc_id)

    current_ids: set[str] = set()
    for latest_ids in by_key.values():
        official = [doc_id for doc_id in latest_ids if _is_official_id(doc_id)]
        current_ids.update(official or latest_ids)

    excluded: set[str] = set()
    for doc_id in ids:
        if not is_versioned_submodulo(doc_id):
            continue
        if doc_id not in current_ids:
            excluded.add(doc_id)
    return excluded


def _is_official_id(document_id: str) -> bool:
    """True se o id carrega o ato normativo associado (`aren` ou `adsp`)."""
    return _OFFICIAL_SUFFIX_RE.search(str(document_id).lower()) is not None


__all__ = [
    "submodulo_key",
    "version_tuple",
    "is_versioned_submodulo",
    "latest_version_by_submodulo",
    "superseded_document_ids",
    "non_current_document_ids",
]
