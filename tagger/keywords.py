"""
Keyword-based AOS tagger.
Reads tags.yaml and matches keywords against listing title + description.
"""

import os
import yaml
from scrapers.base import Listing


TAGS_PATH = os.path.join(os.path.dirname(__file__), "tags.yaml")


def load_tags() -> dict[str, list[str]]:
    with open(TAGS_PATH) as f:
        return yaml.safe_load(f)


def tag_listing(listing: Listing, tags: dict[str, list[str]] = None) -> list[str]:
    """
    Return a list of subfield tags that match the listing.
    Matches against title + description, case-insensitive.
    """
    if tags is None:
        tags = load_tags()

    text = f"{listing.title} {listing.description}".lower()
    matched = []

    for tag, keywords in tags.items():
        for keyword in keywords:
            if keyword.lower() in text:
                matched.append(tag)
                break  # one match per tag is enough

    return matched


def tag_listings(listings: list[Listing]) -> list[Listing]:
    """Tag a batch of listings in place and return them."""
    tags = load_tags()
    for listing in listings:
        listing.aos = tag_listing(listing, tags)
    return listings
