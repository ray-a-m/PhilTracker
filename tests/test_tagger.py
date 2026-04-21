"""Tests for the keyword tagger."""

from scrapers.base import Listing
from tagger.keywords import tag_listing, tag_listings, load_tags


def _make_listing(title="Test", description=""):
    return Listing(
        title=title, institution="Test Uni", url="https://example.com/1", source="test",
        description=description,
    )


def test_load_tags():
    tags = load_tags()
    assert isinstance(tags, dict)
    assert "philosophy-of-physics" in tags
    assert "kant" in tags
    assert "hegel" in tags


def test_physics_tag():
    listing = _make_listing("Postdoc in Philosophy of Physics", "Working on quantum gravity and spacetime.")
    tags_dict = load_tags()
    result = tag_listing(listing, tags_dict)
    assert "philosophy-of-physics" in result


def test_hegel_tag():
    listing = _make_listing("Research Fellow", "This position focuses on Hegel's Science of Logic and absolute idealism.")
    tags_dict = load_tags()
    result = tag_listing(listing, tags_dict)
    assert "hegel" in result


def test_kant_tag():
    listing = _make_listing("Research Fellow", "Working on transcendental idealism and the Critique of Pure Reason.")
    tags_dict = load_tags()
    result = tag_listing(listing, tags_dict)
    assert "kant" in result


def test_no_false_tags():
    listing = _make_listing("Administrative Assistant", "Filing paperwork and scheduling meetings.")
    tags_dict = load_tags()
    result = tag_listing(listing, tags_dict)
    assert result == []


def test_multiple_tags():
    listing = _make_listing(
        "Postdoc in Philosophy of Science",
        "Research on scientific realism and quantum mechanics in the context of formal epistemology and bayesian methods.",
    )
    tags_dict = load_tags()
    result = tag_listing(listing, tags_dict)
    assert "philosophy-of-science" in result
    assert "philosophy-of-physics" in result
    assert "formal-epistemology" in result


def test_case_insensitive():
    listing = _make_listing("QUANTUM MECHANICS POSITION")
    tags_dict = load_tags()
    result = tag_listing(listing, tags_dict)
    assert "philosophy-of-physics" in result


def test_tag_listings_batch():
    listings = [
        _make_listing("Postdoc on Hegel"),
        _make_listing("Fellow in consciousness studies", "phenomenal consciousness and qualia"),
    ]
    tagged = tag_listings(listings)
    assert tagged[0].aos == ["hegel"]
    assert "philosophy-of-mind" in tagged[1].aos
