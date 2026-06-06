"""Contrato, validação e publicação do ground truth de avaliação.

O ground truth é artefato de dados publicado no HuggingFace Hub, não arquivo
versionado no Git. Este módulo guarda o contrato reproduzível: schema JSONL,
validações contra o corpus extraído e publicação versionada.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import requests
from huggingface_hub import CommitOperationAdd, HfApi, hf_hub_url

from src.config.settings import (
    GROUND_TRUTH_HUB_PREFIX,
    GROUND_TRUTH_VERSION,
    HF_DATASET_REPO,
    get_hf_token,
)

GROUND_TRUTH_FILENAME = "ground_truth.jsonl"
GROUND_TRUTH_MANIFEST_FILENAME = "manifest.json"
GROUND_TRUTH_SCHEMA_VERSION = 1
DEFAULT_EXPECTED_COUNT = 50
DEFAULT_SUPPORT_EXCERPT_MIN_COVERAGE = 0.70
DEFAULT_ANSWER_SUPPORT_MIN_COVERAGE = 0.55

QUERY_TYPES = frozenset(
    {
        "definicao",
        "prazo",
        "obrigacao",
        "condicao",
        "excecao",
        "competencia",
        "procedimento",
        "criterio_tecnico",
        "calculo",
    }
)
DIFFICULTIES = frozenset({"facil", "media", "dificil"})
ANSWERABILITIES = frozenset({"corpus_supported", "source_only", "needs_review"})
RELEVANCE_VALUES = frozenset({1, 2, 3})

REQUIRED_FIELDS = frozenset(
    {
        "question_id",
        "question",
        "expected_answer",
        "query_type",
        "difficulty",
        "answerability",
        "tipo",
        "subtipo",
        "relevant_sources",
        "notes",
    }
)
REQUIRED_SOURCE_FIELDS = frozenset(
    {
        "document_id",
        "titulo",
        "citation_label",
        "section_label",
        "url",
        "support_excerpt",
        "relevance",
    }
)

STOPWORDS = frozenset(
    """
    a o as os um uma uns umas de da do das dos e em no na nos nas por para com
    sem sob sobre entre que se ao aos à às é são ser foi foram como qual quais
    quanto quando onde segundo antes depois este esta esse essa isso sua seu suas
    seus pela pelo pelas pelos mais menos ou também não nos nas dos das
    """.split()
)

DOMAIN_SHORT_TOKENS = frozenset(
    """
    dec fec dic fic dmic ren reh res ons te
    pch ena ear gsf pis kv kw mwh gwh
    """.split()
)


class GroundTruthValidationError(ValueError):
    """Erro de contrato do ground truth."""


def hub_prefix(version: str = GROUND_TRUTH_VERSION) -> str:
    """Prefixo versionado do ground truth no HuggingFace Hub."""
    return f"{GROUND_TRUTH_HUB_PREFIX}/version={version}"


def load_ground_truth_jsonl(path: str | Path) -> list[dict[str, Any]]:
    """Carrega JSONL de ground truth com erro claro por linha inválida."""
    path = Path(path)
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError as exc:
            raise GroundTruthValidationError(
                f"JSON inválido na linha {line_number}: {exc.msg}"
            ) from exc
        if not isinstance(parsed, dict):
            raise GroundTruthValidationError(
                f"Linha {line_number}: esperado objeto JSON."
            )
        rows.append(parsed)
    return rows


def validate_ground_truth_file(
    path: str | Path,
    *,
    corpus_df: pd.DataFrame | None = None,
    schema_only: bool = False,
    expected_count: int = DEFAULT_EXPECTED_COUNT,
) -> dict[str, Any]:
    """Carrega e valida um arquivo JSONL."""
    return validate_ground_truth(
        load_ground_truth_jsonl(path),
        corpus_df=corpus_df,
        schema_only=schema_only,
        expected_count=expected_count,
    )


def validate_ground_truth(
    rows: list[dict[str, Any]],
    *,
    corpus_df: pd.DataFrame | None = None,
    schema_only: bool = False,
    expected_count: int = DEFAULT_EXPECTED_COUNT,
    support_excerpt_min_coverage: float = DEFAULT_SUPPORT_EXCERPT_MIN_COVERAGE,
    answer_support_min_coverage: float = DEFAULT_ANSWER_SUPPORT_MIN_COVERAGE,
) -> dict[str, Any]:
    """Valida schema, evidências e consistência com o corpus.

    `schema_only=True` evita qualquer dependência de corpus e é usado nos testes
    offline. Para validação completa, passe `corpus_df` com a tabela documents
    carregada do Hub.
    """
    errors: list[str] = []
    if len(rows) != expected_count:
        errors.append(f"Esperadas {expected_count} perguntas; recebido {len(rows)}.")

    expected_ids = [f"gt-{index:04d}" for index in range(1, len(rows) + 1)]
    actual_ids = [str(row.get("question_id")) for row in rows]
    if actual_ids != expected_ids:
        errors.append(
            "question_id deve ser sequencial: "
            f"esperado início {expected_ids[:3]}, recebido {actual_ids[:3]}."
        )

    catalog = None if schema_only else _build_corpus_catalog(corpus_df, errors)

    for index, row in enumerate(rows, start=1):
        qid = str(row.get("question_id") or f"linha {index}")
        _validate_row_schema(row, qid, errors)
        if _contains_key(row, "chunk_id"):
            errors.append(f"{qid}: campo proibido `chunk_id` encontrado.")
        sources = row.get("relevant_sources")
        if isinstance(sources, list):
            for source_index, source in enumerate(sources, start=1):
                _validate_source(
                    row,
                    source,
                    source_index=source_index,
                    catalog=catalog,
                    errors=errors,
                    support_excerpt_min_coverage=support_excerpt_min_coverage,
                    answer_support_min_coverage=answer_support_min_coverage,
                )

    if errors:
        raise GroundTruthValidationError("\n".join(errors))

    answerability_counts = Counter(str(row["answerability"]) for row in rows)
    return {
        "question_count": len(rows),
        "corpus_supported": answerability_counts.get("corpus_supported", 0),
        "source_only": answerability_counts.get("source_only", 0),
        "needs_review": answerability_counts.get("needs_review", 0),
        "document_count": len(
            {
                source["document_id"]
                for row in rows
                for source in row.get("relevant_sources", [])
            }
        ),
    }


def text_coverage(needle: str, haystack: str) -> tuple[float, list[str]]:
    """Percentual de tokens informativos de `needle` encontrados em `haystack`."""
    needle_tokens = informative_tokens(needle)
    if not needle_tokens:
        return 1.0, []
    haystack_tokens = set(informative_tokens(haystack))
    missing = [token for token in needle_tokens if token not in haystack_tokens]
    coverage = 1.0 - (len(missing) / len(needle_tokens))
    return coverage, missing


def informative_tokens(text: str) -> list[str]:
    """Normaliza texto regulatório e devolve tokens relevantes para comparação."""
    return [
        token
        for token in normalize_text(text).split()
        if token not in STOPWORDS
        and (len(token) >= 4 or token in DOMAIN_SHORT_TOKENS)
    ]


def normalize_text(text: str) -> str:
    """Normaliza acentos e mojibake leve comum no HTML do Planalto."""
    value = str(text).lower()
    # O Planalto frequentemente aparece como `produçăo`, `condiçőes`, `nş`.
    value = (
        value.replace("ă", "a")
        .replace("ę", "e")
        .replace("ő", "o")
        .replace("ş", "s")
        .replace("º", "o")
        .replace("ª", "a")
    )
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def build_ground_truth_manifest(
    path: str | Path,
    *,
    rows: list[dict[str, Any]],
    version: str,
    repo_id: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Monta manifesto auditável para o artefato publicado."""
    path = Path(path)
    return {
        "artifact_type": "ground_truth",
        "schema_version": GROUND_TRUTH_SCHEMA_VERSION,
        "version": version,
        "question_count": len(rows),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "corpus_repo": repo_id,
        "created_at": created_at
        or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "validation": {
            "expected_count": len(rows),
            "support_excerpt_min_coverage": DEFAULT_SUPPORT_EXCERPT_MIN_COVERAGE,
            "answer_support_min_coverage": DEFAULT_ANSWER_SUPPORT_MIN_COVERAGE,
        },
    }


def publish_ground_truth(
    path: str | Path,
    *,
    rows: list[dict[str, Any]] | None = None,
    version: str = GROUND_TRUTH_VERSION,
    repo_id: str | None = None,
    force: bool = False,
    api: HfApi | None = None,
) -> str:
    """Publica JSONL + manifesto no HuggingFace Hub.

    A validação completa deve acontecer antes de chamar esta função. Ela ainda
    valida formato básico e impede sobrescrita acidental da versão.
    """
    path = Path(path)
    if repo_id is None:
        repo_id = HF_DATASET_REPO
    if rows is None:
        rows = load_ground_truth_jsonl(path)
        validate_ground_truth(rows, schema_only=True, expected_count=len(rows))
    if api is None:
        api = HfApi(token=get_hf_token())

    prefix = hub_prefix(version)
    target_jsonl = f"{prefix}/{GROUND_TRUTH_FILENAME}"
    target_manifest = f"{prefix}/{GROUND_TRUTH_MANIFEST_FILENAME}"

    existing = set(api.list_repo_files(repo_id, repo_type="dataset"))
    if not force and (target_jsonl in existing or target_manifest in existing):
        raise GroundTruthValidationError(
            f"Ground truth versão {version} já existe no Hub. "
            "Use --force para sobrescrever."
        )

    manifest = build_ground_truth_manifest(
        path,
        rows=rows,
        version=version,
        repo_id=repo_id,
    )
    operations = [
        CommitOperationAdd(
            path_in_repo=target_jsonl,
            path_or_fileobj=path,
        ),
        CommitOperationAdd(
            path_in_repo=target_manifest,
            path_or_fileobj=json.dumps(
                manifest,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ).encode("utf-8"),
        ),
    ]
    api.create_commit(
        repo_id=repo_id,
        repo_type="dataset",
        commit_message=f"Ground truth {version}: {len(rows)} perguntas",
        operations=operations,
    )
    return f"https://huggingface.co/datasets/{repo_id}"


def load_ground_truth_hub(
    *,
    version: str = GROUND_TRUTH_VERSION,
    repo_id: str | None = None,
) -> list[dict[str, Any]]:
    """Carrega o JSONL publicado no Hub em memória, sem snapshot/cache local."""
    if repo_id is None:
        repo_id = HF_DATASET_REPO
    path = f"{hub_prefix(version)}/{GROUND_TRUTH_FILENAME}"
    url = hf_hub_url(repo_id=repo_id, filename=path, repo_type="dataset")
    headers = {}
    token = os.environ.get("HF_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = requests.get(url, headers=headers, timeout=120)
    response.raise_for_status()
    rows = []
    for line_number, line in enumerate(
        response.content.decode("utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise GroundTruthValidationError(
                f"JSON inválido no Hub, linha {line_number}: {exc.msg}"
            ) from exc
    return rows


def _validate_row_schema(
    row: dict[str, Any],
    qid: str,
    errors: list[str],
) -> None:
    missing = REQUIRED_FIELDS - set(row)
    if missing:
        errors.append(f"{qid}: campos obrigatórios ausentes: {sorted(missing)}.")
    if row.get("query_type") not in QUERY_TYPES:
        errors.append(f"{qid}: query_type inválido: {row.get('query_type')!r}.")
    if row.get("difficulty") not in DIFFICULTIES:
        errors.append(f"{qid}: difficulty inválido: {row.get('difficulty')!r}.")
    if row.get("answerability") not in ANSWERABILITIES:
        errors.append(
            f"{qid}: answerability inválido: {row.get('answerability')!r}."
        )
    sources = row.get("relevant_sources")
    if not isinstance(sources, list) or not sources:
        errors.append(f"{qid}: relevant_sources deve ser lista não vazia.")


def _validate_source(
    row: dict[str, Any],
    source: Any,
    *,
    source_index: int,
    catalog: dict[str, dict[str, Any]] | None,
    errors: list[str],
    support_excerpt_min_coverage: float,
    answer_support_min_coverage: float,
) -> None:
    qid = str(row.get("question_id"))
    label = f"{qid} fonte {source_index}"
    if not isinstance(source, dict):
        errors.append(f"{label}: fonte deve ser objeto JSON.")
        return
    missing = REQUIRED_SOURCE_FIELDS - set(source)
    if missing:
        errors.append(f"{label}: campos obrigatórios ausentes: {sorted(missing)}.")
    if source.get("relevance") not in RELEVANCE_VALUES:
        errors.append(f"{label}: relevance inválido: {source.get('relevance')!r}.")
    if not str(source.get("url", "")).startswith(("http://", "https://")):
        errors.append(f"{label}: URL inválida: {source.get('url')!r}.")

    support_excerpt = str(source.get("support_excerpt") or "")
    expected_answer = str(row.get("expected_answer") or "")
    answer_coverage, answer_missing = text_coverage(expected_answer, support_excerpt)
    if answer_coverage < answer_support_min_coverage:
        errors.append(
            f"{label}: expected_answer pouco sustentada pelo support_excerpt "
            f"({answer_coverage:.2f}); tokens ausentes={answer_missing[:12]}."
        )

    if catalog is None:
        return
    doc_id = str(source.get("document_id") or "")
    document = catalog.get(doc_id)
    if document is None:
        errors.append(f"{label}: document_id não existe no corpus: {doc_id}.")
        return
    if str(row.get("tipo")) != str(document["tipo"]):
        errors.append(
            f"{label}: tipo diverge do corpus: "
            f"{row.get('tipo')!r} != {document['tipo']!r}."
        )
    if str(row.get("subtipo")) != str(document["subtipo"]):
        errors.append(
            f"{label}: subtipo diverge do corpus: "
            f"{row.get('subtipo')!r} != {document['subtipo']!r}."
        )
    valid_urls = {
        url for url in [document["url_original"], document["url_consolidado"]] if url
    }
    if source.get("url") not in valid_urls:
        errors.append(
            f"{label}: URL não bate com url_original/url_consolidado do corpus."
        )

    if row.get("answerability") == "corpus_supported":
        support_coverage, support_missing = text_coverage(
            support_excerpt,
            document["texto_corpus"],
        )
        if support_coverage < support_excerpt_min_coverage:
            errors.append(
                f"{label}: support_excerpt não aparece no corpus "
                f"({support_coverage:.2f}); tokens ausentes={support_missing[:12]}."
            )


def _build_corpus_catalog(
    corpus_df: pd.DataFrame | None,
    errors: list[str],
) -> dict[str, dict[str, Any]] | None:
    if corpus_df is None:
        errors.append("corpus_df é obrigatório para validação completa.")
        return None
    required_columns = {
        "id",
        "tipo",
        "subtipo",
        "url_original",
        "url_consolidado",
        "texto_bruto",
    }
    missing = required_columns - set(corpus_df.columns)
    if missing:
        errors.append(f"corpus_df sem colunas obrigatórias: {sorted(missing)}.")
        return None

    catalog: dict[str, dict[str, Any]] = {}
    for doc_id, group in corpus_df.groupby("id", sort=False):
        first = group.iloc[0]
        catalog[str(doc_id)] = {
            "tipo": first.get("tipo"),
            "subtipo": first.get("subtipo"),
            "url_original": _none_if_na(first.get("url_original")),
            "url_consolidado": _none_if_na(first.get("url_consolidado")),
            "texto_corpus": "\n".join(
                str(text or "")
                for text in group.get("texto_bruto", pd.Series(dtype=str)).tolist()
            ),
        }
    return catalog


def _contains_key(value: Any, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_contains_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, key) for item in value)
    return False


def _none_if_na(value: Any) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    text = str(value)
    return text if text else None


def _rows_to_jsonl_bytes(rows: Iterable[dict[str, Any]]) -> bytes:
    """Serializa linhas JSONL em memória, útil para testes futuros."""
    buffer = io.StringIO()
    for row in rows:
        buffer.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
        buffer.write("\n")
    return buffer.getvalue().encode("utf-8")
