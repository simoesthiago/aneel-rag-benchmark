#!/usr/bin/env python3
"""Publica o ground truth versionado no HuggingFace Hub."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Permite rodar como `python scripts/publish_ground_truth.py` na raiz do repo.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.settings import (  # noqa: E402
    GROUND_TRUTH_VERSION,
    HF_DATASET_REPO,
)
from src.evaluation.ground_truth import (  # noqa: E402
    GroundTruthValidationError,
    load_ground_truth_jsonl,
    publish_ground_truth,
    validate_ground_truth,
)
from src.ingestion.uploader import carregar_corpus_hub  # noqa: E402

DEFAULT_LOCAL_PATH = (
    "data/evaluation/ground_truth/aneel_retrieval_50.jsonl"
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Publica ground truth no Hub")
    parser.add_argument("--path", default=DEFAULT_LOCAL_PATH)
    parser.add_argument("--repo", default=HF_DATASET_REPO)
    parser.add_argument("--version", default=GROUND_TRUTH_VERSION)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Sobrescreve a versão se ela já existir no Hub",
    )
    args = parser.parse_args()

    try:
        rows = load_ground_truth_jsonl(args.path)
        corpus_df = carregar_corpus_hub(args.repo)
        summary = validate_ground_truth(rows, corpus_df=corpus_df, expected_count=50)
        url = publish_ground_truth(
            args.path,
            rows=rows,
            version=args.version,
            repo_id=args.repo,
            force=args.force,
        )
    except (GroundTruthValidationError, FileNotFoundError) as exc:
        print(f"\n❌ Publicação cancelada:\n{exc}")
        return 1

    print("\n✅ Ground truth publicado.")
    print(f"  URL: {url}")
    print(f"  Versão: {args.version}")
    print(f"  Perguntas: {summary['question_count']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
