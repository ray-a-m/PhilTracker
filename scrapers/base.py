"""
Base scraper interface. All scrapers must subclass BaseScraper and implement scrape().
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional
import requests
from bs4 import BeautifulSoup


@dataclass
class Listing:
    """A single job or fellowship listing."""
    title: str
    institution: str
    url: str
    source: str
    deadline: Optional[str] = None          # ISO format: "2026-04-08"
    description: str = ""
    location: str = ""
    duration: str = ""
    start_date: str = ""
    aos_raw: str = ""                       # raw AOS string from the source
    salary: str = ""
    date_scraped: str = field(default_factory=lambda: date.today().isoformat())
    aos: list[str] = field(default_factory=list)  # filled by tagger, not scraper
    listing_type: str = "unknown"           # "job", "fellowship", "postdoc", "phd"

    def __hash__(self):
        return hash((self.title, self.institution, self.url))

    def __eq__(self, other):
        return self.url == other.url


class BaseScraper:
    """
    Subclass this for each source.

    Required:
        name: str           Human-readable name of the source.
        url: str            Base URL of the source.
        scrape() -> list[Listing]
    """
    name: str = "Unknown"
    url: str = ""

    def fetch(self, url: str = None, params: dict = None) -> BeautifulSoup:
        """Fetch a page and return a BeautifulSoup object."""
        target = url or self.url
        headers = {
            "User-Agent": "PhilTracker/0.1 (https://github.com/yourname/philtracker)"
        }
        response = requests.get(target, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")

    def scrape(self) -> list[Listing]:
        """Override this. Return a list of Listing objects."""
        raise NotImplementedError("Subclasses must implement scrape()")

    def run(self):
        """Convenience method: scrape and print results."""
        listings = self.scrape()
        print(f"[{self.name}] Found {len(listings)} listings")
        for listing in listings:
            deadline = listing.deadline or "no deadline"
            print(f"  - {listing.title} @ {listing.institution} ({deadline})")
        return listings
