"""Classifier precision/recall regression against the labelled corpus.

Runs the real LLM against each corpus entry's text and checks the result
matches `expected_is_posting`. This is a `@pytest.mark.live` test — real API
calls, one per corpus entry.

Targets (from SPEC):
    precision ≥ 0.95
    recall    ≥ 0.95

Skipped entirely until the corpus has ≥30 entries (the spec's seed threshold).
"""

from pathlib import Path

import pytest
import yaml

from scrapers.base import Listing


CORPUS_PATH = Path(__file__).parent / "classifier_corpus.yaml"
PRECISION_TARGET = 0.95
RECALL_TARGET = 0.95
SEED_THRESHOLD = 30


def _load_entries() -> list[dict]:
    with open(CORPUS_PATH) as f:
        data = yaml.safe_load(f) or {}
    return data.get("entries") or []


def _make_listing_from_entry(entry: dict) -> Listing:
    """Build a bare Listing from a corpus entry. Only `description` is
    semantically significant — the rest is placeholder metadata."""
    return Listing(
        title=entry.get("id", "corpus-entry"),
        institution="",
        url=f"https://corpus.internal/{entry['id']}",
        source=entry.get("source", "corpus"),
        description=entry["text"],
    )


@pytest.fixture(scope="module")
def corpus() -> list[dict]:
    entries = _load_entries()
    if len(entries) < SEED_THRESHOLD:
        pytest.skip(
            f"classifier_corpus.yaml has {len(entries)} entries "
            f"(target: ≥{SEED_THRESHOLD}). Seed more before running the corpus regression."
        )
    return entries


@pytest.mark.live
def test_classifier_precision_and_recall(corpus):
    from llm.extract import classify_and_extract

    tp = fp = tn = fn = 0

    for entry in corpus:
        listing = _make_listing_from_entry(entry)
        result = classify_and_extract(listing)
        expected = bool(entry["expected_is_posting"])
        got = bool(result.active)

        if expected and got:
            tp += 1
        elif expected and not got:
            fn += 1
        elif not expected and got:
            fp += 1
        else:
            tn += 1

    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0

    summary = (
        f"\nCorpus results: tp={tp} fp={fp} tn={tn} fn={fn} "
        f"| precision={precision:.3f} recall={recall:.3f}"
    )
    print(summary)

    assert precision >= PRECISION_TARGET, f"precision {precision:.3f} below {PRECISION_TARGET}"
    assert recall >= RECALL_TARGET, f"recall {recall:.3f} below {RECALL_TARGET}"
