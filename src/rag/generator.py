"""Geracao simples e deterministica para MVP offline."""

from __future__ import annotations

from typing import Any


def generate_extractive_answer(contexts: list[dict[str, Any]]) -> str:
    if not contexts:
        return "Nao encontrei base suficiente no corpus para responder."
    snippets = []
    for context in contexts[:3]:
        text = " ".join(str(context.get("texto", "")).split())
        snippets.append(text[:500])
    return "\n\n".join(snippets)
