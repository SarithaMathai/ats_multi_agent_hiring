from __future__ import annotations

import chromadb
from chromadb.config import Settings

from configs.settings import settings

_client: chromadb.HttpClient | None = None


def get_chroma_client() -> chromadb.HttpClient:
    global _client
    if _client is None:
        _client = chromadb.HttpClient(
            host=settings.chroma.host,
            port=settings.chroma.port,
            # v2 API defaults
            tenant=chromadb.DEFAULT_TENANT,
            database=chromadb.DEFAULT_DATABASE,
            settings=Settings(
                chroma_client_auth_provider="chromadb.auth.token_authn.TokenAuthClientProvider",
                chroma_client_auth_credentials=settings.chroma.token,
                anonymized_telemetry=False,   # suppress posthog version-mismatch warning
            ),
        )
    return _client
