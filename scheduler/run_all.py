"""
Scheduler entry point: runs all scrapers, tags results, and stores them.

Usage:
    python -m scheduler.run_all          # run all scrapers
    python -m scheduler.run_all philjobs # run a specific scraper

Designed to be called by GitHub Actions on a daily cron schedule.
"""

import sys
import time
from datetime import date

from scrapers.philjobs import PhilJobsScraper
from scrapers.taking_up_spacetime import TakingUpSpacetimeScraper
from tagger.keywords import tag_listings
from backend.models import init_db, insert_listing, deactivate_expired

# Registry of all scrapers
SCRAPERS = {
    "philjobs": PhilJobsScraper,
    "taking_up_spacetime": TakingUpSpacetimeScraper,
}


def run_scraper(scraper_cls) -> list:
    """Run a single scraper, return its listings."""
    scraper = scraper_cls()
    print(f"\n{'='*60}")
    print(f"Running: {scraper.name}")
    print(f"URL:     {scraper.url}")
    print(f"{'='*60}")

    try:
        listings = scraper.scrape()
        print(f"[{scraper.name}] Scraped {len(listings)} listings")
        return listings
    except Exception as e:
        print(f"[{scraper.name}] FAILED: {e}")
        return []


def run_all(selected: list[str] | None = None):
    """Run all (or selected) scrapers, tag, and store results."""
    init_db()
    deactivate_expired()

    all_listings = []
    scrapers_to_run = SCRAPERS

    if selected:
        scrapers_to_run = {
            k: v for k, v in SCRAPERS.items() if k in selected
        }
        unknown = set(selected) - set(SCRAPERS.keys())
        if unknown:
            print(f"Warning: unknown scrapers ignored: {unknown}")
            print(f"Available: {list(SCRAPERS.keys())}")

    for name, scraper_cls in scrapers_to_run.items():
        listings = run_scraper(scraper_cls)
        all_listings.extend(listings)
        # Be polite: pause between scrapers
        time.sleep(2)

    # Tag all listings
    print(f"\nTagging {len(all_listings)} listings...")
    tagged = tag_listings(all_listings)

    # Store in database
    new_count = 0
    dup_count = 0
    for listing in tagged:
        if insert_listing(listing):
            new_count += 1
        else:
            dup_count += 1

    print(f"\nDone! Date: {date.today().isoformat()}")
    print(f"  Total scraped: {len(all_listings)}")
    print(f"  New listings:  {new_count}")
    print(f"  Duplicates:    {dup_count}")

    return all_listings


def main():
    selected = sys.argv[1:] if len(sys.argv) > 1 else None
    run_all(selected)


if __name__ == "__main__":
    main()
