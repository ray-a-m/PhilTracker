"""
Single-call classify + extract pipeline.

`classify_and_extract(listing)` sends the listing to Haiku 4.5 via the prompt
and tool schema in llm/prompts.py, then maps the returned dict onto the
Listing dataclass fields.

Contract:
- Caller must filter out listings whose URL is already in the DB before
  calling this function (URL cache check lives in scheduler/run_all.py).
- On `is_posting=true`: Listing is enriched with LLM-canonicalized title,
  institution, deadline, location, duration, summary, aos, listing_type,
  confidence. active=True.
- On `is_posting=false`: Listing keeps the scraper's title/institution
  (useful for debug), and gets active=False + the LLM's confidence. The
  row is still persisted so the URL is cached against future re-scrapes.
"""

from typing import Any

from scrapers.base import Listing
from llm.client import call_with_retry
from llm.prompts import build_user_message


def classify_and_extract(listing: Listing, *, client=None) -> Listing:
    """Run the single-shot classifier call and return the enriched Listing."""
    user_msg = build_user_message(listing)
    result = call_with_retry(user_msg, client=client)
    return _apply_result(listing, result)


def _apply_result(listing: Listing, result: dict[str, Any]) -> Listing:
    is_posting = bool(result.get("is_posting", False))
    listing.confidence = float(result.get("confidence", 0.0))
    listing.active = is_posting

    if not is_posting:
        return listing

    # LLM-canonicalized fields override scraper values when non-empty.
    if result.get("title"):
        listing.title = result["title"]
    if result.get("institution"):
        listing.institution = result["institution"]

    # Deadline: LLM returns ISO-8601 string or None. Trust what it gives,
    # falling back to scraper only if the LLM returned null/empty.
    llm_deadline = result.get("deadline")
    if llm_deadline:
        listing.deadline = llm_deadline

    listing.location = result.get("location", "") or listing.location
    listing.duration = result.get("duration", "") or ""
    listing.summary = result.get("summary", "") or ""
    listing.aos = list(result.get("aos", []) or [])
    listing.listing_type = result.get("posting_type", "unknown") or "unknown"

    return listing
