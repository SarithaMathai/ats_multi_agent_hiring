"""Lightweight types for the RAG retriever layer — no heavy dependencies."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RetrievedChunk:
    id: str
    document: str
    metadata: dict = field(default_factory=dict)
    distance: float = 0.0
    collection_name: str = ""
