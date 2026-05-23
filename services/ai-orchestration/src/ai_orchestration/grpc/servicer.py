"""AiOrchestrationServicer — gRPC server implementation.

Implements the AiOrchestration service from ai_orchestration.proto.
Called by the Go API gateway for every BA turn and document ingestion request.

Generated proto imports (produced by scripts/generate_proto.sh):
  ai_orchestration_pb2, ai_orchestration_pb2_grpc
  common_pb2
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import AsyncIterator

from ..config import OrchestrationConfig
from ..db.pool import get_pool
from ..db.repository import DocumentRepository
from ..executor import PipelineAbortedError, PipelineExecutor
from ..ingestion.pipeline import IngestionPipeline
from ..llm.context import SessionLLMContextFactory

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Import generated proto stubs — fall back gracefully if not yet generated.
# ---------------------------------------------------------------------------

try:
    from . import ai_orchestration_pb2 as pb2          # type: ignore[attr-defined]
    from . import ai_orchestration_pb2_grpc as pb2_grpc  # type: ignore[attr-defined]
    from . import common_pb2                            # type: ignore[attr-defined]
    _PROTO_AVAILABLE = True
except ImportError:
    logger.warning(
        "Proto stubs not found — run scripts/generate_proto.sh to generate them. "
        "The gRPC servicer will not function until stubs are present."
    )
    _PROTO_AVAILABLE = False
    pb2 = None            # type: ignore[assignment]
    pb2_grpc = None       # type: ignore[assignment]
    common_pb2 = None     # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Servicer
# ---------------------------------------------------------------------------

class AiOrchestrationServicer:
    """
    gRPC servicer for the Python AI Orchestration service.

    Instantiated once at startup; all state is passed via request messages.
    """

    def __init__(
        self,
        config: OrchestrationConfig,
        redis: object | None = None,
    ) -> None:
        self._config  = config
        self._redis   = redis
        self._executor = PipelineExecutor(config)
        self._factory  = SessionLLMContextFactory(config, redis=redis)

    # ------------------------------------------------------------------
    # RunPipeline — streaming
    # ------------------------------------------------------------------

    async def RunPipeline(
        self,
        request: object,
        context: object,
    ) -> AsyncIterator[object]:
        """
        Execute one BA turn through the LangGraph pipeline.

        Yields:
          - token events (one per guidance token)
          - a single TurnComplete event at the end
        """
        if not _PROTO_AVAILABLE:
            logger.error("RunPipeline called but proto stubs not generated")
            return

        session_state = _proto_session_to_dict(request.session_state)  # type: ignore[union-attr]
        user_message  = request.user_message                            # type: ignore[union-attr]

        llm_ctx = await self._factory.for_turn(session_state)

        try:
            async for token in self._executor.run(session_state, user_message, llm_ctx):
                yield pb2.PipelineEvent(token=token)
        except PipelineAbortedError as exc:
            result = self._executor.last_result
            if result:
                yield pb2.PipelineEvent(complete=_build_turn_complete(result, pb2, common_pb2))
            return

        result = self._executor.last_result
        if result:
            yield pb2.PipelineEvent(complete=_build_turn_complete(result, pb2, common_pb2))

        logger.info(
            "RunPipeline complete — intent=%s cost=%.4f",
            result.intent if result else "?",
            result.cost_usd if result else 0.0,
        )

    # ------------------------------------------------------------------
    # IngestDocument — fire-and-forget
    # ------------------------------------------------------------------

    async def IngestDocument(self, request: object, context: object) -> object:
        """
        Accept a document and enqueue ingestion.

        The ingestion runs as a background asyncio task so this RPC returns
        immediately. Status is pushed to Redis pub/sub when ingestion completes.
        """
        if not _PROTO_AVAILABLE:
            return

        try:
            doc_id      = uuid.UUID(request.document_id)   # type: ignore[union-attr]
            workspace   = uuid.UUID(request.workspace_id)  # type: ignore[union-attr]
            project     = uuid.UUID(request.project_id)    # type: ignore[union-attr]
            session     = uuid.UUID(request.session_id)    # type: ignore[union-attr]
            filename    = request.filename                  # type: ignore[union-attr]
            content     = request.content                  # type: ignore[union-attr]
        except (ValueError, AttributeError) as exc:
            logger.error("IngestDocument: bad request — %s", exc)
            return pb2.IngestResponse(document_id="", status="rejected")

        if not content:
            logger.warning("IngestDocument: empty content for document %s — rejected", doc_id)
            return pb2.IngestResponse(document_id=str(doc_id), status="rejected")

        pool = await get_pool()
        repo = DocumentRepository(pool)
        pipeline = IngestionPipeline(
            repo=repo,
            config=self._config.ingestion,
            redis=self._redis,
        )

        # Register document row first so status is visible immediately.
        await repo.create_document(
            document_id=doc_id,
            workspace_id=workspace,
            project_id=project,
            session_id=session,
            filename=filename,
            file_hash=_sha256(content),
            r2_key="",  # R2 key not used when content is inlined
        )

        # Kick off ingestion in the background.
        asyncio.create_task(
            pipeline.run(
                document_id=doc_id,
                workspace_id=workspace,
                project_id=project,
                session_id=session,
                content=content,
                filename=filename,
            ),
            name=f"ingest-{doc_id}",
        )

        logger.info("IngestDocument accepted — document=%s workspace=%s", doc_id, workspace)
        return pb2.IngestResponse(document_id=str(doc_id), status="accepted")

    # ------------------------------------------------------------------
    # Healthz
    # ------------------------------------------------------------------

    async def Healthz(self, request: object, context: object) -> object:
        if not _PROTO_AVAILABLE:
            return
        return pb2.HealthResponse(status="ok")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _proto_session_to_dict(proto: object) -> dict:
    """Convert SessionStateProto to a Python dict for PipelineExecutor."""
    if proto is None:
        return {}

    # If state_json is populated, parse it directly.
    state_json: str = getattr(proto, "state_json", "") or ""
    if state_json:
        try:
            return json.loads(state_json)
        except json.JSONDecodeError:
            pass

    # Fallback: build a minimal dict from top-level proto fields.
    return {
        "session_id":        getattr(proto, "session_id", ""),
        "workspace_id":      getattr(proto, "workspace_id", ""),
        "project_id":        getattr(proto, "project_id", ""),
        "current_phase":     getattr(proto, "current_phase", "ProblemIntake"),
        "turn_count":        getattr(proto, "turn_count", 0),
        "total_llm_cost_usd": getattr(proto, "total_cost_usd", 0.0),
        "ac_met":            list(getattr(proto, "ac_met", [])),
        "ac_waived":         list(getattr(proto, "ac_waived", [])),
        "documents_indexed": list(getattr(proto, "documents_indexed", [])),
    }


def _build_turn_complete(result: object, pb2_mod: object, common_mod: object) -> object:
    """Map a TurnResult to a TurnComplete proto message."""
    entities = [
        common_mod.EntityProto(
            entity_type=e.entity_type,
            value=e.value,
            confidence=e.confidence,
            source=e.source,
            source_chunk_ids=e.source_chunk_ids,
        )
        for e in (getattr(result, "entities", []) or [])
    ]
    ac_updates = [
        common_mod.AcUpdateProto(
            criterion_id=a.criterion_id,
            met=a.met,
            evidence=a.evidence,
        )
        for a in (getattr(result, "ac_updates", []) or [])
    ]
    gap = getattr(result, "gap_analysis", None)

    return pb2_mod.TurnComplete(
        intent=getattr(result, "intent", ""),
        entities=entities,
        ac_updates=ac_updates,
        transition_ready=gap.is_terminal if gap else False,
        gap_criterion_id=gap.criterion_id if gap else "",
        suggested_question=gap.suggested_question if gap else "",
        cost_usd=float(getattr(result, "cost_usd", 0.0)),
        node_errors=dict(getattr(result, "node_errors", {}) or {}),
        aborted=bool(getattr(result, "aborted", False)),
    )


def _sha256(content: bytes) -> str:
    import hashlib
    return hashlib.sha256(content).hexdigest()
