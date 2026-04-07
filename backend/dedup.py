"""
Smart deduplication for PhilTracker listings.

Before inserting a listing, checks:
1. Exact URL match (existing behavior)
2. Fuzzy match: same institution + similar title → same job

When a duplicate is found, merges: keeps the entry with more fields populated
and the longer description, stores both URLs in secondary_urls.
"""

import json
import re
import string
import sqlite3
from backend.models import get_db
from datetime import date


# Words to strip when comparing titles for similarity
STOP_WORDS = {
    "postdoctoral", "postdoc", "post-doc", "fellowship", "position",
    "researcher", "associate", "assistant", "senior", "junior",
    "tenure-track", "tenure", "track", "fixed-term", "temporary",
    "permanent", "full-time", "part-time", "in", "of", "the", "a",
    "an", "and", "at", "for", "to", "with", "on", "&", "-", "–",
    "professor", "lecturer", "reader", "faculty", "member",
    "research", "visiting", "scholar", "open", "call",
}

# Minimum keyword overlap ratio to consider titles as matching
SIMILARITY_THRESHOLD = 0.70


def normalize_institution(name: str) -> str:
    """Normalize institution name for comparison."""
    s = name.lower().strip()
    # Remove punctuation
    s = s.translate(str.maketrans("", "", string.punctuation))
    # Normalize common variations
    s = s.replace("university", "univ").replace("université", "univ")
    s = s.replace("institute", "inst").replace("institut", "inst")
    s = s.replace("center", "ctr").replace("centre", "ctr")
    s = s.replace("department", "dept")
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_title_keywords(title: str) -> set[str]:
    """Extract meaningful keywords from a title, stripping stop words."""
    words = re.findall(r"[a-z]+", title.lower())
    return {w for w in words if w not in STOP_WORDS and len(w) > 2}


def title_similarity(keywords_a: set[str], keywords_b: set[str]) -> float:
    """Compute keyword overlap ratio between two title keyword sets."""
    if not keywords_a or not keywords_b:
        return 0.0
    intersection = keywords_a & keywords_b
    # Use the smaller set as denominator (asymmetric Jaccard-like)
    smaller = min(len(keywords_a), len(keywords_b))
    if smaller == 0:
        return 0.0
    return len(intersection) / smaller


def find_fuzzy_duplicate(listing, conn) -> dict | None:
    """
    Check if a fuzzy duplicate exists in the database.
    Returns the matching row as a dict, or None.
    """
    norm_inst = normalize_institution(listing.institution)
    new_keywords = extract_title_keywords(listing.title)

    if not norm_inst or norm_inst == "unknown" or not new_keywords:
        return None

    # Query active listings — we only need title, institution, id
    rows = conn.execute(
        "SELECT id, title, institution, url, description, deadline, "
        "location, duration, start_date, aos_raw, salary, "
        "secondary_urls, source, listing_type, aos "
        "FROM listings WHERE active = 1"
    ).fetchall()

    for row in rows:
        row_dict = dict(row)
        row_norm_inst = normalize_institution(row_dict["institution"])

        # Institution must match
        if row_norm_inst != norm_inst:
            continue

        # Title keywords must overlap above threshold
        row_keywords = extract_title_keywords(row_dict["title"])
        sim = title_similarity(new_keywords, row_keywords)
        if sim >= SIMILARITY_THRESHOLD:
            return row_dict

    return None


def count_populated_fields(listing) -> int:
    """Count how many optional fields are populated on a Listing object."""
    count = 0
    for field in ("deadline", "description", "location", "duration",
                  "start_date", "aos_raw", "salary"):
        val = getattr(listing, field, "")
        if val:
            count += 1
    return count


def count_populated_fields_row(row: dict) -> int:
    """Count how many optional fields are populated on a DB row."""
    count = 0
    for field in ("deadline", "description", "location", "duration",
                  "start_date", "aos_raw", "salary"):
        if row.get(field):
            count += 1
    return count


def merge_secondary_urls(existing_urls_json: str | None, new_url: str, existing_url: str) -> str:
    """Merge URLs into the secondary_urls JSON list."""
    urls = set()
    if existing_urls_json:
        try:
            urls = set(json.loads(existing_urls_json))
        except (json.JSONDecodeError, TypeError):
            pass
    urls.add(new_url)
    urls.add(existing_url)
    return json.dumps(sorted(urls))


def smart_insert(listing) -> str:
    """
    Insert a listing with smart deduplication.

    Returns:
        "new"       — inserted as new listing
        "duplicate" — exact URL match, skipped
        "merged"    — fuzzy match found, merged fields
    """
    conn = get_db()
    try:
        # 1. Check exact URL match
        existing = conn.execute(
            "SELECT id FROM listings WHERE url = ?", (listing.url,)
        ).fetchone()
        if existing:
            return "duplicate"

        # 2. Check fuzzy match
        fuzzy_match = find_fuzzy_duplicate(listing, conn)
        if fuzzy_match:
            _merge_into_existing(fuzzy_match, listing, conn)
            return "merged"

        # 3. No match — insert new
        conn.execute(
            """INSERT INTO listings
               (title, institution, url, source, deadline, description,
                location, duration, start_date, aos_raw, salary,
                secondary_urls, date_scraped, date_first_seen, aos, listing_type)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                listing.title,
                listing.institution,
                listing.url,
                listing.source,
                listing.deadline,
                listing.description,
                listing.location,
                listing.duration,
                listing.start_date,
                listing.aos_raw,
                listing.salary,
                "[]",
                listing.date_scraped,
                date.today().isoformat(),
                json.dumps(listing.aos),
                listing.listing_type,
            ),
        )
        conn.commit()
        return "new"

    except sqlite3.IntegrityError:
        return "duplicate"
    finally:
        conn.close()


def _merge_into_existing(existing: dict, new_listing, conn):
    """Merge a new listing into an existing DB row, keeping the best data."""
    row_id = existing["id"]

    new_field_count = count_populated_fields(new_listing)
    existing_field_count = count_populated_fields_row(existing)
    new_is_better = new_field_count > existing_field_count

    # Merge secondary URLs
    secondary = merge_secondary_urls(
        existing.get("secondary_urls"),
        new_listing.url,
        existing["url"],
    )

    # For each field, pick the better value (prefer non-empty, longer descriptions)
    title = new_listing.title if new_is_better else existing["title"]
    institution = new_listing.institution if new_is_better else existing["institution"]
    source = f"{existing['source']}, {new_listing.source}" if new_listing.source not in existing["source"] else existing["source"]

    # Keep the longer description
    new_desc = new_listing.description or ""
    existing_desc = existing.get("description", "") or ""
    description = new_desc if len(new_desc) > len(existing_desc) else existing_desc

    # For structured fields, prefer non-empty
    deadline = new_listing.deadline or existing.get("deadline") or None
    location = new_listing.location or existing.get("location", "") or ""
    duration = new_listing.duration or existing.get("duration", "") or ""
    start_date = new_listing.start_date or existing.get("start_date", "") or ""
    aos_raw = new_listing.aos_raw or existing.get("aos_raw", "") or ""
    salary = new_listing.salary or existing.get("salary", "") or ""

    # Merge AOS tags
    existing_aos = []
    try:
        existing_aos = json.loads(existing.get("aos", "[]"))
    except (json.JSONDecodeError, TypeError):
        pass
    merged_aos = list(set(existing_aos + new_listing.aos))

    # Listing type: prefer non-"unknown"
    listing_type = existing.get("listing_type", "unknown")
    if listing_type == "unknown" and new_listing.listing_type != "unknown":
        listing_type = new_listing.listing_type

    conn.execute(
        """UPDATE listings SET
            title = ?, institution = ?, source = ?, deadline = ?,
            description = ?, location = ?, duration = ?, start_date = ?,
            aos_raw = ?, salary = ?, secondary_urls = ?, aos = ?,
            listing_type = ?, date_scraped = ?
           WHERE id = ?""",
        (
            title, institution, source, deadline,
            description, location, duration, start_date,
            aos_raw, salary, secondary, json.dumps(merged_aos),
            listing_type, date.today().isoformat(),
            row_id,
        ),
    )
    conn.commit()
