"""RAGRetrievalNode — hybrid dense + sparse retrieval from the chunk table.

No LLM in this node — pure database operation.
Embedding model: voyage-large-2 (to embed the query)
Search: pgvector ANN (dense) + BM25 (sparse) via asyncpg
Timeout: 1000ms

Output: state["retrieved_chunks"] — list[ChunkRef], ranked by hybrid score

Mandatory filters applied on every query (tenant isolation):
  - tenant_id == session.workspace_id
  - project_id == session.project_id
  - is_active == true
  - valid_until IS NULL OR valid_until > now()
"""
from __future__ import annotations

import logging

from ..config import OrchestrationConfig
from ..llm.features import LLMFeature
from ..models.entities import ChunkRef
from ..pipeline.state import PipelineState
from .base import PipelineNode

logger = logging.getLogger(__name__)


class RAGRetrievalNode(PipelineNode):

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
        # TODO(sprint1): implement hybrid retrieval
        # 1. Embed query: client = state["llm_ctx"].get(LLMFeature.EMBEDDING)
        # 2. BM25 candidate retrieval (rank-bm25, in-process or pre-computed)
        # 3. pgvector ANN query with mandatory tenant/project/active filters
        # 4. Hybrid score fusion (bm25_weight from config.rag)
        # 5. Cross-encoder re-rank to config.rag.rerank_top_k
        _ = state["llm_ctx"].get(LLMFeature.EMBEDDING)
        chunks: list[ChunkRef] = []  # placeholder
        logger.debug("RAGRetrieval → %d chunks", len(chunks))
        return {**state, "retrieved_chunks": chunks}
