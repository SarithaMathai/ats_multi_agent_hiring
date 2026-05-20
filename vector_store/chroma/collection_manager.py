import chromadb

from configs.settings import settings
from vector_store.chroma.client import get_chroma_client

# Collection names sourced from settings so they stay in one place
_COLLECTION_NAMES = [
    settings.chroma.collection_candidates,
    settings.chroma.collection_resumes,
    settings.chroma.collection_feedback,
    settings.chroma.collection_interventions,
]

# Metadata applied to each collection at creation time
_COLLECTION_METADATA: dict[str, dict] = {
    settings.chroma.collection_candidates: {"description": "candidate profiles and attributes"},
    settings.chroma.collection_resumes: {"description": "resume text chunks for semantic search"},
    settings.chroma.collection_feedback: {"description": "interview feedback and stage notes"},
    settings.chroma.collection_interventions: {
        "description": "case studies and best practices for improvement recommendations",
        "hnsw:space": "cosine",
    },
}


def get_or_create_collection(name: str) -> chromadb.Collection:
    client = get_chroma_client()
    metadata = _COLLECTION_METADATA.get(name, {})
    # embedding_function=None — we supply pre-computed embeddings ourselves (Day 5).
    # Omitting this causes chromadb to serialize its default ONNX function,
    # which fails with KeyError: '_type' in chromadb 0.5.x.
    return client.get_or_create_collection(
        name=name,
        metadata=metadata,
        embedding_function=None,  # type: ignore[arg-type]
    )


def initialise_all_collections() -> dict[str, chromadb.Collection]:
    collections = {}
    for name in _COLLECTION_NAMES:
        collections[name] = get_or_create_collection(name)
        print(f"  OK collection ready: {name}")
    return collections


def get_collection(name: str) -> chromadb.Collection:
    return get_chroma_client().get_collection(
        name=name,
        embedding_function=None,  # type: ignore[arg-type]
    )
