"""
Scraper for PhilJobs (https://philjobs.org).
Pulls job and fellowship listings from the PhilJobs RSS/listing pages.
"""

import re
from scrapers.base import BaseScraper, Listing


class PhilJobsScraper(BaseScraper):
    name = "PhilJobs"
    url = "https://philjobs.org/job/search"

    # PhilJobs listing type slugs -> our listing_type
    TYPE_MAP = {
        "postdoc": "postdoc",
        "tenure": "job",
        "fixed-term": "job",
        "graduate": "phd",
        "fellowship": "fellowship",
    }

    def scrape(self) -> list[Listing]:
        listings = []

        # PhilJobs paginates; scrape first 3 pages to stay polite
        for page in range(1, 4):
            params = {"page": page}
            try:
                soup = self.fetch(params=params)
            except Exception as e:
                print(f"[{self.name}] Error fetching page {page}: {e}")
                break

            job_rows = soup.select("table.joblist tr.job-listing, div.job-listing, div.listing-item")
            if not job_rows:
                # Fall back: try generic row/link patterns on the page
                job_rows = soup.select("tr:has(a[href*='/job/show/'])")

            if not job_rows:
                break  # no more results

            for row in job_rows:
                listing = self._parse_row(row)
                if listing:
                    listings.append(listing)

        return listings

    def _parse_row(self, row) -> Listing | None:
        """Parse a single job row/card into a Listing."""
        # Find the main link
        link = row.select_one("a[href*='/job/show/']") or row.select_one("a[href*='philjobs.org']")
        if not link:
            return None

        title = link.get_text(strip=True)
        href = link.get("href", "")
        if not title or not href:
            return None

        # Ensure absolute URL
        if href.startswith("/"):
            href = f"https://philjobs.org{href}"

        # Institution: often in a separate cell or span
        inst_el = (
            row.select_one("td.institution")
            or row.select_one("span.institution")
            or row.select_one(".employer")
        )
        institution = inst_el.get_text(strip=True) if inst_el else self._extract_institution(row, title)

        # Deadline
        deadline = self._extract_deadline(row)

        # Listing type
        listing_type = "unknown"
        row_text = row.get_text().lower()
        for slug, ltype in self.TYPE_MAP.items():
            if slug in row_text:
                listing_type = ltype
                break

        # Description snippet (if available on the index page)
        desc_el = row.select_one("td.description, .snippet, .listing-description")
        description = desc_el.get_text(strip=True) if desc_el else ""

        return Listing(
            title=title,
            institution=institution,
            url=href,
            source=self.name,
            deadline=deadline,
            description=description,
            listing_type=listing_type,
        )

    def _extract_institution(self, row, title: str) -> str:
        """Best-effort institution extraction from row text."""
        cells = row.select("td")
        if len(cells) >= 2:
            return cells[1].get_text(strip=True)
        # Fall back: look for text after " at " or " - " in title
        for sep in [" at ", " – ", " - "]:
            if sep in title:
                return title.split(sep, 1)[1].strip()
        return "Unknown"

    def _extract_deadline(self, row) -> str | None:
        """Try to find an ISO deadline in the row."""
        deadline_el = row.select_one("td.deadline, .deadline, span.date")
        if deadline_el:
            text = deadline_el.get_text(strip=True)
            return self._parse_date(text)
        # Scan full row text for date patterns
        text = row.get_text()
        return self._parse_date(text)

    @staticmethod
    def _parse_date(text: str) -> str | None:
        """Extract an ISO date from text like 'April 8, 2026' or '2026-04-08'."""
        # ISO format already
        iso_match = re.search(r"\d{4}-\d{2}-\d{2}", text)
        if iso_match:
            return iso_match.group()

        # "Month Day, Year" format
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
    scraper = PhilJobsScraper()
    scraper.run()
