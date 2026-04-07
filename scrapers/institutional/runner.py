"""
Institutional scraper runner.
Reads config.yaml, instantiates the appropriate scraper type for each site,
runs them all, and returns combined results.
"""

import os
import time
import yaml
from scrapers.base import Listing
from scrapers.institutional.wordpress_scraper import WordPressScraper
from scrapers.institutional.static_scraper import StaticScraper


CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")

SCRAPER_TYPES = {
    "wordpress": WordPressScraper,
    "static": StaticScraper,
}


def load_config() -> list[dict]:
    """Load institutional site configs from YAML."""
    with open(CONFIG_PATH) as f:
        data = yaml.safe_load(f)
    return data.get("sites", [])


def run_institutional(sites: list[dict] | None = None) -> list[Listing]:
    """
    Run all (or specified) institutional scrapers.
    Returns combined list of Listings.
    """
    if sites is None:
        sites = load_config()

    all_listings = []

    for site in sites:
        name = site.get("name", "Unknown")
        scraper_type = site.get("type", "static")
        scraper_cls = SCRAPER_TYPES.get(scraper_type, StaticScraper)

        print(f"  [{name}] ({scraper_type}) {site.get('url', '')}")

        try:
            scraper = scraper_cls(site)
            listings = scraper.scrape()
            print(f"  [{name}] Found {len(listings)} listings")
            all_listings.extend(listings)
        except Exception as e:
            print(f"  [{name}] FAILED: {e}")

        time.sleep(1)  # polite delay between sites

    return all_listings


def run_institutional_by_subfield(subfield: str) -> list[Listing]:
    """Run only institutional scrapers matching a given subfield."""
    sites = load_config()
    filtered = [s for s in sites if s.get("subfield") == subfield]
    return run_institutional(filtered)


if __name__ == "__main__":
    import sys
    listings = run_institutional()
    print(f"\nTotal institutional listings: {len(listings)}")
    for listing in listings:
        deadline = listing.deadline or "no deadline"
        print(f"  - {listing.title} @ {listing.institution} ({deadline})")
