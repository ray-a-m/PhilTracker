"""Tests for database models."""

import json
import os
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


def test_init_db(temp_db):
    conn = models.get_db()
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    conn.close()
    table_names = {row["name"] for row in tables}
    assert "listings" in table_names
    assert "users" in table_names


def test_insert_listing():
    listing = _make_listing()
    assert models.insert_listing(listing) is True


def test_insert_duplicate_url():
    listing = _make_listing()
    models.insert_listing(listing)
    assert models.insert_listing(listing) is False


def test_get_active_listings():
    models.insert_listing(_make_listing("Job A", "https://a.com"))
    models.insert_listing(_make_listing("Job B", "https://b.com"))
    results = models.get_active_listings()
    assert len(results) == 2


def test_get_active_listings_by_tags():
    listing = _make_listing("Physics Job", "https://a.com")
    listing.aos = ["philosophy-of-physics"]
    models.insert_listing(listing)

    listing2 = _make_listing("Ethics Job", "https://b.com")
    listing2.aos = ["political-philosophy-ethics"]
    models.insert_listing(listing2)

    results = models.get_active_listings(tags=["philosophy-of-physics"])
    assert len(results) == 1
    assert results[0]["title"] == "Physics Job"


def test_deactivate_expired():
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    listing_expired = _make_listing("Expired", "https://a.com", deadline=yesterday)
    listing_active = _make_listing("Active", "https://b.com", deadline=tomorrow)

    models.insert_listing(listing_expired)
    models.insert_listing(listing_active)

    models.deactivate_expired()

    results = models.get_active_listings()
    assert len(results) == 1
    assert results[0]["title"] == "Active"


def test_secondary_urls_column():
    """Verify the secondary_urls column exists."""
    listing = _make_listing()
    models.insert_listing(listing)

    conn = models.get_db()
    row = dict(conn.execute("SELECT secondary_urls FROM listings WHERE id = 1").fetchone())
    conn.close()
    assert row["secondary_urls"] == "[]"


def test_all_fields_stored():
    listing = _make_listing(
        location="Oxford, UK",
        duration="3 years",
        start_date="2026-09-01",
        aos_raw="Philosophy of Physics",
        salary="£40,000",
    )
    models.insert_listing(listing)

    conn = models.get_db()
    row = dict(conn.execute("SELECT * FROM listings WHERE id = 1").fetchone())
    conn.close()
    assert row["location"] == "Oxford, UK"
    assert row["duration"] == "3 years"
    assert row["start_date"] == "2026-09-01"
    assert row["aos_raw"] == "Philosophy of Physics"
    assert row["salary"] == "£40,000"
