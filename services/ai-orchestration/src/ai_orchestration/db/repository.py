"""Database operations for documents, chunks, and cost tracking.

All write operations set LOCAL app.tenant_id for row-level security.
The pool is expected to be initialised via db.pool.init_pool() at startup.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import asyncpg

from ..models.entities import ChunkRef

logger = logging.getLogger(__name__)


class DocumentRepository:
    """Wraps asyncpg pool with domain-specific query methods."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ------------------------------------------------------------------
    # Documents
    # ------------------------------------------------------------------

    async def create_document(
        self,
        document_id: uuid.UUID,
        workspace_id: uuid.UUID,
        project_id: uuid.UUID,
        session_id: uuid.UUID,
        filename: str,
        file_hash: str,
        r2_key: str,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"SET LOCAL app.tenant_id = '{workspace_id}'",
            )
            await conn.execute(
                """
                INSERT INTO documents (
                    document_id, workspace_id, project_id, session_id,
                    filename, file_hash, r2_key, status, created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending', NOW(), NOW())
                ON CONFLICT (file_hash, project_id) DO NOTHING
                """,
                document_id,
                workspace_id,
                project_id,
                session_id,
                filename,
                file_hash,
                r2_key,
            )

    async def update_document_status(
        self,
        document_id: uuid.UUID,
        status: str,
        token_count: int | None = None,
        error_message: str | None = None,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE documents
                SET status        = $2,
                    token_count   = COALESCE($3, token_count),
                    error_message = $4,
                    updated_at    = NOW()
                WHERE document_id = $1
                """,
                document_id,
                status,
                token_count,
                error_message,
            )

    async def get_by_hash(
        self,
        file_hash: str,
        project_id: uuid.UUID,
    ) -> uuid.UUID | None:
        """Return document_id of an already-indexed document with the same hash, or None."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT document_id FROM documents
                WHERE file_hash = $1 AND project_id = $2 AND status = 'indexed'
                """,
                file_hash,
                project_id,
            )
        return uuid.UUID(str(row["document_id"])) if row else None

    # ------------------------------------------------------------------
    # Chunks
    # ------------------------------------------------------------------

    async def insert_chunks(
        self,
        chunks: list[dict[str, Any]],
        workspace_id: uuid.UUID,
    ) -> None:
        """Batch-insert document chunks with pgvector embedding and BM25 sparse vector."""
        if not chunks:
            return

        records = [
            (
                chunk["chunk_id"],
                chunk["document_id"],
                chunk["workspace_id"],
                chunk["project_id"],
                chunk["content"],
                chunk["embedding"],
                json.dumps(chunk["sparse_vector"]),
                chunk["chunk_index"],
                chunk["token_count"],
                chunk.get("section_title"),
                chunk.get("page_number"),
            )
            for chunk in chunks
        ]

        async with self._pool.acquire() as conn:
            await conn.execute(f"SET LOCAL app.tenant_id = '{workspace_id}'")
            await conn.executemany(
                """
                INSERT INTO document_chunks (
                    chunk_id, document_id, workspace_id, project_id,
                    content, embedding, sparse_vector,
                    chunk_index, token_count, section_title, page_number,
                    is_active, confidence_modifier, created_at
                )
                VALUES (
                    $1, $2, $3, $4,
                    $5, $6, $7::jsonb,
                    $8, $9, $10, $11,
                    TRUE, 1.0, NOW()
                )
                ON CONFLICT (chunk_id) DO NOTHING
                """,
                records,
            )
        logger.debug("Inserted %d chunks for workspace=%s", len(chunks), workspace_id)

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    async def hybrid_search(
        self,
        query_embedding: list[float],
        bm25_tokens: dict[str, float],
        workspace_id: uuid.UUID,
        project_id: uuid.UUID,
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3,
        top_k: int = 20,
    ) -> list[ChunkRef]:
        """Call the hybrid_search() SQL function and map rows to ChunkRef."""
        async with self._pool.acquire() as conn:
            await conn.execute(f"SET LOCAL app.tenant_id = '{workspace_id}'")
            rows = await conn.fetch(
                """
                SELECT * FROM hybrid_search(
                    $1::vector, $2::jsonb, $3, $4, $5, $6, $7
                )
                """,
                query_embedding,
                json.dumps(bm25_tokens),
                workspace_id,
                project_id,
                dense_weight,
                sparse_weight,
                top_k,
            )

        return [
            ChunkRef(
                chunk_id=uuid.UUID(str(row["chunk_id"])),
                content=row["content"],
                score=float(row["score"]),
                section_title=row.get("section_title"),
                page_number=row.get("page_number"),
                trust_tier=int(row.get("trust_tier", 3)),
                document_id=uuid.UUID(str(row["document_id"])) if row.get("document_id") else None,
                source_type=str(row.get("source_type", "pdf")),
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Cost tracking
    # ------------------------------------------------------------------

    async def log_cost(
        self,
        workspace_id: uuid.UUID,
        session_id: uuid.UUID,
        llm_feature: str,
        model_id: str,
        cost_usd: float,
        budget_stage: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO cost_log (
                    log_id, workspace_id, session_id,
                    llm_feature, model_id, cost_usd, budget_stage,
                    input_tokens, output_tokens, created_at
                )
                VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $6, $7, $8, NOW())
                """,
                workspace_id,
                session_id,
                llm_feature,
                model_id,
                cost_usd,
                budget_stage,
                input_tokens,
                output_tokens,
            )
