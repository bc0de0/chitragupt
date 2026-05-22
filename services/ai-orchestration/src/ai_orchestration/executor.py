"""PipelineExecutor — the core per-turn orchestration entry point.

This is the only public interface the gRPC servicer will call (when the
service layer is added in a later sprint). It owns the compiled LangGraph graph
and exposes a single async generator that processes one BA turn end-to-end,
yielding guidance tokens as they stream from the LLM.

Lifecycle:
  1. Instantiate PipelineExecutor once at service startup.
  2. For each BA turn call executor.run(session_state, message, llm_ctx).
  3. Iterate the returned async generator to receive tokens.
  4. Await executor.get_last_result() to read structured outputs (entities, AC updates, etc.).

The executor is stateless between turns — all per-turn state lives in PipelineState.
"""
from __future__ import annotations

import asyncio
import logging
from asyncio import Queue
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

from langgraph.graph import StateGraph
from langgraph.graph.graph import CompiledGraph

from .agents.entity_extractor import EntityExtractorNode
from .agents.gap_analyzer import GapAnalyzerNode
from .agents.guidance_generator import GuidanceGeneratorNode
from .agents.intent_classifier import IntentClassifierNode
from .agents.rag_retrieval import RAGRetrievalNode
from .config import OrchestrationConfig
from .llm.context import SessionLLMContext
from .models.entities import AcUpdate, ChunkRef, Entity, GapResult
from .pipeline.state import PipelineState

logger = logging.getLogger(__name__)

# None is the stream-done sentinel placed by GuidanceGeneratorNode
_STREAM_DONE: None = None


# ---------------------------------------------------------------------------
# Result dataclass returned after a completed turn
# ---------------------------------------------------------------------------

@dataclass
class TurnResult:
    """Structured outputs from a completed pipeline run."""
    intent:          str
    entities:        list[Entity]       = field(default_factory=list)
    ac_updates:      list[AcUpdate]     = field(default_factory=list)
    gap_analysis:    GapResult | None   = None
    guidance_tokens: list[str]          = field(default_factory=list)
    node_errors:     dict[str, str]     = field(default_factory=dict)
    aborted:         bool               = False
    cost_usd:        float              = 0.0

    @property
    def has_errors(self) -> bool:
        return bool(self.node_errors)

    @property
    def transition_ready(self) -> bool:
        return (
            self.gap_analysis is not None
            and self.gap_analysis.is_terminal
            and not self.aborted
        )


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------

class PipelineAbortedError(Exception):
    """
    Raised by PipelineExecutor.run() when GuidanceGeneratorNode fails unrecoverably.
    The gRPC servicer catches this and sends a static error message to the BA.
    """

    def __init__(self, node_errors: dict[str, str]) -> None:
        self.node_errors = node_errors
        super().__init__(f"Pipeline aborted — node errors: {node_errors}")


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_pipeline(config: OrchestrationConfig) -> CompiledGraph:
    """
    Construct and compile the LangGraph per-turn pipeline.

    Graph topology (linear — no branches in happy path):
        classify_intent → extract_entities → retrieve_context → analyze_gaps → generate_guidance

    Called once at service startup. The compiled graph is a process-level singleton:
    it is stateless (all state lives in PipelineState) and safe to share across
    concurrent async invocations.
    """
    graph: StateGraph = StateGraph(PipelineState)  # type: ignore[arg-type]

    graph.add_node("classify_intent",   IntentClassifierNode(config))
    graph.add_node("extract_entities",  EntityExtractorNode(config))
    graph.add_node("retrieve_context",  RAGRetrievalNode(config))
    graph.add_node("analyze_gaps",      GapAnalyzerNode(config))
    graph.add_node("generate_guidance", GuidanceGeneratorNode(config))

    graph.add_edge("classify_intent",  "extract_entities")
    graph.add_edge("extract_entities", "retrieve_context")
    graph.add_edge("retrieve_context", "analyze_gaps")
    graph.add_edge("analyze_gaps",     "generate_guidance")

    graph.set_entry_point("classify_intent")
    graph.set_finish_point("generate_guidance")

    compiled = graph.compile()
    logger.info("Pipeline compiled — 5 nodes, linear topology")
    return compiled


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------

class PipelineExecutor:
    """
    Process-level singleton. Owns the compiled LangGraph graph.

    Usage (before the service layer exists — e.g. in tests or a CLI harness):

        config   = OrchestrationConfig.default()
        factory  = SessionLLMContextFactory(config)
        executor = PipelineExecutor(config)

        session  = {"session_id": "...", "current_phase": "ProblemIntake", ...}
        llm_ctx  = await factory.for_turn(session)

        async for token in executor.run(session, "Tell me about your problem", llm_ctx):
            print(token, end="", flush=True)

        result = executor.last_result   # TurnResult with entities, AC updates, etc.
    """

    def __init__(self, config: OrchestrationConfig) -> None:
        self._config = config
        self._graph: CompiledGraph = build_pipeline(config)
        self._last_result: TurnResult | None = None

    @property
    def last_result(self) -> TurnResult | None:
        """The TurnResult from the most recently completed run(). None before first run."""
        return self._last_result

    async def run(
        self,
        session_state: Any,
        user_message: str,
        llm_ctx: SessionLLMContext,
    ) -> AsyncGenerator[str, None]:
        """
        Execute one BA turn through the full pipeline.

        Yields guidance tokens as they stream from GuidanceGeneratorNode.
        After the generator is exhausted, executor.last_result holds the full TurnResult.

        Raises:
            PipelineAbortedError — if GuidanceGeneratorNode fails unrecoverably.
              The caller is responsible for sending a fallback error message to the BA.
        """
        token_queue: Queue[str | None] = Queue(
            maxsize=self._config.orchestration.streaming.token_queue_maxsize,
        )
        llm_ctx.token_sink = token_queue

        initial: PipelineState = {
            "session_state":     session_state,
            "user_message":      user_message,
            "llm_ctx":           llm_ctx,
            "intent":            None,
            "extracted_entities": [],
            "retrieved_chunks":  [],
            "gap_analysis":      None,
            "guidance_tokens":   [],
            "ac_updates":        [],
            "node_errors":       {},
            "pipeline_aborted":  False,
        }

        # Run the graph as a background task so token streaming is concurrent.
        # The task puts None on token_queue when generation is done (or on error).
        pipeline_task: asyncio.Task[TurnResult] = asyncio.create_task(
            self._run_graph(initial)
        )

        # Yield tokens as they arrive; None sentinel exits the loop
        async for token in self._drain_queue(token_queue, pipeline_task):
            yield token

        # Graph is guaranteed done by the time _drain_queue exits (sentinel is emitted
        # in _run_graph's finally block, before the function returns).
        result = await pipeline_task
        self._last_result = result

        if result.aborted:
            raise PipelineAbortedError(result.node_errors)

    # ------------------------------------------------------------------
    # Internal implementation
    # ------------------------------------------------------------------

    async def _run_graph(self, initial_state: PipelineState) -> TurnResult:
        """
        Invoke the compiled LangGraph graph.
        Always puts None on the token queue before returning (sentinel for _drain_queue).
        """
        sink: Queue[str | None] | None = initial_state["llm_ctx"].token_sink

        try:
            final: PipelineState = await self._graph.ainvoke(initial_state)  # type: ignore[assignment]
        except Exception as exc:
            logger.exception("LangGraph raised unexpectedly — pipeline aborted")
            return TurnResult(
                intent="Clarification",
                node_errors={"pipeline": str(exc)},
                aborted=True,
            )
        finally:
            # Always close the queue so _drain_queue exits cleanly.
            # GuidanceGeneratorNode already puts None on success; this is the safety net
            # for the error path and any node that forgets to close the sink.
            if sink is not None:
                try:
                    sink.put_nowait(_STREAM_DONE)
                except asyncio.QueueFull:
                    pass  # queue is full — GuidanceGeneratorNode already closed it

        return TurnResult(
            intent=final.get("intent") or "Clarification",
            entities=final.get("extracted_entities") or [],
            ac_updates=final.get("ac_updates") or [],
            gap_analysis=final.get("gap_analysis"),
            guidance_tokens=final.get("guidance_tokens") or [],
            node_errors=final.get("node_errors") or {},
            aborted=final.get("pipeline_aborted", False),
            cost_usd=initial_state["llm_ctx"].budget.spent_usd,
        )

    @staticmethod
    async def _drain_queue(
        queue: Queue[str | None],
        pipeline_task: asyncio.Task[TurnResult],
    ) -> AsyncGenerator[str, None]:
        """
        Yield tokens from queue until None sentinel.
        Cancels the pipeline task if the absolute timeout is exceeded.
        The timeout here is a safety ceiling — individual node timeouts are tighter.
        """
        absolute_timeout = 25.0  # seconds — ceiling covering the longest BRD generation

        while True:
            try:
                token = await asyncio.wait_for(queue.get(), timeout=absolute_timeout)
            except asyncio.TimeoutError:
                logger.error(
                    "Token queue produced no sentinel after %.0fs — cancelling pipeline task",
                    absolute_timeout,
                )
                pipeline_task.cancel()
                return

            if token is _STREAM_DONE:
                return

            yield token
