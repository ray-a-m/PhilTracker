"""
Smart deduplication for PhilTracker listings.

Two checks before insert:
  1. Exact URL match — the schema UNIQUE constraint also enforces this
  2. Fuzzy match — same institution + similar title, across sources

When a fuzzy duplicate is found, the new listing is dropped (returns
"duplicate"). LLM-canonicalized title/institution values make fuzzy matches
both rarer and cleaner than the pre-LLM pipeline.
"""

import re
import string

from backend.models import get_db, insert_listing


STOP_WORDS = {
    "postdoctoral", "postdoc", "post-doc", "fellowship", "position",
    "researcher", "associate", "assistant", "senior", "junior",
    "tenure-track", "tenure", "track", "fixed-term", "temporary",
    "permanent", "full-time", "part-time", "in", "of", "the", "a",
    "an", "and", "at", "for", "to", "with", "on", "&", "-", "–",
    "professor", "lecturer", "reader", "faculty", "member",
    "research", "visiting", "scholar", "open", "call",
}

SIMILARITY_THRESHOLD = 0.70


def normalize_institution(name: str) -> str:
    s = name.lower().strip()
    s = s.translate(str.maketrans("", "", string.punctuation))
    s = s.replace("university", "univ").replace("université", "univ")
    s = s.replace("institute", "inst").replace("institut", "inst")
    s = s.replace("center", "ctr").replace("centre", "ctr")
    s = s.replace("department", "dept")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_title_keywords(title: str) -> set[str]:
    words = re.findall(r"[a-z]+", title.lower())
    return {w for w in words if w not in STOP_WORDS and len(w) > 2}


def title_similarity(keywords_a: set[str], keywords_b: set[str]) -> float:
    if not keywords_a or not keywords_b:
        return 0.0
    intersection = keywords_a & keywords_b
    smaller = min(len(keywords_a), len(keywords_b))
    if smaller == 0:
        return 0.0
    return len(intersection) / smaller


def find_fuzzy_duplicate(listing, conn) -> dict | None:
    """Return the matching row if a fuzzy duplicate exists, else None."""
    norm_inst = normalize_institution(listing.institution)
    new_keywords = extract_title_keywords(listing.title)

    if not norm_inst or norm_inst == "unknown" or not new_keywords:
        return None

    rows = conn.execute(
        "SELECT id, title, institution, url FROM listings WHERE active = 1"
    ).fetchall()

    for row in rows:
        row_dict = dict(row)
        if normalize_institution(row_dict["institution"]) != norm_inst:
            continue
        row_keywords = extract_title_keywords(row_dict["title"])
        if title_similarity(new_keywords, row_keywords) >= SIMILARITY_THRESHOLD:
            return row_dict

    return None


def smart_insert(listing) -> str:
    """
    Insert a listing with fuzzy-match dedup on top of URL uniqueness.

    Returns:
        "new"       — inserted
        "duplicate" — exact URL match OR fuzzy match against an active row
    """
    conn = get_db()
    try:
        if conn.execute(
            "SELECT 1 FROM listings WHERE url = ?", (listing.url,)
        ).fetchone():
            return "duplicate"
        if find_fuzzy_duplicate(listing, conn) is not None:
            return "duplicate"
    finally:
        conn.close()

    return "new" if insert_listing(listing) else "duplicate"
