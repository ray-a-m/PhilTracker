"""Tests for the listings-only SQLite schema."""

import pytest
from datetime import date, timedelta

from scrapers.base import Listing
from backend import models


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Use a temporary database for each test."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(models, "DB_PATH", db_path)
    monkeypatch.setenv("PHILTRACKER_DB", db_path)
    models.init_db()
    yield db_path


def _make_listing(title="Test Job", url="https://example.com/1", **kwargs):
    defaults = dict(
        institution="Test University",
        source="test",
        description="A test listing.",
    )
    defaults.update(kwargs)
    return Listing(title=title, url=url, **defaults)


def test_init_db_listings_only(temp_db):
    conn = models.get_db()
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    conn.close()
    names = {row["name"] for row in tables}
    assert names == {"listings"}


def test_schema_has_new_columns(temp_db):
    conn = models.get_db()
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(listings)").fetchall()}
    conn.close()
    assert {"summary", "confidence", "duration"} <= cols
    assert not ({"start_date", "aos_raw", "salary", "secondary_urls"} & cols)


def test_insert_listing():
    assert models.insert_listing(_make_listing()) is True


def test_insert_duplicate_url_returns_false():
    listing = _make_listing()
    models.insert_listing(listing)
    assert models.insert_listing(listing) is False


def test_insert_preserves_active_flag():
    rejected = _make_listing("Rejected Post", "https://example.com/r")
    rejected.active = False
    models.insert_listing(rejected)
    conn = models.get_db()
    row = dict(conn.execute("SELECT active FROM listings WHERE url = ?", (rejected.url,)).fetchone())
    conn.close()
    assert row["active"] == 0


def test_insert_stores_llm_fields():
    listing = _make_listing(
        location="Oxford, UK",
        duration="3 years",
        summary="Three-year postdoc in philosophy of physics.",
        confidence=0.93,
    )
    listing.aos = ["philosophy-of-physics"]
    listing.listing_type = "postdoc"
    models.insert_listing(listing)

    conn = models.get_db()
    row = dict(conn.execute("SELECT * FROM listings WHERE id = 1").fetchone())
    conn.close()
    assert row["location"] == "Oxford, UK"
    assert row["duration"] == "3 years"
    assert row["summary"] == "Three-year postdoc in philosophy of physics."
    assert row["confidence"] == pytest.approx(0.93)
    assert row["listing_type"] == "postdoc"


def test_get_known_urls():
    models.insert_listing(_make_listing("A", "https://a.com"))
    models.insert_listing(_make_listing("B", "https://b.com"))
    urls = models.get_known_urls()
    assert urls == {"https://a.com", "https://b.com"}


def test_get_new_active_listings_filters_by_date_and_active():
    today = date.today().isoformat()
    models.insert_listing(_make_listing("Active Today", "https://a.com"))

    rejected = _make_listing("Rejected Today", "https://r.com")
    rejected.active = False
    models.insert_listing(rejected)

    results = models.get_new_active_listings(today)
    titles = [r["title"] for r in results]
    assert titles == ["Active Today"]


def test_count_rejected_today():
    today = date.today().isoformat()
    models.insert_listing(_make_listing("Accepted", "https://a.com"))
    for i in range(3):
        rejected = _make_listing(f"Rejected {i}", f"https://r{i}.com")
        rejected.active = False
        models.insert_listing(rejected)
    assert models.count_rejected_today(today) == 3


def test_deactivate_expired():
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    models.insert_listing(_make_listing("Expired", "https://a.com", deadline=yesterday))
    models.insert_listing(_make_listing("Active", "https://b.com", deadline=tomorrow))

    models.deactivate_expired()

    today = date.today().isoformat()
    results = models.get_new_active_listings(today)
    titles = [r["title"] for r in results]
    assert titles == ["Active"]
