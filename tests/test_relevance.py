"""Tests for relevance scoring."""

import json
from backend.relevance import score_listing, score_listings


def _make_listing_dict(title="Test", description="", aos=None, **kwargs):
    d = {
        "title": title,
        "description": description,
        "aos": json.dumps(aos or []),
        "institution": "Test Uni",
        "url": "https://example.com/1",
        "deadline": "2026-06-01",
    }
    d.update(kwargs)
    return d


def test_physics_profile_scores_physics_higher():
    """A quantum gravity postdoc at Geneva should score higher than a bioethics lecturer."""
    interests = {"philosophy-of-physics", "philosophy-of-science"}

    physics_listing = _make_listing_dict(
        title="Postdoctoral Researcher in Quantum Gravity",
        description="Working on foundations of quantum mechanics and spacetime at the Geneva Symmetry Group.",
        aos=["philosophy-of-physics", "philosophy-of-science"],
    )

    bioethics_listing = _make_listing_dict(
        title="Lecturer in Bioethics",
        description="Teaching applied ethics and research ethics at Georgetown.",
        aos=["political-philosophy-ethics", "ethics-of-science"],
    )

    physics_score = score_listing(interests, physics_listing)
    bioethics_score = score_listing(interests, bioethics_listing)

    assert physics_score > bioethics_score
    assert physics_score > 50  # should be high
    assert bioethics_score < 30  # should be low


def test_idealism_profile():
    """A German idealism specialist should get high scores on Hegel positions."""
    interests = {"german-idealism"}

    hegel = _make_listing_dict(
        title="Postdoc on Hegel's Science of Logic",
        description="Research on absolute idealism and dialectic in the Hegel tradition.",
        aos=["german-idealism"],
    )

    score = score_listing(interests, hegel)
    assert score >= 70


def test_no_matching_tags():
    """A listing with no matching tags should score low."""
    interests = {"philosophy-of-physics"}

    listing = _make_listing_dict(
        title="Assistant Professor of Medieval Philosophy",
        description="Specialization in Thomas Aquinas and scholasticism.",
        aos=["historical-philosophy"],
    )

    score = score_listing(interests, listing)
    assert score < 20


def test_empty_profile():
    """An empty profile should return score 0."""
    listing = _make_listing_dict(aos=["philosophy-of-physics"])
    assert score_listing(set(), listing) == 0


def test_listing_with_no_tags():
    """A listing with no AOS tags should still get some score from keyword matching."""
    interests = {"philosophy-of-physics"}
    listing = _make_listing_dict(
        title="Research on quantum mechanics foundations",
        description="This position involves quantum gravity research.",
        aos=[],
    )
    score = score_listing(interests, listing)
    # Should get some keyword bonus even without tag match
    assert score > 0


def test_multiple_interest_matches():
    """More matching interests = higher score."""
    listing = _make_listing_dict(
        aos=["philosophy-of-physics", "philosophy-of-science", "formal-epistemology"],
    )

    one_match = score_listing({"philosophy-of-physics"}, listing)
    two_matches = score_listing({"philosophy-of-physics", "philosophy-of-science"}, listing)
    three_matches = score_listing({"philosophy-of-physics", "philosophy-of-science", "formal-epistemology"}, listing)

    assert three_matches >= two_matches >= one_match


def test_score_listings_sorts_by_relevance():
    """score_listings should sort by relevance descending."""
    interests = {"philosophy-of-physics"}

    listings = [
        _make_listing_dict(title="Ethics job", aos=["political-philosophy-ethics"]),
        _make_listing_dict(title="Physics job", aos=["philosophy-of-physics"]),
        _make_listing_dict(title="Logic job", aos=["logic"]),
    ]

    scored = score_listings(interests, listings)

    assert scored[0]["title"] == "Physics job"
    assert scored[0]["relevance"] >= scored[1]["relevance"]
    assert scored[1]["relevance"] >= scored[2]["relevance"]
