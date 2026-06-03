"""
Reparo temporário para completar pares texto/markdown ausentes no Hub.

Por que este módulo existe?
---------------------------
Após o refactor da ingestão, o benchmark passou a exigir duas linhas por
documento: `metodo_extracao=texto` e `metodo_extracao=markdown`. Rodadas
incrementais podem deixar pares incompletos quando um download ou extrator falha
em uma estratégia e passa na outra.

Este script é intencionalmente cirúrgico e temporário: ele carrega o corpus já
publicado, identifica ids com uma estratégia faltante, baixa novamente apenas o
arquivo desses ids e publica somente as linhas reparadas via merge incremental.

Uso:
    python -m src.ingestion.repair_missing_extractions --dry-run --max-docs 5
    python -m src.ingestion.repair_missing_extractions
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import pandas as pd
import requests

from src.config.settings import HF_DATASET_REPO
from src.ingestion.extractors import extrair_texto
from src.ingestion.schema import montar_documento, validar_schema
from src.ingestion.scraper_atos import _baixar_url_cedoc
from src.ingestion.scraper_manuais import _baixar_url
from src.ingestion.uploader import (
    carregar_corpus_hub,
    mesclar_corpus,
    publicar_corpus,
)

METODOS_ESPERADOS = frozenset({"texto", "markdown"})


@dataclass(frozen=True)
class ReparoExtracao:
    """Representa uma linha ausente para um documento já existente no Hub."""

    doc_id: str
    metodo_faltante: str
    referencia: dict[str, Any]


def encontrar_reparos(df: pd.DataFrame) -> list[ReparoExtracao]:
    """
    Encontra documentos que não possuem as duas estratégias de extração.

    Retorna um item por método faltante. A linha `referencia` é a versão que já
    existe no Hub e fornece os metadados estáveis do documento.
    """
    reparos: list[ReparoExtracao] = []
    for doc_id, grupo in df.groupby("id", sort=True):
        presentes = set(grupo["metodo_extracao"].dropna().astype(str))
        for metodo_faltante in sorted(METODOS_ESPERADOS - presentes):
            referencia = grupo.iloc[0].to_dict()
            reparos.append(
                ReparoExtracao(
                    doc_id=str(doc_id),
                    metodo_faltante=metodo_faltante,
                    referencia=referencia,
                )
            )
    return reparos


def montar_documento_reparado(
    referencia: dict[str, Any],
    resultado: dict[str, Any],
    *,
    scraped_at: str,
) -> dict[str, Any]:
    """Monta a linha reparada preservando metadados do documento de referência."""
    return montar_documento(
        id=str(referencia["id"]),
        tipo=str(referencia["tipo"]),
        subtipo=_none_if_na(referencia.get("subtipo")),
        numero=_none_if_na(referencia.get("numero")),
        ano=_int_or_none(referencia.get("ano")),
        titulo=str(referencia["titulo"]),
        assunto=_none_if_na(referencia.get("assunto")),
        situacao=_none_if_na(referencia.get("situacao")),
        data_publicacao=_none_if_na(referencia.get("data_publicacao")),
        fonte=str(referencia["fonte"]),
        url_original=str(referencia["url_original"]),
        url_consolidado=_none_if_na(referencia.get("url_consolidado")),
        formato_original=str(referencia["formato_original"]),
        resultado=resultado,
        scraped_at=scraped_at,
    )


def reparar_extracao(reparo: ReparoExtracao, *, scraped_at: str) -> dict[str, Any]:
    """Baixa o arquivo original, extrai o método faltante e retorna a linha nova."""
    referencia = reparo.referencia
    formato = str(referencia["formato_original"]).lower()
    conteudo = baixar_conteudo_referencia(referencia)
    resultado = extrair_texto(
        conteudo,
        formato,
        formato_saida=reparo.metodo_faltante,
    )

    if len(resultado["texto"].strip()) < 100:
        raise RuntimeError(
            f"{reparo.doc_id}: extração {reparo.metodo_faltante} retornou "
            "texto_bruto < 100 chars"
        )

    return montar_documento_reparado(referencia, resultado, scraped_at=scraped_at)


def baixar_conteudo_referencia(referencia: dict[str, Any]) -> bytes:
    """
    Baixa o arquivo usando o caminho mais compatível com a fonte.

    Para `www2.aneel.gov.br`, usamos o helper do cedoc/ com curl_cffi porque
    requests comum sofre bloqueio por TLS fingerprinting. Para os demais hosts,
    reaproveitamos o downloader dos manuais, que já cobre GitLab/gov.br/ONS.
    """
    formato = str(referencia["formato_original"]).lower()
    url_original = str(referencia["url_original"])
    url_consolidado = _none_if_na(referencia.get("url_consolidado"))
    host = urlparse(url_original).hostname or ""

    if formato == "pdf" and host == "www2.aneel.gov.br":
        conteudo = _baixar_url_cedoc(url_original, "reparo-original")
        if conteudo is None and url_consolidado:
            conteudo = _baixar_url_cedoc(url_consolidado, "reparo-consolidado")
        if conteudo is None:
            raise RuntimeError(f"Não foi possível baixar PDF do cedoc/: {url_original}")
        return conteudo

    try:
        return _baixar_url(url_original)
    except requests.HTTPError as exc:
        if not url_consolidado:
            raise
        print(f"    original falhou ({exc}); tentando consolidado")
        return _baixar_url(url_consolidado)


def _none_if_na(value: object) -> Any | None:
    """Converte NaN/pandas.NA em None para manter o schema limpo."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    return value


def _int_or_none(value: object) -> int | None:
    value = _none_if_na(value)
    if value is None:
        return None
    return int(value)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Repara pares texto/markdown ausentes no corpus do Hub"
    )
    parser.add_argument("--repo", default=HF_DATASET_REPO)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Baixa e extrai, mas não publica no Hub",
    )
    parser.add_argument(
        "--max-docs",
        type=int,
        default=None,
        help="Limita a quantidade de reparos nesta execução",
    )
    parser.add_argument(
        "--id",
        action="append",
        dest="ids",
        help="Repara apenas ids específicos (repetível)",
    )
    args = parser.parse_args()

    df_hub = carregar_corpus_hub(args.repo)
    reparos = encontrar_reparos(df_hub)
    if args.ids:
        ids = set(args.ids)
        reparos = [reparo for reparo in reparos if reparo.doc_id in ids]
    if args.max_docs is not None:
        reparos = reparos[: args.max_docs]

    if not reparos:
        print("✅ Nenhum par texto/markdown ausente.")
        return 0

    print(f"🔧 Reparos a executar: {len(reparos)}")
    scraped_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    documentos: list[dict[str, Any]] = []
    erros: list[str] = []

    for index, reparo in enumerate(reparos, start=1):
        print(
            f"[{index}/{len(reparos)}] {reparo.doc_id} "
            f"→ {reparo.metodo_faltante}"
        )
        try:
            documentos.append(reparar_extracao(reparo, scraped_at=scraped_at))
            print("    ✅ reparado")
        except Exception as exc:
            mensagem = f"{reparo.doc_id}/{reparo.metodo_faltante}: {exc}"
            erros.append(mensagem)
            print(f"    ❌ {mensagem}")

    if not documentos:
        print("\n❌ Nenhum reparo gerou documento válido.")
        return 1

    df_reparos = pd.DataFrame(documentos)
    validar_schema(df_reparos)
    df_final = mesclar_corpus(df_hub, df_reparos)
    restantes = encontrar_reparos(df_final)

    print(f"\nReparos válidos nesta execução: {len(df_reparos)}")
    print(f"IDs ainda assimétricos após merge local: {len(restantes)}")

    if args.dry_run:
        print("[dry-run] Upload pulado.")
    else:
        publicar_corpus(df_final, repo_id=args.repo, mesclar_com_hub=False)

    if erros or restantes:
        print("\n⚠️  Reparo parcial.")
        if erros:
            print("Erros:")
            for erro in erros[:30]:
                print(f"  - {erro}")
        return 1

    print("\n✅ Todos os pares texto/markdown foram reparados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
