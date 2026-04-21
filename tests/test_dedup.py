"""Tests for smart deduplication."""

import pytest

from scrapers.base import Listing
from backend.dedup import (
    normalize_institution,
    extract_title_keywords,
    title_similarity,
    smart_insert,
)
from backend import models


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(models, "DB_PATH", db_path)
    monkeypatch.setenv("PHILTRACKER_DB", db_path)
    models.init_db()
    yield db_path


def _make_listing(title, institution, url, description="", **kwargs):
    return Listing(
        title=title, institution=institution, url=url, source="test",
        description=description, **kwargs,
    )


def test_normalize_institution():
    assert normalize_institution("University of Oxford") == "univ of oxford"
    assert normalize_institution("The University of Oxford") == "the univ of oxford"
    assert normalize_institution("Centre for Philosophy of Science") == "ctr for philosophy of science"
    assert normalize_institution("Max-Planck-Institut") == "maxplanckinst"


def test_extract_title_keywords():
    kw = extract_title_keywords("Postdoctoral Research Fellow in Philosophy of Physics")
    assert "philosophy" in kw
    assert "physics" in kw
    assert "postdoctoral" not in kw
    assert "research" not in kw


def test_title_similarity_high():
    a = extract_title_keywords("Postdoc in Philosophy of Physics")
    b = extract_title_keywords("Postdoctoral Fellow in Philosophy of Physics")
    assert title_similarity(a, b) >= 0.70


def test_title_similarity_low():
    a = extract_title_keywords("Postdoc in Philosophy of Physics")
    b = extract_title_keywords("Lecturer in Medieval History")
    assert title_similarity(a, b) < 0.70


def test_exact_url_duplicate_returns_duplicate():
    listing = _make_listing("Test Job", "Test Uni", "https://example.com/job/1")
    assert smart_insert(listing) == "new"
    assert smart_insert(listing) == "duplicate"


def test_fuzzy_match_returns_duplicate():
    listing1 = _make_listing(
        "Postdoc in Philosophy of Physics",
        "University of Oxford",
        "https://philjobs.org/job/show/111",
    )
    listing2 = _make_listing(
        "Postdoctoral Fellow in Philosophy of Physics",
        "University of Oxford",
        "https://dailynous.com/oxford-postdoc",
    )
    assert smart_insert(listing1) == "new"
    assert smart_insert(listing2) == "duplicate"

    conn = models.get_db()
    count = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    conn.close()
    assert count == 1


def test_different_institutions_no_dedup():
    listing1 = _make_listing(
        "Postdoc in Philosophy of Physics",
        "University of Oxford",
        "https://example.com/1",
    )
    listing2 = _make_listing(
        "Postdoc in Philosophy of Physics",
        "University of Cambridge",
        "https://example.com/2",
    )
    assert smart_insert(listing1) == "new"
    assert smart_insert(listing2) == "new"

    conn = models.get_db()
    count = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    conn.close()
    assert count == 2


def test_different_titles_no_dedup():
    listing1 = _make_listing("Postdoc in Ethics", "Princeton University", "https://a.com/1")
    listing2 = _make_listing("Lecturer in Medieval History", "Princeton University", "https://b.com/2")
    assert smart_insert(listing1) == "new"
    assert smart_insert(listing2) == "new"
