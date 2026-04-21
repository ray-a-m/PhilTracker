"""Snapshot + escape tests for mailer.render.

Snapshots use *synthetic* fixture data only; no real scraper output. Set
`UPDATE_SNAPSHOTS=1 pytest` to regenerate after an intentional template change.
"""

import os

import pytest

from mailer.render import render_digest, render_listing


SNAPSHOTS_DIR = os.path.join(os.path.dirname(__file__), "snapshots")


def _snapshot(name: str, actual: str) -> None:
    path = os.path.join(SNAPSHOTS_DIR, name)
    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        with open(path, "w") as f:
            f.write(actual)
    with open(path) as f:
        expected = f.read()
    assert actual == expected, (
        f"{name} drifted. Review the diff; regenerate with UPDATE_SNAPSHOTS=1 pytest."
    )


# ─── fixture data ────────────────────────────────────────────────────────


FIXTURE_LISTINGS = [
    {
        "url": "https://example.org/physics-postdoc",
        "title": "Postdoctoral Fellow in Philosophy of Physics",
        "institution": "University of Example",
        "deadline": "2099-06-15",
        "location": "Example City, ZZ",
        "duration": "2 years",
        "description": "",
        "summary": "Two-year postdoctoral fellowship focused on foundations of quantum mechanics.",
        "aos": ["philosophy-of-physics"],
        "listing_type": "postdoc",
        "source": "FakeSource",
    },
    {
        "url": "https://example.org/hegel-fellow",
        "title": "Research Fellow — Hegel's Logic",
        "institution": "Example Institute for Philosophy",
        "deadline": None,
        "location": "",
        "duration": "",
        "description": "",
        "summary": "One-year visiting fellowship for scholarship on Hegel's Science of Logic.",
        "aos": ["hegel"],
        "listing_type": "fellowship",
        "source": "FakeSource",
    },
    {
        "url": "https://example.org/ethics-tt",
        "title": "Assistant Professor of Ethics",
        "institution": "Example College",
        "deadline": "2099-11-01",
        "location": "Somewhere, ZZ",
        "duration": "",
        "description": "",
        "summary": "Tenure-track position open to any area of ethics.",
        "aos": ["political-philosophy-ethics"],
        "listing_type": "job",
        "source": "FakeSource",
    },
]

INTERESTS = ["philosophy-of-physics", "hegel"]


# ─── digest rendering ────────────────────────────────────────────────────


def test_digest_3_listings_snapshot():
    subject, html = render_digest(
        listings=FIXTURE_LISTINGS,
        interests=INTERESTS,
        rejected_count=4,
        today="2099-04-21",
    )
    assert subject == "[PhilTracker] 2099-04-21 — 3 new listings (2 matching your interests)"
    _snapshot("digest_3listings.html", html)


def test_digest_empty_snapshot():
    subject, html = render_digest(
        listings=[],
        interests=INTERESTS,
        rejected_count=0,
        today="2099-04-21",
    )
    assert subject == "[PhilTracker] 2099-04-21 — no new listings"
    _snapshot("digest_empty.html", html)


def test_digest_interest_sections_come_first():
    """Order: interest slugs in the order listed in `interests`, then the rest alphabetically."""
    subject, html = render_digest(
        listings=FIXTURE_LISTINGS,
        interests=INTERESTS,
        rejected_count=0,
        today="2099-04-21",
    )
    idx_physics = html.find("philosophy-of-physics")
    idx_hegel = html.find("hegel")
    idx_ethics = html.find("political-philosophy-ethics")
    assert 0 <= idx_physics < idx_hegel < idx_ethics


# ─── per-listing rendering ───────────────────────────────────────────────


def test_listing_subject_and_snapshot():
    subject, html = render_listing(FIXTURE_LISTINGS[0])
    assert subject == (
        "[PhilTracker] Postdoctoral Fellow in Philosophy of Physics "
        "— University of Example (2099-06-15)"
    )
    _snapshot("listing_physics.html", html)


def test_listing_no_deadline_subject():
    subject, _ = render_listing(FIXTURE_LISTINGS[1])
    assert subject == (
        "[PhilTracker] Research Fellow — Hegel's Logic "
        "— Example Institute for Philosophy (no deadline)"
    )


# ─── escape defense ──────────────────────────────────────────────────────


def test_summary_with_script_tag_is_escaped():
    """If the LLM's summary contains raw HTML, it must render as escaped text."""
    hostile = dict(FIXTURE_LISTINGS[0])
    hostile["summary"] = "<script>alert(1)</script>"
    _, html = render_digest(
        listings=[hostile],
        interests=INTERESTS,
        rejected_count=0,
        today="2099-04-21",
    )
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_title_with_script_tag_is_escaped():
    hostile = dict(FIXTURE_LISTINGS[0])
    hostile["title"] = "Evil <img onerror=alert(1)>"
    _, html = render_listing(hostile)
    assert "<img onerror=alert(1)>" not in html
    assert "&lt;img onerror=alert(1)&gt;" in html
