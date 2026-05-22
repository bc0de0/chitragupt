"""PipelineState — the shared TypedDict threaded through every LangGraph node.

Rules:
  - Nodes read from upstream fields; write only to their own output field(s).
  - No node modifies another node's field.
  - `node_errors` is the only dict that accumulates across nodes.
  - `pipeline_aborted` is set True only by GuidanceGeneratorNode on unrecoverable failure.
"""
from __future__ import annotations

from typing import Any, Optional, TypedDict

from ..llm.context import SessionLLMContext
from ..models.entities import AcUpdate, ChunkRef, Entity, GapResult


class PipelineState(TypedDict):
    # ---- Inputs (set at pipeline entry; never mutated by nodes) ----------------
    session_state:    Any                    # SessionStateProto or dict (tests)
    user_message:     str
    llm_ctx:          SessionLLMContext

    # ---- Node outputs (each node owns exactly one field) -----------------------
    intent:              Optional[str]       # set by IntentClassifierNode
    extracted_entities:  list[Entity]        # set by EntityExtractorNode
    retrieved_chunks:    list[ChunkRef]      # set by RAGRetrievalNode
    gap_analysis:        Optional[GapResult] # set by GapAnalyzerNode
    guidance_tokens:     list[str]           # set by GuidanceGeneratorNode
    ac_updates:          list[AcUpdate]      # set by EntityExtractorNode / GapAnalyzerNode

    # ---- Error tracking (accumulated across all nodes) -------------------------
    node_errors:      dict[str, str]         # node_class_name → error message
    pipeline_aborted: bool                   # True only on GuidanceGenerator failure
