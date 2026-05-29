"""Formatacao de contexto para prompts futuros."""

from __future__ import annotations

from typing import Any


def format_contexts(contexts: list[dict[str, Any]]) -> str:
    blocks = []
    for index, context in enumerate(contexts, start=1):
        citation = context.get("citation_label") or context.get("chunk_id")
        text = context.get("texto", "")
        blocks.append(f"[{index}] {citation}\n{text}")
    return "\n\n".join(blocks)
