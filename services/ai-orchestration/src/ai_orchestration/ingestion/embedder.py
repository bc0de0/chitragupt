"""Voyage AI embedding client for the ingestion pipeline.

Wraps voyageai.AsyncClient with batching so large document sets don't exceed
the API's per-request limit. The same voyage-large-2 model used at query time
is used here so embedding spaces are identical.

Usage:
    embedder = Embedder(batch_size=128)
    vectors = await embedder.embed_texts(["chunk 1 text", "chunk 2 text"])
    query_vec = await embedder.embed_query("what is the budget?")
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_EMBEDDING_MODEL = "voyage-large-2"
_DIMENSION = 1024


class Embedder:
    """Batched async wrapper around voyageai.AsyncClient."""

    def __init__(self, batch_size: int = 128) -> None:
        self._batch_size = batch_size
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            import voyageai  # noqa: PLC0415
            self._client = voyageai.AsyncClient()
        return self._client

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of document chunks (input_type='document')."""
        if not texts:
            return []

        client = self._get_client()
        results: list[list[float]] = []

        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            response = await client.embed(batch, model=_EMBEDDING_MODEL, input_type="document")
            results.extend(response.embeddings)

        logger.debug("Embedded %d texts in %d batches", len(texts), -(-len(texts) // self._batch_size))
        return results

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single retrieval query (input_type='query')."""
        client = self._get_client()
        response = await client.embed([text], model=_EMBEDDING_MODEL, input_type="query")
        return response.embeddings[0]
