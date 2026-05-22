"""Domain entities shared across pipeline nodes.

These are the structured outputs that flow through PipelineState.
They map directly to the ontology in docs/architecture/ontology.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


@dataclass
class Entity:
    """An entity extracted by EntityExtractorNode from a BA turn."""
    entity_type: str        # "actor" | "requirement" | "constraint" | "assumption" | "gap"
    value:       str        # raw extracted text
    confidence:  float = 1.0
    source:      str   = "conversation"   # "conversation" | "document"
    phase:       str   = ""               # phase in which it was extracted


@dataclass
class ChunkRef:
    """A document chunk returned by RAGRetrievalNode."""
    chunk_id:      UUID
    content:       str
    score:         float          # hybrid retrieval score (0–1)
    section_title: str | None = None
    page_number:   int | None = None
    trust_tier:    int        = 3
    document_id:   UUID | None = None
    source_type:   str        = "pdf"


@dataclass
class GapResult:
    """The single highest-priority unmet AC criterion, output of GapAnalyzerNode."""
    criterion_id:       str
    description:        str
    suggested_question: str       # exact question to put to the BA next
    priority:           int  = 0  # lower = more important
    is_terminal:        bool = False  # True when all AC met (transition ready)
    unmet_count:        int  = 0


@dataclass
class AcUpdate:
    """An AC status change detected by a node, forwarded to Rust after pipeline completes."""
    criterion_id: str
    met:          bool
    evidence:     str = ""        # short rationale for the change
