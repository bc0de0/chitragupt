"""Domain 5 — Code Correctness: Chunker tests.

T-CORR-01, T-CORR-02, T-CORR-03.

Tests verify that the sliding-window chunker produces correct boundaries,
correct overlap, and discards micro-chunks below the minimum token threshold.
All tests run in the 'fast' CI mode — no external I/O.
"""
from __future__ import annotations

import pytest

from ai_orchestration.ingestion.chunker import Chunker, TextChunk
from ai_orchestration.ingestion.document_processor import RawPage


def _make_pages(word_count: int, section: str = "S1", page: int = 1) -> list[RawPage]:
    """Produce a single RawPage with exactly `word_count` unique words."""
    text = " ".join(f"word{i}" for i in range(word_count))
    return [RawPage(text=text, page_number=page, section_title=section)]


# ─────────────────────────────────────────────────────────────────────────────
# T-CORR-01: 512-token window produces correct chunk boundaries
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
def test_corr_01_chunker_512_window_correct_boundaries():
    """
    T-CORR-01: A page with 1100 words and chunk_size=512, overlap=64, min=50
    should produce 3 chunks whose token counts respect the window size.

    Word math:
      chunk0: words 0..511    → 512 tokens
      chunk1: words 448..959  → 512 tokens   (start = 512-64 = 448)
      chunk2: words 896..1099 → 204 tokens   (start = 960-64 = 896)

    EXPECTED: PASS
    """
    pages = _make_pages(1100)
    chunker = Chunker(chunk_size_tokens=512, overlap_tokens=64, min_tokens=50)
    chunks = chunker.chunk(pages)

    assert len(chunks) == 3, f"Expected 3 chunks, got {len(chunks)}"
    assert chunks[0].token_count == 512
    assert chunks[1].token_count == 512
    assert chunks[2].token_count == 204  # 1100 - 896


@pytest.mark.fast
def test_corr_01b_single_page_single_chunk_when_small():
    """A page with fewer tokens than chunk_size → exactly 1 chunk."""
    pages = _make_pages(100)
    chunker = Chunker(chunk_size_tokens=512, overlap_tokens=64, min_tokens=50)
    chunks = chunker.chunk(pages)

    assert len(chunks) == 1
    assert chunks[0].token_count == 100


@pytest.mark.fast
def test_corr_01c_empty_page_produces_no_chunks():
    """An empty page contributes no chunks."""
    pages = [RawPage(text="", page_number=1)]
    chunker = Chunker(chunk_size_tokens=512, overlap_tokens=64, min_tokens=50)
    chunks = chunker.chunk(pages)

    assert chunks == []


@pytest.mark.fast
def test_corr_01d_chunk_indices_are_sequential_and_zero_based():
    """chunk_index must be sequential starting from 0."""
    pages = _make_pages(1200)
    chunker = Chunker(chunk_size_tokens=512, overlap_tokens=64, min_tokens=50)
    chunks = chunker.chunk(pages)

    for expected_idx, chunk in enumerate(chunks):
        assert chunk.chunk_index == expected_idx, (
            f"chunk_index={chunk.chunk_index}, expected={expected_idx}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# T-CORR-02: 64-token overlap — last 64 tokens of chunk N = first 64 of chunk N+1
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
def test_corr_02_overlap_tokens_shared_between_adjacent_chunks():
    """
    T-CORR-02: The last `overlap` tokens of chunk N must equal the first `overlap`
    tokens of chunk N+1. This guarantees semantic continuity across chunk boundaries.

    EXPECTED: PASS
    """
    pages = _make_pages(600)
    chunker = Chunker(chunk_size_tokens=512, overlap_tokens=64, min_tokens=50)
    chunks = chunker.chunk(pages)

    assert len(chunks) >= 2, "Need at least 2 chunks to test overlap"

    for i in range(len(chunks) - 1):
        tail = chunks[i].text.split()[-64:]
        head = chunks[i + 1].text.split()[:64]
        assert tail == head, (
            f"Overlap mismatch between chunk {i} and chunk {i+1}. "
            f"Tail: {tail[:5]}... Head: {head[:5]}..."
        )


@pytest.mark.fast
def test_corr_02b_overlap_preserved_across_multiple_chunks():
    """Overlap invariant holds for all adjacent pairs in a long document."""
    pages = _make_pages(2000)
    chunker = Chunker(chunk_size_tokens=512, overlap_tokens=64, min_tokens=50)
    chunks = chunker.chunk(pages)

    assert len(chunks) >= 3, "Need at least 3 chunks for multi-pair overlap check"

    for i in range(len(chunks) - 1):
        tail = chunks[i].text.split()[-64:]
        head = chunks[i + 1].text.split()[:64]
        assert tail == head, f"Overlap mismatch at chunk pair ({i}, {i+1})"


# ─────────────────────────────────────────────────────────────────────────────
# T-CORR-03: Micro-chunks below min_tokens (50) are discarded
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.fast
def test_corr_03_micro_chunks_below_min_tokens_discarded():
    """
    T-CORR-03: A trailing chunk with fewer than min_tokens words must be discarded.

    With chunk_size=512, overlap=64, min=50:
      - 560 words → chunk0: 512 words, chunk1 start: 512-64=448, chunk1: words 448..559 → 112 tokens (kept)
      - 520 words → chunk0: 512 words, chunk1 start: 448, chunk1: words 448..519 → 72 tokens (kept)
      - 514 words → chunk0: 512 words, chunk1 start: 448, chunk1: words 448..513 → 66 tokens (kept)
      - 510 words → chunk0: 510 words (fits in one), only 1 chunk

    To get a micro-chunk: need start + window < min. With chunk_size=100, overlap=20, min=50:
      - 115 words → chunk0: 100 words, chunk1 start: 80, chunk1: 35 words → below 50 → discarded

    EXPECTED: PASS
    """
    pages = _make_pages(115)
    chunker = Chunker(chunk_size_tokens=100, overlap_tokens=20, min_tokens=50)
    chunks = chunker.chunk(pages)

    # chunk0: 100 tokens; chunk1: 15 tokens (below min=50) → discarded
    assert len(chunks) == 1, (
        f"Expected 1 chunk (micro-chunk discarded), got {len(chunks)}. "
        f"Token counts: {[c.token_count for c in chunks]}"
    )
    assert chunks[0].token_count == 100


@pytest.mark.fast
def test_corr_03b_first_chunk_kept_even_if_below_min_tokens():
    """The first (and only) chunk is kept even if it is below min_tokens."""
    pages = _make_pages(30)  # fewer than min_tokens=50
    chunker = Chunker(chunk_size_tokens=512, overlap_tokens=64, min_tokens=50)
    chunks = chunker.chunk(pages)

    assert len(chunks) == 1, "First chunk must always be kept regardless of min_tokens"
    assert chunks[0].token_count == 30


@pytest.mark.fast
def test_corr_03c_chunk_inherits_page_metadata():
    """Chunks carry the section_title and page_number from their source RawPage."""
    pages = [RawPage(
        text=" ".join(f"word{i}" for i in range(100)),
        page_number=3,
        section_title="Introduction",
    )]
    chunker = Chunker(chunk_size_tokens=512, overlap_tokens=64, min_tokens=50)
    chunks = chunker.chunk(pages)

    assert len(chunks) == 1
    assert chunks[0].page_number == 3
    assert chunks[0].section_title == "Introduction"
