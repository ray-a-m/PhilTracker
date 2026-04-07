"""
Scraper for HigherEdJobs (https://www.higheredjobs.com).
Uses Playwright (headless browser) to get past bot protection.
Searches the philosophy faculty category.
"""

import re
import time
from scrapers.base import BaseScraper, Listing


class HigherEdJobsScraper(BaseScraper):
    name = "HigherEdJobs"
    url = "https://www.higheredjobs.com/faculty/search.cfm?JobCat=89"

    # Category 89 = Philosophy
    PAGES_TO_SCRAPE = 3

    def scrape(self) -> list[Listing]:
        """Scrape HigherEdJobs using Playwright for JS rendering."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print(f"[{self.name}] Playwright not installed. Run: pip install playwright && playwright install chromium")
            return []

        listings = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="PhilTracker/0.1 (https://github.com/yourname/philtracker)"
            )

            for page_num in range(1, self.PAGES_TO_SCRAPE + 1):
                url = f"{self.url}&StartRow={1 + (page_num - 1) * 25}"
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(2000)  # let JS render

                    page_listings = self._extract_listings(page, url)
                    if not page_listings:
                        break
                    listings.extend(page_listings)

                    time.sleep(1)
                except Exception as e:
                    print(f"[{self.name}] Error on page {page_num}: {e}")
                    break

            browser.close()

        return listings

    def _extract_listings(self, page, search_url: str) -> list[Listing]:
        """Extract listings from a rendered HigherEdJobs search results page."""
        listings = []

        # Try common result selectors
        rows = page.query_selector_all("div.job-result, div.result-item, tr.job-listing")
        if not rows:
            # Fall back: look for links to job detail pages
            rows = page.query_selector_all("a[href*='/job/detail/']")
            if rows:
                return self._extract_from_links(rows, search_url)

        for row in rows:
            try:
                listing = self._parse_row(row, search_url)
                if listing:
                    listings.append(listing)
            except Exception:
                continue

        return listings

    def _parse_row(self, row, search_url: str) -> Listing | None:
        """Parse a single result row."""
        link = row.query_selector("a[href*='/job/']")
        if not link:
            return None

        title = link.inner_text().strip()
        href = link.get_attribute("href") or ""
        if not title or not href:
            return None

        if href.startswith("/"):
            href = f"https://www.higheredjobs.com{href}"

        # Institution
        inst_el = row.query_selector(".institution, .employer, .company")
        institution = inst_el.inner_text().strip() if inst_el else "Unknown"

        # Location
        loc_el = row.query_selector(".location, .city-state")
        location = loc_el.inner_text().strip() if loc_el else ""

        # Date / deadline
        date_el = row.query_selector(".date, .posted-date, .closing-date")
        deadline = None
        if date_el:
            deadline = self._parse_date(date_el.inner_text().strip())

        # Description snippet
        desc_el = row.query_selector(".description, .snippet, .summary")
        description = desc_el.inner_text().strip() if desc_el else ""

        return Listing(
            title=title,
            institution=institution,
            url=href,
            source=self.name,
            deadline=deadline,
            description=description[:5000],
            location=location,
            listing_type=self._classify_type(f"{title} {description}".lower()),
        )

    def _extract_from_links(self, links, search_url: str) -> list[Listing]:
        """Fall back: extract listings from job detail links."""
        listings = []
        seen = set()

        for link in links:
            title = link.inner_text().strip()
            href = link.get_attribute("href") or ""

            if not title or len(title) < 5 or not href:
                continue
            if href.startswith("/"):
                href = f"https://www.higheredjobs.com{href}"
            if href in seen:
                continue
            seen.add(href)

            # Get parent context
            parent = link.evaluate("el => el.parentElement?.innerText || ''")
            institution = self._extract_institution(parent)
            location = self._extract_location(parent)

            listings.append(Listing(
                title=title,
                institution=institution,
                url=href,
                source=self.name,
                description=parent[:5000] if parent else "",
                location=location,
                listing_type=self._classify_type(f"{title} {parent}".lower()),
            ))

        return listings

    @staticmethod
    def _extract_institution(text: str) -> str:
        uni_match = re.search(
            r"(University of [\w\s]+|[\w\s]+ University|[\w\s]+ College|"
            r"[\w\s]+ Institute|[\w\s]+ School)",
            text[:300],
        )
        return uni_match.group().strip() if uni_match else "Unknown"

    @staticmethod
    def _extract_location(text: str) -> str:
        loc_match = re.search(
            r"(?:Location|Located)[:\s]*([^\n]{3,80})",
            text,
            re.IGNORECASE,
        )
        return loc_match.group(1).strip() if loc_match else ""

    @staticmethod
    def _classify_type(text: str) -> str:
        if any(kw in text for kw in ["postdoc", "post-doc", "postdoctoral"]):
            return "postdoc"
        if any(kw in text for kw in ["fellowship", "fellow"]):
            return "fellowship"
        if any(kw in text for kw in ["phd", "doctoral", "graduate assistant"]):
            return "phd"
        if any(kw in text for kw in ["tenure", "professor", "lecturer", "faculty", "assistant prof"]):
            return "job"
        return "job"  # default for HigherEdJobs

    @staticmethod
    def _parse_date(text: str) -> str | None:
        iso_match = re.search(r"\d{4}-\d{2}-\d{2}", text)
        if iso_match:
            return iso_match.group()

        month_names = {
            "january": "01", "february": "02", "march": "03", "april": "04",
            "may": "05", "june": "06", "july": "07", "august": "08",
            "september": "09", "october": "10", "november": "11", "december": "12",
        }
        pattern = r"(" + "|".join(month_names.keys()) + r")\s+(\d{1,2}),?\s+(\d{4})"
        match = re.search(pattern, text.lower())
        if match:
            month = month_names[match.group(1)]
            day = match.group(2).zfill(2)
            year = match.group(3)
            return f"{year}-{month}-{day}"
        return None


if __name__ == "__main__":
    scraper = HigherEdJobsScraper()
    scraper.run()
