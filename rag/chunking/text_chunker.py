"""
Splits long text into overlapping chunks suitable for embedding.

Two strategies:
  fixed_size  — split by character count with configurable overlap
  paragraph   — split on blank lines, merge short paragraphs together
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TextChunk:
    text: str
    chunk_index: int
    total_chunks: int
    start_char: int
    end_char: int


def chunk_fixed_size(
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[TextChunk]:
    """Split *text* into fixed-size character chunks with *overlap* chars of context carry-over."""
    if not text:
        return []

    chunks: list[TextChunk] = []
    start = 0
    idx = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        # Extend to the next word boundary so we don't cut mid-word
        if end < len(text):
            while end < len(text) and text[end] not in (" ", "\n"):
                end += 1

        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append(TextChunk(
                text=chunk_text,
                chunk_index=idx,
                total_chunks=0,       # back-filled below
                start_char=start,
                end_char=end,
            ))
            idx += 1

        next_start = end - overlap
        if next_start <= start:       # guard against infinite loop on tiny texts
            break
        start = next_start

    for chunk in chunks:
        chunk.total_chunks = len(chunks)
    return chunks


def chunk_by_paragraph(
    text: str,
    min_chars: int = 100,
    max_chars: int = 1500,
) -> list[TextChunk]:
    """Split on blank lines, merging short paragraphs until they reach *min_chars*."""
    if not text:
        return []

    raw = [p.strip() for p in text.split("\n\n") if p.strip()]

    merged: list[str] = []
    buffer = ""

    for para in raw:
        if buffer:
            combined = buffer + "\n\n" + para
            if len(combined) <= max_chars:
                buffer = combined
            else:
                merged.append(buffer)
                buffer = para
        else:
            buffer = para

    if buffer:
        merged.append(buffer)

    chunks = [
        TextChunk(
            text=p,
            chunk_index=i,
            total_chunks=len(merged),
            start_char=0,
            end_char=len(p),
        )
        for i, p in enumerate(merged)
        if len(p) >= min_chars
    ]
    return chunks
