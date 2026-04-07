"""
Relevance scoring for PhilTracker.

Given a user profile (set of interest tags) and a listing,
computes a 0–100 relevance score based on tag overlap and keyword matches.
"""

import json
from tagger.keywords import load_tags


_TAG_KEYWORDS_CACHE = None


def _get_tag_keywords() -> dict[str, list[str]]:
    """Load and cache the tag -> keywords mapping."""
    global _TAG_KEYWORDS_CACHE
    if _TAG_KEYWORDS_CACHE is None:
        _TAG_KEYWORDS_CACHE = load_tags()
    return _TAG_KEYWORDS_CACHE


def score_listing(interests: set[str], listing: dict) -> int:
    """
    Score a listing's relevance to a user profile.

    Args:
        interests: set of tag strings like {"philosophy-of-physics", "german-idealism"}
        listing: dict with keys "aos" (JSON string of tags), "title", "description"

    Returns:
        Integer score 0–100
    """
    if not interests:
        return 0

    # Parse listing tags
    listing_tags = set()
    aos_raw = listing.get("aos", "[]")
    if isinstance(aos_raw, str):
        try:
            listing_tags = set(json.loads(aos_raw))
        except (json.JSONDecodeError, TypeError):
            pass
    elif isinstance(aos_raw, list):
        listing_tags = set(aos_raw)

    # Component 1: Tag overlap (0–70 points)
    # More matching tags = higher score
    tag_matches = interests & listing_tags
    if interests:
        tag_ratio = len(tag_matches) / len(interests)
    else:
        tag_ratio = 0.0
    tag_score = min(70, int(tag_ratio * 70))

    # Component 2: Keyword bonus (0–30 points)
    # Check if the listing text contains keywords from the user's interest tags
    text = f"{listing.get('title', '')} {listing.get('description', '')}".lower()
    keyword_hits = 0
    total_keywords = 0
    tag_keywords = _get_tag_keywords()

    for interest_tag in interests:
        keywords = tag_keywords.get(interest_tag, [])
        total_keywords += len(keywords)
        for kw in keywords:
            if kw.lower() in text:
                keyword_hits += 1

    if total_keywords > 0:
        keyword_ratio = keyword_hits / total_keywords
        keyword_score = min(30, int(keyword_ratio * 100))
    else:
        keyword_score = 0

    return min(100, tag_score + keyword_score)


def score_listings(interests: set[str], listings: list[dict]) -> list[dict]:
    """
    Score and sort a list of listings by relevance.
    Adds a "relevance" key to each listing dict.
    Returns listings sorted by relevance (descending), then deadline (ascending).
    """
    for listing in listings:
        listing["relevance"] = score_listing(interests, listing)

    listings.sort(key=lambda l: (-l["relevance"], l.get("deadline") or "9999-12-31"))
    return listings
