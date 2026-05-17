"""
Semantic similarity retrieval from ChromaDB.

Returns structured RetrievedChunk objects that agents pass to context_builder
to assemble the grounding context for their LLM prompts.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from rag.embeddings.embedder import Embedder
from vector_store.chroma.collection_manager import get_collection


@dataclass
class RetrievedChunk:
    id: str
    document: str
    metadata: dict = field(default_factory=dict)
    distance: float = 0.0
    collection_name: str = ""


class ChromaRetriever:
    def __init__(self) -> None:
        self._embedder = Embedder()

    def retrieve(
        self,
        query: str,
        collection_name: str,
        n_results: int = 5,
        filters: dict | None = None,
    ) -> list[RetrievedChunk]:
        """Return the top-*n_results* semantically similar documents for *query*.

        Args:
            query:           Natural-language question or issue description.
            collection_name: ChromaDB collection to search (use settings.chroma.*).
            n_results:       Maximum number of chunks to return.
            filters:         Optional ChromaDB `where` filter dict for metadata.

        Returns:
            List of RetrievedChunk ordered by ascending distance (most similar first).
        """
        query_embedding = self._embedder.embed(query)
        collection = get_collection(collection_name)

        kwargs: dict = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if filters:
            kwargs["where"] = filters

        result = collection.query(**kwargs)

        ids       = result.get("ids",       [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        return [
            RetrievedChunk(
                id=doc_id,
                document=doc or "",
                metadata=meta or {},
                distance=dist,
                collection_name=collection_name,
            )
            for doc_id, doc, meta, dist in zip(ids, documents, metadatas, distances)
        ]

    def retrieve_multi(
        self,
        query: str,
        collection_names: list[str],
        n_results_per_collection: int = 3,
        filters: dict | None = None,
    ) -> dict[str, list[RetrievedChunk]]:
        """Retrieve from multiple collections in one call.

        Returns a dict keyed by collection name for use with
        context_builder.build_multi_collection_context().
        """
        return {
            name: self.retrieve(query, name, n_results_per_collection, filters)
            for name in collection_names
        }
