"""
Scheduler entry point: runs all scrapers, tags results, and stores them.

Usage:
    python -m scheduler.run_all                     # run everything
    python -m scheduler.run_all philjobs            # run a specific scraper
    python -m scheduler.run_all institutional       # run all institutional scrapers
    python -m scheduler.run_all philjobs spacetime  # run multiple specific scrapers

Designed to be called by GitHub Actions on a daily cron schedule.
"""

import sys
import time
from datetime import date

from scrapers.philjobs import PhilJobsScraper
from scrapers.taking_up_spacetime import TakingUpSpacetimeScraper
from scrapers.academic_jobs_wiki import AcademicJobsWikiScraper
from scrapers.higheredjobs import HigherEdJobsScraper
from scrapers.institutional.runner import run_institutional
from tagger.keywords import tag_listings
from backend.models import init_db, deactivate_expired
from backend.dedup import smart_insert

# Registry of standalone scrapers
SCRAPERS = {
    "philjobs": PhilJobsScraper,
    "spacetime": TakingUpSpacetimeScraper,
    "academic_jobs_wiki": AcademicJobsWikiScraper,
    "higheredjobs": HigherEdJobsScraper,
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

    if selected:
        # Run only selected scrapers
        for name in selected:
            if name == "institutional":
                print(f"\n{'='*60}")
                print("Running: All institutional scrapers")
                print(f"{'='*60}")
                try:
                    listings = run_institutional()
                    print(f"[Institutional] Total: {len(listings)} listings")
                    all_listings.extend(listings)
                except Exception as e:
                    print(f"[Institutional] FAILED: {e}")
            elif name in SCRAPERS:
                listings = run_scraper(SCRAPERS[name])
                all_listings.extend(listings)
                time.sleep(2)
            else:
                print(f"Warning: unknown scraper '{name}'")
                print(f"Available: {list(SCRAPERS.keys()) + ['institutional']}")
    else:
        # Run everything
        for name, scraper_cls in SCRAPERS.items():
            listings = run_scraper(scraper_cls)
            all_listings.extend(listings)
            time.sleep(2)

        # Run all institutional scrapers
        print(f"\n{'='*60}")
        print("Running: All institutional scrapers")
        print(f"{'='*60}")
        try:
            inst_listings = run_institutional()
            print(f"[Institutional] Total: {len(inst_listings)} listings")
            all_listings.extend(inst_listings)
        except Exception as e:
            print(f"[Institutional] FAILED: {e}")

    # Tag all listings
    print(f"\nTagging {len(all_listings)} listings...")
    tagged = tag_listings(all_listings)

    # Store in database with smart deduplication
    new_count = 0
    dup_count = 0
    merged_count = 0
    for listing in tagged:
        result = smart_insert(listing)
        if result == "new":
            new_count += 1
        elif result == "merged":
            merged_count += 1
        else:
            dup_count += 1

    print(f"\nDone! Date: {date.today().isoformat()}")
    print(f"  Total scraped: {len(all_listings)}")
    print(f"  New listings:  {new_count}")
    print(f"  Merged:        {merged_count}")
    print(f"  Duplicates:    {dup_count}")

    return all_listings


def main():
    selected = sys.argv[1:] if len(sys.argv) > 1 else None
    run_all(selected)


if __name__ == "__main__":
    main()
