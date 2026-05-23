"""RAGRetrievalNode — hybrid dense + sparse retrieval from the chunk table.

No LLM in this node — pure database operation.

Steps:
  1. Embed the user message using voyage-large-2 (input_type='query').
  2. Build a BM25 sparse vector from the query tokens.
  3. Call hybrid_search() SQL function via asyncpg (mandatory tenant/project filter).
  4. Return state["retrieved_chunks"] as list[ChunkRef] ranked by hybrid score.

Timeout: 1 000 ms (config.orchestration.pipeline.timeout_ms.rag_retrieval).
On timeout or DB error: returns empty list and writes to node_errors (never raises).

Mandatory filters enforced inside hybrid_search() SQL function:
  - workspace_id (tenant isolation via RLS)
  - project_id
  - is_active = TRUE
  - valid_until IS NULL OR valid_until > now()
"""
from __future__ import annotations

import logging
import uuid

from ..config import OrchestrationConfig
from ..db.pool import get_pool
from ..db.repository import DocumentRepository
from ..ingestion.embedder import Embedder
from ..ingestion.pipeline import _bm25_sparse
from ..models.entities import ChunkRef
from ..pipeline.state import PipelineState
from .base import PipelineNode

logger = logging.getLogger(__name__)


class RAGRetrievalNode(PipelineNode):
    """Retrieves relevant document chunks using hybrid dense + sparse search."""

    def __init__(self, config: OrchestrationConfig) -> None:
        super().__init__(config)
        self._embedder = Embedder(batch_size=config.ingestion.embedding_batch_size)

    @property
    def timeout_ms(self) -> int:
        return self._config.orchestration.pipeline.timeout_ms.rag_retrieval

    async def __call__(self, state: PipelineState) -> PipelineState:
        return await self._run_with_timeout(
            self._retrieve(state),
            state,
            default={**state, "retrieved_chunks": []},
        )

    async def _retrieve(self, state: PipelineState) -> PipelineState:
        session = state["session_state"]
        query = state["user_message"]

        workspace_id = _extract_uuid(session, "workspace_id")
        project_id = _extract_uuid(session, "project_id")

        # No documents indexed yet — skip DB round-trip
        docs_indexed = _get_list(session, "documents_indexed")
        if not docs_indexed:
            logger.debug("RAGRetrieval skipped — no documents indexed for project=%s", project_id)
            return {**state, "retrieved_chunks": []}

        # 1. Embed query
        query_embedding = await self._embedder.embed_query(query)

        # 2. Build sparse tokens
        bm25_tokens = _bm25_sparse(query.lower().split())

        # 3. Query database
        pool = await get_pool()
        repo = DocumentRepository(pool)

        chunks = await repo.hybrid_search(
            query_embedding=query_embedding,
            bm25_tokens=bm25_tokens,
            workspace_id=workspace_id,
            project_id=project_id,
            dense_weight=self._config.rag.dense_weight,
            sparse_weight=self._config.rag.bm25_weight,
            top_k=self._config.rag.top_k,
        )

        logger.debug(
            "RAGRetrieval → %d chunks (workspace=%s project=%s)",
            len(chunks),
            workspace_id,
            project_id,
        )
        return {**state, "retrieved_chunks": chunks}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_uuid(session: object, field: str) -> uuid.UUID:
    val = session.get(field, "") if isinstance(session, dict) else getattr(session, field, "")
    try:
        return uuid.UUID(str(val))
    except (ValueError, AttributeError):
        return uuid.uuid4()


def _get_list(session: object, field: str) -> list:
    if isinstance(session, dict):
        return session.get(field, []) or []
    return list(getattr(session, field, []) or [])
