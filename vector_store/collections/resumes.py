from configs.settings import settings
from vector_store.chroma.collection_manager import get_or_create_collection


class ResumesCollection:
    def __init__(self) -> None:
        self._col = get_or_create_collection(settings.chroma.collection_resumes)

    def add(
        self,
        chunk_id: str,
        text: str,
        embedding: list[float],
        metadata: dict | None = None,
    ) -> None:
        self._col.add(
            ids=[chunk_id],
            documents=[text],
            embeddings=[embedding],
            metadatas=[metadata or {}],
        )

    def search(
        self,
        query_embedding: list[float],
        n_results: int = 5,
        filters: dict | None = None,
    ) -> list[dict]:
        results = self._col.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=filters,
            include=["documents", "metadatas", "distances"],
        )
        return _flatten(results)


def _flatten(results: dict) -> list[dict]:
    output = []
    ids = results.get("ids", [[]])[0]
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]
    for id_, doc, meta, dist in zip(ids, docs, metas, dists):
        output.append({"id": id_, "document": doc, "metadata": meta, "distance": dist})
    return output
