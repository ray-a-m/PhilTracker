"""End-to-end pipeline integration tests.

All external surfaces are mocked:
- Scraper classes return in-memory Listing lists
- `run_institutional` returns []
- Anthropic client returns a fixed tool_use payload
- `smtplib.SMTP_SSL` is patched

Verifies that scheduler.run_all.pipeline walks the full chain without
touching the network or the real filesystem DB.
"""

import io
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend import models
from scrapers.base import Listing


# ─── fixtures ────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "sched.db")
    monkeypatch.setattr(models, "DB_PATH", db_path)
    monkeypatch.setenv("PHILTRACKER_DB", db_path)
    monkeypatch.setenv("PHILTRACKER_CONFIG", str(tmp_path / "nonexistent.yaml"))
    yield


def _mock_tool_use_response(payload: dict) -> SimpleNamespace:
    block = SimpleNamespace(type="tool_use", name="record_listing_classification", input=payload)
    return SimpleNamespace(content=[block])


def _mock_anthropic_client(payload: dict) -> MagicMock:
    client = MagicMock()
    client.messages.create.return_value = _mock_tool_use_response(payload)
    return client


def _make_listing(i: int) -> Listing:
    return Listing(
        title=f"Raw scraper title {i}",
        institution=f"Raw scraper institution {i}",
        url=f"https://example.org/listing-{i}",
        source="TestSource",
        description=f"This is listing number {i}. Philosophy of physics postdoc.",
    )


# ─── pipeline runs ───────────────────────────────────────────────────────


def test_pipeline_empty_scrape_emits_no_new_listings_digest():
    """Zero listings scraped → still emits a receipt digest."""
    from scheduler import run_all as sched

    with patch.object(sched, "_scrape_selected", return_value=[]):
        buf = io.StringIO()
        with redirect_stdout(buf):
            sched.pipeline(selected=None, dry_run=True)

    out = buf.getvalue()
    assert "no new listings" in out.lower()
    assert "DRY-RUN" in out  # came from mailer.send
    assert "Total scraped: 0" in out


def test_pipeline_with_scraped_listings_classifies_inserts_and_renders():
    """3 scraped listings → LLM classifies → 2 accepted + 1 rejected →
    digest has 2 entries + 2 per-listing emails; 1 rejected-today in footer."""
    from scheduler import run_all as sched

    scraped = [_make_listing(1), _make_listing(2), _make_listing(3)]

    # First two get accepted, third is a reject
    accept_payload = {
        "is_posting": True, "confidence": 0.9, "posting_type": "postdoc",
        "title": "", "institution": "", "deadline": "2099-12-31",
        "location": "Somewhere, ZZ", "duration": "2 years",
        "aos": ["philosophy-of-physics"], "summary": "A real posting.",
    }
    reject_payload = {
        "is_posting": False, "confidence": 0.85, "posting_type": "unknown",
        "title": "", "institution": "", "deadline": None,
        "location": "", "duration": "",
        "aos": [], "summary": "",
    }
    client = MagicMock()
    client.messages.create.side_effect = [
        _mock_tool_use_response(accept_payload),
        _mock_tool_use_response(accept_payload),
        _mock_tool_use_response(reject_payload),
    ]

    with patch.object(sched, "_scrape_selected", return_value=scraped), \
         patch("llm.extract.call_with_retry", side_effect=lambda msg, client=None: (
             client.messages.create.return_value.content[0].input
             if hasattr(client, "messages") else None
         )):
        # Simpler: patch classify_and_extract directly instead of going through call_with_retry
        pass

    # Redo with a cleaner patch: inject the anthropic client into extract
    call_count = {"n": 0}
    responses = [accept_payload, accept_payload, reject_payload]

    def fake_call_with_retry(msg, client=None, max_retries=3):
        r = responses[call_count["n"]]
        call_count["n"] += 1
        return r

    with patch.object(sched, "_scrape_selected", return_value=scraped), \
         patch("llm.extract.call_with_retry", side_effect=fake_call_with_retry):
        buf = io.StringIO()
        with redirect_stdout(buf):
            sched.pipeline(selected=None, dry_run=True)

    out = buf.getvalue()

    # 3 scraped, all 3 classified
    assert "Total scraped: 3" in out
    assert "URL cache: 3 fresh" in out
    assert "[1/3] classifying" in out
    assert "[3/3] classifying" in out

    # 3 inserted (2 active, 1 reject — smart_insert still returns "new" for the reject row)
    assert "Inserted: 3 new" in out

    # Digest reports 2 active + 1 rejected
    assert "2 new listings" in out
    assert "Done. 2 active in digest, 1 rejected today." in out

    # 1 digest DRY-RUN block + 2 per-listing DRY-RUN blocks = 3 total
    assert out.count("--- DRY-RUN:") == 3


def test_pipeline_skips_already_known_urls():
    """A second run on the same set of URLs should send zero LLM calls."""
    from scheduler import run_all as sched

    scraped = [_make_listing(1), _make_listing(2)]

    # Pre-populate the DB with those URLs
    models.init_db()
    for listing in scraped:
        models.insert_listing(listing)

    mock_call = MagicMock()

    with patch.object(sched, "_scrape_selected", return_value=scraped), \
         patch("llm.extract.call_with_retry", side_effect=mock_call):
        buf = io.StringIO()
        with redirect_stdout(buf):
            sched.pipeline(selected=None, dry_run=True)

    out = buf.getvalue()
    assert "URL cache: 0 fresh, 2 already in DB" in out
    mock_call.assert_not_called()


def test_main_catches_exception_and_calls_failure_notice(monkeypatch):
    """If the pipeline raises, main() dispatches send_failure_notice before re-raising."""
    from scheduler import run_all as sched

    failure_calls: list = []

    def broken_pipeline(*args, **kwargs):
        raise RuntimeError("scraper blew up")

    def capture_failure(reason, *, dry_run=False):
        failure_calls.append((reason, dry_run))

    monkeypatch.setattr(sched, "pipeline", broken_pipeline)
    monkeypatch.setattr(sched, "send_failure_notice", capture_failure)
    monkeypatch.setattr("sys.argv", ["scheduler.run_all", "--dry-run"])

    with pytest.raises(RuntimeError, match="scraper blew up"):
        sched.main()

    assert len(failure_calls) == 1
    reason, dry_run = failure_calls[0]
    assert "RuntimeError: scraper blew up" in reason
    assert dry_run is True
