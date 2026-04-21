"""
HTML rendering for the digest and per-listing emails.

Both paths share `mailer/templates/listing.html.j2` so the per-entry layout
stays identical across the digest and the pinnable per-listing emails.
jinja2 autoescape is enabled via `select_autoescape` — any LLM-extracted
text (title, summary, etc.) containing HTML will render as escaped text,
not as live markup.
"""

import os
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape


TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(
        enabled_extensions=("html", "j2", "html.j2"),
        default_for_string=True,
        default=True,
    ),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _assign_section(listing: dict[str, Any], interests: list[str]) -> str:
    """First interest-matching aos; else first aos; else 'other'."""
    aos = listing.get("aos") or []
    for interest in interests:
        if interest in aos:
            return interest
    if aos:
        return aos[0]
    return "other"


def _group_by_section(
    listings: list[dict[str, Any]], interests: list[str]
) -> list[tuple[str, list[dict[str, Any]]]]:
    """Group listings into sections; interest-matching slugs first (in the
    order the user listed them), then the remaining slugs alphabetically."""
    buckets: dict[str, list[dict[str, Any]]] = {}
    for listing in listings:
        section = _assign_section(listing, interests)
        buckets.setdefault(section, []).append(listing)

    ordered: list[tuple[str, list[dict[str, Any]]]] = []
    for interest in interests:
        if interest in buckets:
            ordered.append((interest, buckets.pop(interest)))
    for slug in sorted(buckets):
        ordered.append((slug, buckets.pop(slug)))
    return ordered


def render_digest(
    listings: list[dict[str, Any]],
    interests: list[str],
    rejected_count: int,
    today: str,
) -> tuple[str, str]:
    """Return (subject, html_body) for the day's digest email."""
    interest_set = set(interests)
    interest_match_count = sum(
        1 for l in listings if set(l.get("aos") or []) & interest_set
    )

    if not listings:
        subject = f"[PhilTracker] {today} — no new listings"
    else:
        plural = "s" if len(listings) != 1 else ""
        subject = (
            f"[PhilTracker] {today} — "
            f"{len(listings)} new listing{plural} "
            f"({interest_match_count} matching your interests)"
        )

    sections = _group_by_section(listings, interests)
    html = _env.get_template("digest.html.j2").render(
        today=today,
        listings=listings,
        sections=sections,
        interests=interests,
        interest_match_count=interest_match_count,
        rejected_count=rejected_count,
    )
    return subject, html


def render_listing(listing: dict[str, Any]) -> tuple[str, str]:
    """Return (subject, html_body) for a per-listing email."""
    title = listing.get("title") or "(untitled)"
    institution = listing.get("institution") or ""
    deadline = listing.get("deadline") or "no deadline"

    parts = [f"[PhilTracker] {title}"]
    if institution:
        parts.append(f" — {institution}")
    parts.append(f" ({deadline})")
    subject = "".join(parts)

    html = _env.get_template("listing.html.j2").render(listing=listing)
    return subject, html
