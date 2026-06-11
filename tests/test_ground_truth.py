import json
from pathlib import Path

import pandas as pd
import pytest


def _source(
    *,
    document_id: str = "doc-1",
    url: str = "https://example.com/doc-1.pdf",
    support_excerpt: str = (
        "A produção, transmissão e distribuição de energia elétrica devem "
        "ser reguladas e fiscalizadas."
    ),
) -> dict:
    return {
        "document_id": document_id,
        "titulo": "Documento 1",
        "citation_label": "Documento 1, Art. 1o",
        "section_label": "Art. 1o",
        "url": url,
        "support_excerpt": support_excerpt,
        "relevance": 3,
    }


def _question(**overrides) -> dict:
    base = {
        "question_id": "gt-0001",
        "question": "O que deve ser regulado e fiscalizado?",
        "expected_answer": (
            "A produção, transmissão e distribuição de energia elétrica "
            "devem ser reguladas e fiscalizadas."
        ),
        "query_type": "definicao",
        "difficulty": "facil",
        "answerability": "corpus_supported",
        "tipo": "lei",
        "subtipo": "lei_federal",
        "relevant_sources": [_source()],
        "notes": "",
    }
    base.update(overrides)
    return base


def _corpus_df(texto: str | None = None) -> pd.DataFrame:
    texto = texto or (
        "A produçăo, transmissăo e distribuiçăo de energia elétrica devem "
        "ser reguladas e fiscalizadas."
    )
    return pd.DataFrame(
        [
            {
                "id": "doc-1",
                "tipo": "lei",
                "subtipo": "lei_federal",
                "url_original": "https://example.com/doc-1.pdf",
                "url_consolidado": None,
                "metodo_extracao": "texto",
                "texto_bruto": texto,
            }
        ]
    )


def test_load_ground_truth_jsonl_carrega_linhas_validas(tmp_path: Path):
    from src.evaluation.ground_truth import load_ground_truth_jsonl

    path = tmp_path / "ground_truth.jsonl"
    path.write_text(json.dumps(_question(), ensure_ascii=False) + "\n", encoding="utf-8")

    rows = load_ground_truth_jsonl(path)

    assert rows == [_question()]


def test_load_ground_truth_jsonl_falha_com_json_invalido(tmp_path: Path):
    from src.evaluation.ground_truth import GroundTruthValidationError, load_ground_truth_jsonl

    path = tmp_path / "ground_truth.jsonl"
    path.write_text('{"question_id": "gt-0001"\n', encoding="utf-8")

    with pytest.raises(GroundTruthValidationError, match="linha 1"):
        load_ground_truth_jsonl(path)


def test_validate_ground_truth_schema_bloqueia_campos_invalidos():
    from src.evaluation.ground_truth import GroundTruthValidationError, validate_ground_truth

    row = _question()
    del row["expected_answer"]

    with pytest.raises(GroundTruthValidationError, match="expected_answer"):
        validate_ground_truth([row], schema_only=True, expected_count=1)


def test_validate_ground_truth_bloqueia_chunk_id_recursivo():
    from src.evaluation.ground_truth import GroundTruthValidationError, validate_ground_truth

    row = _question(relevant_sources=[_source() | {"chunk_id": "doc-1::markdown::0"}])

    with pytest.raises(GroundTruthValidationError, match="chunk_id"):
        validate_ground_truth([row], schema_only=True, expected_count=1)


def test_validate_ground_truth_exige_ids_sequenciais():
    from src.evaluation.ground_truth import GroundTruthValidationError, validate_ground_truth

    row = _question(question_id="gt-0002")

    with pytest.raises(GroundTruthValidationError, match="gt-0001"):
        validate_ground_truth([row], schema_only=True, expected_count=1)


def test_validate_ground_truth_confere_catalogo_e_texto_do_corpus():
    from src.evaluation.ground_truth import validate_ground_truth

    summary = validate_ground_truth([_question()], corpus_df=_corpus_df(), expected_count=1)

    assert summary["question_count"] == 1
    assert summary["corpus_supported"] == 1


def test_validate_ground_truth_falha_quando_document_id_nao_existe():
    from src.evaluation.ground_truth import GroundTruthValidationError, validate_ground_truth

    row = _question(relevant_sources=[_source(document_id="doc-inexistente")])

    with pytest.raises(GroundTruthValidationError, match="doc-inexistente"):
        validate_ground_truth([row], corpus_df=_corpus_df(), expected_count=1)


def test_validate_ground_truth_falha_quando_url_nao_bate_catalogo():
    from src.evaluation.ground_truth import GroundTruthValidationError, validate_ground_truth

    row = _question(relevant_sources=[_source(url="https://example.com/outro.pdf")])

    with pytest.raises(GroundTruthValidationError, match="URL"):
        validate_ground_truth([row], corpus_df=_corpus_df(), expected_count=1)


def test_validate_ground_truth_exige_support_excerpt_para_corpus_supported():
    from src.evaluation.ground_truth import GroundTruthValidationError, validate_ground_truth

    row = _question(
        relevant_sources=[
            _source(
                support_excerpt=(
                    "Trecho completamente ausente da base textual extraída do documento."
                )
            )
        ]
    )

    with pytest.raises(GroundTruthValidationError, match="support_excerpt"):
        validate_ground_truth([row], corpus_df=_corpus_df(), expected_count=1)


def test_validate_ground_truth_source_only_nao_exige_trecho_no_corpus():
    from src.evaluation.ground_truth import validate_ground_truth

    row = _question(
        answerability="source_only",
        expected_answer="Trecho documentado apenas na fonte oficial.",
        relevant_sources=[
            _source(
                support_excerpt="Trecho documentado apenas na fonte oficial."
            )
        ],
    )

    summary = validate_ground_truth([row], corpus_df=_corpus_df(), expected_count=1)

    assert summary["source_only"] == 1


def test_text_coverage_normaliza_encoding_do_planalto():
    from src.evaluation.ground_truth import text_coverage

    coverage, missing = text_coverage(
        "produção, transmissão e distribuição",
        "produçăo, transmissăo e distribuiçăo",
    )

    assert coverage == 1.0
    assert missing == []


def test_informative_tokens_preserva_siglas_regulatorias_curtas():
    from src.evaluation.ground_truth import informative_tokens

    tokens = informative_tokens(
        "DEC FEC DIC FIC DMIC REN ONS TE PCH ENA EAR GSF "
        "ICMS PIS COFINS kV kW MWh GWh ANEEL PRODIST"
    )

    assert "dec" in tokens
    assert "fec" in tokens
    assert "dic" in tokens
    assert "fic" in tokens
    assert "dmic" in tokens
    assert "ren" in tokens
    assert "ons" in tokens
    assert "te" in tokens
    assert "pch" in tokens
    assert "ena" in tokens
    assert "ear" in tokens
    assert "gsf" in tokens
    assert "icms" in tokens
    assert "pis" in tokens
    assert "cofins" in tokens
    assert "kv" in tokens
    assert "kw" in tokens
    assert "mwh" in tokens
    assert "gwh" in tokens


def test_build_ground_truth_manifest_inclui_hash_e_validacao(tmp_path: Path):
    from src.evaluation.ground_truth import build_ground_truth_manifest

    path = tmp_path / "ground_truth.jsonl"
    path.write_text(json.dumps(_question(), ensure_ascii=False) + "\n", encoding="utf-8")

    manifest = build_ground_truth_manifest(
        path,
        rows=[_question()],
        version="retrieval-50",
        repo_id="simoesthiago/aneel-corpus",
        created_at="2026-06-05T00:00:00Z",
    )

    assert manifest["artifact_type"] == "ground_truth"
    assert manifest["version"] == "retrieval-50"
    assert manifest["question_count"] == 1
    assert len(manifest["sha256"]) == 64


def test_publish_ground_truth_publica_jsonl_e_manifest_com_paths_corretos(tmp_path: Path):
    from src.evaluation import ground_truth

    class FakeApi:
        def __init__(self):
            self.files = []
            self.operations = None

        def list_repo_files(self, repo_id, repo_type):
            return self.files

        def create_commit(self, **kwargs):
            self.operations = kwargs["operations"]

    path = tmp_path / "ground_truth.jsonl"
    path.write_text(json.dumps(_question(), ensure_ascii=False) + "\n", encoding="utf-8")
    fake_api = FakeApi()

    url = ground_truth.publish_ground_truth(
        path,
        rows=[_question()],
        version="retrieval-50",
        repo_id="simoesthiago/aneel-corpus",
        api=fake_api,
    )

    paths = [operation.path_in_repo for operation in fake_api.operations]
    assert url == "https://huggingface.co/datasets/simoesthiago/aneel-corpus"
    assert paths == [
        "data/evaluation/ground_truth/version=retrieval-50/ground_truth.jsonl",
        "data/evaluation/ground_truth/version=retrieval-50/manifest.json",
    ]


def test_publish_ground_truth_recusa_sobrescrever_sem_force(tmp_path: Path):
    from src.evaluation.ground_truth import GroundTruthValidationError, publish_ground_truth

    class FakeApi:
        def list_repo_files(self, repo_id, repo_type):
            return [
                "data/evaluation/ground_truth/version=retrieval-50/ground_truth.jsonl",
            ]

    path = tmp_path / "ground_truth.jsonl"
    path.write_text(json.dumps(_question(), ensure_ascii=False) + "\n", encoding="utf-8")

    with pytest.raises(GroundTruthValidationError, match="já existe"):
        publish_ground_truth(
            path,
            rows=[_question()],
            version="retrieval-50",
            repo_id="simoesthiago/aneel-corpus",
            api=FakeApi(),
        )


def _corpus_df_cross_tipo() -> pd.DataFrame:
    texto = (
        "A produçăo, transmissăo e distribuiçăo de energia elétrica devem "
        "ser reguladas e fiscalizadas."
    )
    return pd.DataFrame(
        [
            {
                "id": "doc-1",
                "tipo": "lei",
                "subtipo": "lei_federal",
                "url_original": "https://example.com/doc-1.pdf",
                "url_consolidado": None,
                "metodo_extracao": "texto",
                "texto_bruto": texto,
            },
            {
                "id": "doc-2",
                "tipo": "procedimento",
                "subtipo": "proret",
                "url_original": "https://example.com/doc-2.pdf",
                "url_consolidado": None,
                "metodo_extracao": "texto",
                "texto_bruto": texto,
            },
        ]
    )


def _cross_tipo_source(*, tipo_override: bool) -> dict:
    fonte = _source(document_id="doc-2", url="https://example.com/doc-2.pdf")
    fonte["group"] = "g1"
    if tipo_override:
        fonte["tipo"] = "procedimento"
        fonte["subtipo"] = "proret"
    return fonte


def test_validate_aceita_fonte_cross_tipo_com_override_por_fonte():
    # any_of: fonte alternativa de OUTRO tipo (procedimento) numa pergunta lei,
    # carregando `tipo`/`subtipo` próprios -> passa.
    from src.evaluation.ground_truth import validate_ground_truth

    fonte_principal = _source()
    fonte_principal["group"] = "g1"
    row = _question(
        relevant_sources=[fonte_principal, _cross_tipo_source(tipo_override=True)]
    )
    summary = validate_ground_truth(
        [row], corpus_df=_corpus_df_cross_tipo(), expected_count=1
    )
    assert summary["question_count"] == 1


def test_validate_rejeita_fonte_cross_tipo_sem_override():
    # Sem o override por-fonte, a fonte procedimento diverge do tipo lei da
    # linha -> erro de tipo (comportamento estrito preservado).
    from src.evaluation.ground_truth import (
        GroundTruthValidationError,
        validate_ground_truth,
    )

    fonte_principal = _source()
    fonte_principal["group"] = "g1"
    row = _question(
        relevant_sources=[fonte_principal, _cross_tipo_source(tipo_override=False)]
    )
    with pytest.raises(GroundTruthValidationError, match="tipo diverge"):
        validate_ground_truth(
            [row], corpus_df=_corpus_df_cross_tipo(), expected_count=1
        )
