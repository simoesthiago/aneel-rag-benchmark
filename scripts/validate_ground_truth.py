#!/usr/bin/env python3
"""Valida o ground truth de avaliação local ou publicado no HuggingFace Hub."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Permite rodar como `python scripts/validate_ground_truth.py` na raiz do repo.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.settings import (  # noqa: E402
    GROUND_TRUTH_VERSION,
    HF_DATASET_REPO,
)
from src.evaluation.ground_truth import (  # noqa: E402
    GroundTruthValidationError,
    load_ground_truth_hub,
    validate_ground_truth,
    validate_ground_truth_file,
)
from src.ingestion.uploader import carregar_corpus_hub  # noqa: E402

DEFAULT_LOCAL_PATH = (
    "data/evaluation/ground_truth/aneel_retrieval_50.jsonl"
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida ground truth JSONL")
    parser.add_argument("--path", default=DEFAULT_LOCAL_PATH)
    parser.add_argument("--repo", default=HF_DATASET_REPO)
    parser.add_argument("--version", default=GROUND_TRUTH_VERSION)
    parser.add_argument("--hub", action="store_true", help="Valida artefato no Hub")
    parser.add_argument(
        "--schema-only",
        action="store_true",
        help="Valida apenas JSONL/schema, sem carregar corpus do Hub",
    )
    parser.add_argument("--expected-count", type=int, default=50)
    args = parser.parse_args()

    try:
        if args.hub:
            print(f"Carregando ground truth do Hub ({args.repo}, {args.version})...")
            rows = load_ground_truth_hub(version=args.version, repo_id=args.repo)
            corpus_df = None if args.schema_only else carregar_corpus_hub(args.repo)
            summary = validate_ground_truth(
                rows,
                corpus_df=corpus_df,
                schema_only=args.schema_only,
                expected_count=args.expected_count,
            )
        else:
            corpus_df = None if args.schema_only else carregar_corpus_hub(args.repo)
            summary = validate_ground_truth_file(
                args.path,
                corpus_df=corpus_df,
                schema_only=args.schema_only,
                expected_count=args.expected_count,
            )
    except (GroundTruthValidationError, FileNotFoundError) as exc:
        print(f"\n❌ Ground truth inválido:\n{exc}")
        return 1

    print("\n✅ Ground truth validado.")
    print(f"  Perguntas: {summary['question_count']}")
    print(f"  Documentos únicos: {summary['document_count']}")
    print(f"  corpus_supported: {summary['corpus_supported']}")
    print(f"  source_only: {summary['source_only']}")
    print(f"  needs_review: {summary['needs_review']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
