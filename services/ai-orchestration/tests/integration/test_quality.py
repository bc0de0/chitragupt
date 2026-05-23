"""Domain 3 — Quality of Response: Integration tests (real LLM).

T-QUAL-01: Intent precision ≥ 0.90 on 50 golden utterances.
T-QUAL-02: Entity extraction F1 ≥ 0.80 on 10 annotated transcripts.

Requires: OPENROUTER_API_KEY, golden dataset at tests/fixtures/golden_utterances.jsonl.
Run with: pytest -m quality
"""
import pytest


@pytest.mark.quality
@pytest.mark.skip(reason="Requires real LLM calls (OPENROUTER_API_KEY). Run with: pytest -m quality")
async def test_qual_01_intent_precision_on_golden_utterances():
    """
    T-QUAL-01: Run IntentClassifier against 50 labelled BA utterances from
    tests/fixtures/golden_utterances.jsonl. Precision must be ≥ 0.90.

    Requires: OPENROUTER_API_KEY + golden dataset.
    """
    raise NotImplementedError("Quality test — requires live LLM and golden dataset.")


@pytest.mark.quality
@pytest.mark.skip(reason="Requires real LLM calls (OPENROUTER_API_KEY). Run with: pytest -m quality")
async def test_qual_02_entity_extraction_f1_on_annotated_transcripts():
    """
    T-QUAL-02: Run EntityExtractor against 10 annotated BA transcripts.
    Entity extraction F1 must be ≥ 0.80.

    Requires: OPENROUTER_API_KEY + annotated transcript fixtures.
    """
    raise NotImplementedError("Quality test — requires live LLM and annotated transcripts.")
