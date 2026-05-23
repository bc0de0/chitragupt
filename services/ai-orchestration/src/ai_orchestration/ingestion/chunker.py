"""Sliding-window text chunker.

Uses whitespace tokenisation (1 token ≈ 1 word). This approximation is fast
and consistent across the codebase — pgvector stores voyage-large-2 embeddings
which do their own sub-word tokenisation internally.

Chunks preserve the page_number and section_title from their source RawPage.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from .document_processor import RawPage

logger = logging.getLogger(__name__)


@dataclass
class TextChunk:
    text: str
    chunk_index: int
    token_count: int
    section_title: str | None = None
    page_number: int | None = None


def _word_tokens(text: str) -> list[str]:
    return text.split()


class Chunker:
    """Split RawPage list into overlapping fixed-size windows."""

    def __init__(
        self,
        chunk_size_tokens: int = 512,
        overlap_tokens: int = 64,
        min_tokens: int = 50,
    ) -> None:
        self._size = chunk_size_tokens
        self._overlap = overlap_tokens
        self._min = min_tokens

    def chunk(self, pages: list[RawPage]) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        idx = 0

        for page in pages:
            tokens = _word_tokens(page.text)
            if not tokens:
                continue

            start = 0
            while start < len(tokens):
                end = min(start + self._size, len(tokens))
                window = tokens[start:end]
                token_count = len(window)

                # Drop trailing micro-chunks unless it's the first (and only) chunk.
                if token_count >= self._min or not chunks:
                    chunks.append(
                        TextChunk(
                            text=" ".join(window),
                            chunk_index=idx,
                            token_count=token_count,
                            section_title=page.section_title,
                            page_number=page.page_number,
                        )
                    )
                    idx += 1

                if end == len(tokens):
                    break
                start = end - self._overlap

        logger.debug("Chunker produced %d chunks from %d pages", len(chunks), len(pages))
        return chunks
