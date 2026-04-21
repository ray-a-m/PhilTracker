"""Tests for the taxonomy loader. Keyword-matching was removed — the LLM
handles all tagging from content now."""

from tagger.keywords import load_tags


def test_load_tags_returns_dict():
    tags = load_tags()
    assert isinstance(tags, dict)
    assert all(isinstance(v, list) for v in tags.values())


def test_core_taxonomy_slugs_present():
    """Spec-critical slugs that the digest ranking + ground-truth rely on."""
    tags = load_tags()
    required = {
        "philosophy-of-physics",
        "philosophy-of-science",
        "kant",
        "hegel",
    }
    missing = required - tags.keys()
    assert not missing, f"missing slugs: {missing}"


def test_no_empty_keyword_lists():
    tags = load_tags()
    empty = [slug for slug, kws in tags.items() if not kws]
    assert not empty, f"slugs with no keywords: {empty}"
