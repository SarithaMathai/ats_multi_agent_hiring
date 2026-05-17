"""
Singleton sentence-transformers wrapper.
Produces float vectors using the embedding model configured in settings.
"""
from __future__ import annotations

from sentence_transformers import SentenceTransformer

from configs.settings import settings


class Embedder:
    """Thread-safe singleton — one model loaded per process."""

    _instance: Embedder | None = None
    _model: SentenceTransformer | None = None

    def __new__(cls) -> Embedder:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            # Strip the "sentence-transformers/" namespace prefix if present
            model_name = settings.llm.embedding_model.replace(
                "sentence-transformers/", ""
            )
            self._model = SentenceTransformer(model_name)
        return self._model

    def embed(self, text: str) -> list[float]:
        """Embed a single string into a float vector."""
        return self._get_model().encode([text], show_progress_bar=False)[0].tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple strings in one forward pass."""
        return self._get_model().encode(texts, show_progress_bar=False).tolist()
