"""
Formats RetrievedChunk lists into a readable context string for agent prompts.

Budget accounting: ~4 characters per token (rough but sufficient for prompt sizing).
"""
from __future__ import annotations

from rag.retriever.types import RetrievedChunk

_CHARS_PER_TOKEN = 4


def build_context_string(
    chunks: list[RetrievedChunk],
    max_tokens: int = 2000,
) -> str:
    """Render *chunks* as a numbered evidence block within a character budget.

    Args:
        chunks:     Retrieved chunks, typically from ChromaRetriever.retrieve().
        max_tokens: Approximate token budget. Chunks beyond the budget are omitted.

    Returns:
        A multi-line string ready to inject into an agent system or user prompt.
    """
    if not chunks:
        return "No relevant context found."

    max_chars = max_tokens * _CHARS_PER_TOKEN
    lines: list[str] = ["=== Retrieved Context ==="]
    used = len(lines[0])

    for i, chunk in enumerate(chunks, start=1):
        similarity = 1.0 - chunk.distance
        header = f"\n[{i}] similarity={similarity:.2f} | collection={chunk.collection_name}"
        body = chunk.document.strip()
        entry = f"{header}\n{body}\n"

        if used + len(entry) > max_chars:
            remaining = len(chunks) - i + 1
            lines.append(
                f"\n[... {remaining} more chunk(s) omitted — token budget reached]"
            )
            break

        lines.append(entry)
        used += len(entry)

    return "".join(lines)


def build_multi_collection_context(
    chunks_by_collection: dict[str, list[RetrievedChunk]],
    max_tokens: int = 3000,
) -> str:
    """Render evidence from multiple collections into labelled sections.

    Distributes the token budget evenly across collections so no single
    collection dominates the prompt.

    Args:
        chunks_by_collection: Dict mapping collection name → list of chunks.
                              Typically from ChromaRetriever.retrieve_multi().
        max_tokens:           Total token budget across all sections.

    Returns:
        A multi-line string with one labelled section per collection.
    """
    if not chunks_by_collection:
        return "No relevant context found."

    n = max(len(chunks_by_collection), 1)
    budget = max_tokens // n
    sections: list[str] = []

    for name, chunks in chunks_by_collection.items():
        section = build_context_string(chunks, max_tokens=budget)
        sections.append(f"--- {name} ---\n{section}")

    return "\n\n".join(sections)
