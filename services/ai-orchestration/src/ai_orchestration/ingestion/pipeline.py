"""IngestionPipeline — end-to-end document processing.

Flow per document:
  1. Set Redis status → "ingesting"
  2. Extract text from bytes (PDF / DOCX / TXT) via DocumentProcessor
  3. Split into overlapping windows via Chunker
  4. Optionally scrub PII with regex patterns
  5. Embed all chunks in batches via Embedder (voyage-large-2)
  6. Compute lightweight BM25 sparse vectors for hybrid search
  7. Batch-insert chunk records into PostgreSQL via DocumentRepository
  8. Set document status → "indexed", set Redis status → "indexed"
  9. Publish "indexed" event to Redis pub/sub channel

Redis keys (from REDIS_SCHEMA.md):
  doc:{workspace_id}:{document_id}:status   — pending | ingesting | indexed | failed
  doc:{workspace_id}:{document_id}:error    — error message (on failure only)
  events:{workspace_id}:{document_id}:indexed — pub/sub notification
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from ..config import IngestionConfig
from ..db.repository import DocumentRepository
from .chunker import Chunker
from .document_processor import DocumentProcessor
from .embedder import Embedder

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PII redaction patterns
# ---------------------------------------------------------------------------

_PII_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[EMAIL]"),
    (re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[PHONE]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    (re.compile(r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14})\b"), "[CARD]"),
]


def _scrub_pii(text: str) -> str:
    for pattern, replacement in _PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


# ---------------------------------------------------------------------------
# BM25 sparse vector construction
# ---------------------------------------------------------------------------

def _bm25_sparse(tokens: list[str]) -> dict[str, float]:
    """Compute normalised term-frequency sparse vector for BM25 hybrid search.

    The stored JSON {term: weight} is consumed by the hybrid_search() SQL function
    to compute sparse similarity against query tokens.
    """
    freq: dict[str, int] = {}
    for token in tokens:
        t = token.lower()
        freq[t] = freq.get(t, 0) + 1
    total = len(tokens) or 1
    return {t: count / total for t, count in freq.items()}


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class IngestionPipeline:
    """Orchestrates the full document ingestion flow."""

    def __init__(
        self,
        repo: DocumentRepository,
        config: IngestionConfig,
        redis: Any | None = None,
    ) -> None:
        self._repo = repo
        self._config = config
        self._redis = redis
        self._processor = DocumentProcessor()
        self._chunker = Chunker(
            chunk_size_tokens=config.chunk_size_tokens,
            overlap_tokens=config.chunk_overlap_tokens,
            min_tokens=config.min_chunk_tokens,
        )
        self._embedder = Embedder(batch_size=config.embedding_batch_size)

    async def run(
        self,
        document_id: uuid.UUID,
        workspace_id: uuid.UUID,
        project_id: uuid.UUID,
        session_id: uuid.UUID,
        content: bytes,
        filename: str,
    ) -> None:
        await self._set_redis_status(workspace_id, document_id, "ingesting")
        try:
            total_tokens = await self._ingest(
                document_id, workspace_id, project_id, content, filename
            )
            await self._repo.update_document_status(
                document_id, "indexed", token_count=total_tokens
            )
            await self._set_redis_status(workspace_id, document_id, "indexed")
            await self._publish_indexed(workspace_id, document_id)
            logger.info(
                "Ingestion complete: document=%s tokens=%d chunks=?",
                document_id,
                total_tokens,
            )
        except Exception as exc:
            logger.exception("Ingestion failed for document %s", document_id)
            await self._repo.update_document_status(
                document_id, "failed", error_message=str(exc)
            )
            await self._set_redis_status(workspace_id, document_id, "failed", str(exc))

    # ------------------------------------------------------------------
    # Internal steps
    # ------------------------------------------------------------------

    async def _ingest(
        self,
        document_id: uuid.UUID,
        workspace_id: uuid.UUID,
        project_id: uuid.UUID,
        content: bytes,
        filename: str,
    ) -> int:
        # 1. Extract
        pages = self._processor.process(content, filename)
        logger.info("Extracted %d pages from '%s'", len(pages), filename)

        # 2. Chunk
        chunks = self._chunker.chunk(pages)
        if not chunks:
            logger.warning("No chunks produced for document %s", document_id)
            return 0

        # 3. PII scrub
        if self._config.pii_scrub_enabled:
            for chunk in chunks:
                chunk.text = _scrub_pii(chunk.text)

        # 4. Embed
        texts = [c.text for c in chunks]
        embeddings = await self._embedder.embed_texts(texts)

        total_tokens = sum(c.token_count for c in chunks)

        # 5. Build records
        records = [
            {
                "chunk_id": uuid.uuid4(),
                "document_id": document_id,
                "workspace_id": workspace_id,
                "project_id": project_id,
                "content": chunk.text,
                "embedding": embedding,
                "sparse_vector": _bm25_sparse(chunk.text.split()),
                "chunk_index": chunk.chunk_index,
                "token_count": chunk.token_count,
                "section_title": chunk.section_title,
                "page_number": chunk.page_number,
            }
            for chunk, embedding in zip(chunks, embeddings)
        ]

        # 6. Persist
        await self._repo.insert_chunks(records, workspace_id)
        return total_tokens

    async def _set_redis_status(
        self,
        workspace_id: uuid.UUID,
        document_id: uuid.UUID,
        status: str,
        error: str | None = None,
    ) -> None:
        if self._redis is None:
            return
        key = f"doc:{workspace_id}:{document_id}:status"
        await self._redis.set(key, status)
        if error:
            await self._redis.set(
                f"doc:{workspace_id}:{document_id}:error",
                error[:500],
            )

    async def _publish_indexed(
        self,
        workspace_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> None:
        if self._redis is None:
            return
        channel = f"events:{workspace_id}:{document_id}:indexed"
        await self._redis.publish(channel, "indexed")
