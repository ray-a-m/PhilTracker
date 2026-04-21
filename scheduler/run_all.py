"""
PhilTracker nightly pipeline.

    init_db → deactivate_expired → scrape all → URL-cache filter
    → classify_and_extract (LLM) → smart_insert → query today's active
    → render digest + per-listing → send_run

Wrapped in top-level try/except so any failure dispatches
`send_failure_notice` before re-raising. Silence is the failure mode to avoid.

Usage:
    python -m scheduler.run_all                     # run everything, send for real
    python -m scheduler.run_all --dry-run           # run everything, print emails to stdout
    python -m scheduler.run_all philjobs            # single scraper
    python -m scheduler.run_all philjobs spacetime  # multiple specific scrapers
    python -m scheduler.run_all institutional       # all institutional scrapers
"""

import argparse
import os
import sys
import time
from datetime import date

import yaml
from dotenv import load_dotenv

from backend import models
from backend.dedup import smart_insert
from llm.extract import classify_and_extract
from mailer.render import render_digest, render_listing
from mailer.send import send_failure_notice, send_run
from scrapers.academic_jobs_wiki import AcademicJobsWikiScraper
from scrapers.higheredjobs import HigherEdJobsScraper
from scrapers.institutional.runner import run_institutional
from scrapers.philjobs import PhilJobsScraper
from scrapers.taking_up_spacetime import TakingUpSpacetimeScraper


SCRAPERS = {
    "philjobs": PhilJobsScraper,
    "spacetime": TakingUpSpacetimeScraper,
    "academic_jobs_wiki": AcademicJobsWikiScraper,
    "higheredjobs": HigherEdJobsScraper,
}

CONFIG_PATH = os.environ.get("PHILTRACKER_CONFIG", "config.local.yaml")


def _load_interests() -> list[str]:
    if not os.path.exists(CONFIG_PATH):
        print(
            f"[warn] {CONFIG_PATH} not found — running without interest prioritization",
            file=sys.stderr,
        )
        return []
    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f) or {}
    return list(cfg.get("interests", []))


def _run_scraper(cls) -> list:
    scraper = cls()
    print(f"\n{'=' * 60}\nRunning: {scraper.name}\nURL:     {scraper.url}\n{'=' * 60}")
    try:
        listings = scraper.scrape()
        print(f"[{scraper.name}] scraped {len(listings)} listings")
        return listings
    except Exception as e:
        print(f"[{scraper.name}] FAILED: {e}", file=sys.stderr)
        return []


def _scrape_selected(selected: list[str] | None) -> list:
    targets = selected if selected else list(SCRAPERS.keys()) + ["institutional"]
    all_listings: list = []
    for name in targets:
        if name == "institutional":
            print(f"\n{'=' * 60}\nRunning: all institutional scrapers\n{'=' * 60}")
            try:
                inst = run_institutional()
                print(f"[institutional] total: {len(inst)} listings")
                all_listings.extend(inst)
            except Exception as e:
                print(f"[institutional] FAILED: {e}", file=sys.stderr)
        elif name in SCRAPERS:
            all_listings.extend(_run_scraper(SCRAPERS[name]))
            time.sleep(1)
        else:
            print(f"[warn] unknown scraper '{name}'", file=sys.stderr)
    return all_listings


def pipeline(selected: list[str] | None, dry_run: bool) -> None:
    models.init_db()
    models.deactivate_expired()

    scraped = _scrape_selected(selected)
    print(f"\nTotal scraped: {len(scraped)}")

    known_urls = models.get_known_urls()
    fresh = [l for l in scraped if l.url not in known_urls]
    print(
        f"URL cache: {len(fresh)} fresh, "
        f"{len(scraped) - len(fresh)} already in DB (skipping LLM)"
    )

    for idx, listing in enumerate(fresh, start=1):
        print(f"  [{idx}/{len(fresh)}] classifying {listing.url}")
        classify_and_extract(listing)

    new_count = dup_count = 0
    for listing in fresh:
        if smart_insert(listing) == "new":
            new_count += 1
        else:
            dup_count += 1
    print(f"Inserted: {new_count} new, {dup_count} duplicate/fuzzy-match")

    today = date.today().isoformat()
    active_today = models.get_new_active_listings(today)
    rejected_today = models.count_rejected_today(today)
    interests = _load_interests()

    digest_subject, digest_html = render_digest(
        listings=active_today,
        interests=interests,
        rejected_count=rejected_today,
        today=today,
    )
    per_listing = [render_listing(l) for l in active_today]

    send_run(
        digest_subject=digest_subject,
        digest_html=digest_html,
        per_listing_emails=per_listing,
        dry_run=dry_run,
    )
    print(
        f"\nDone. {len(active_today)} active in digest, "
        f"{rejected_today} rejected today."
    )


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="PhilTracker nightly runner")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print emails to stdout instead of sending via SMTP",
    )
    parser.add_argument(
        "scrapers", nargs="*",
        help=f"Optional scraper names; choose from {list(SCRAPERS) + ['institutional']}",
    )
    args = parser.parse_args()

    try:
        pipeline(selected=args.scrapers or None, dry_run=args.dry_run)
    except Exception as e:
        reason = f"{type(e).__name__}: {e}"
        print(f"\n[FATAL] {reason}", file=sys.stderr)
        send_failure_notice(reason, dry_run=args.dry_run)
        raise


if __name__ == "__main__":
    main()
