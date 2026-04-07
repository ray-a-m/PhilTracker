"""
Scraper for PhilJobs (https://philjobs.org).
Pulls job and fellowship listings from the PhilJobs listing pages,
then fetches each detail page for full description and structured fields.
"""

import re
import time
from scrapers.base import BaseScraper, Listing


class PhilJobsScraper(BaseScraper):
    name = "PhilJobs"
    url = "https://philjobs.org/job/search"

    # PhilJobs job category query paths and their listing types
    CATEGORIES = {
        "/jobQuery/fixedTerm": "job",
        "/jobQuery/tt": "job",
        "/jobQuery/senior": "job",
        "/jobQuery/other": "unknown",
    }

    # Also check the main search page
    PAGES_PER_CATEGORY = 3

    def scrape(self) -> list[Listing]:
        listings = []
        seen_urls = set()

        # Scrape each category
        for path, default_type in self.CATEGORIES.items():
            cat_url = f"https://philjobs.org{path}"
            cat_listings = self._scrape_category(cat_url, default_type)
            for listing in cat_listings:
                if listing.url not in seen_urls:
                    seen_urls.add(listing.url)
                    listings.append(listing)
            time.sleep(1)

        # Also scrape the main search page
        main_listings = self._scrape_category(self.url, "unknown")
        for listing in main_listings:
            if listing.url not in seen_urls:
                seen_urls.add(listing.url)
                listings.append(listing)

        return listings

    def _scrape_category(self, base_url: str, default_type: str) -> list[Listing]:
        """Scrape all pages of a PhilJobs category."""
        listings = []

        for page in range(1, self.PAGES_PER_CATEGORY + 1):
            params = {"page": page}
            try:
                soup = self.fetch(base_url, params=params)
            except Exception as e:
                print(f"[{self.name}] Error fetching {base_url} page {page}: {e}")
                break

            job_rows = soup.select("table.joblist tr.job-listing, div.job-listing, div.listing-item")
            if not job_rows:
                job_rows = soup.select("tr:has(a[href*='/job/show/'])")

            if not job_rows:
                break

            for row in job_rows:
                listing = self._parse_row(row, default_type)
                if listing:
                    listings.append(listing)

            time.sleep(1)

        return listings

    # PhilJobs listing type slugs -> our listing_type
    TYPE_MAP = {
        "postdoc": "postdoc",
        "tenure": "job",
        "fixed-term": "job",
        "graduate": "phd",
        "fellowship": "fellowship",
    }

    def _parse_row(self, row, default_type: str = "unknown") -> Listing | None:
        """Parse a single job row/card into a Listing, then fetch its detail page."""
        link = row.select_one("a[href*='/job/show/']") or row.select_one("a[href*='philjobs.org']")
        if not link:
            return None

        title = link.get_text(strip=True)
        href = link.get("href", "")
        if not title or not href:
            return None

        if href.startswith("/"):
            href = f"https://philjobs.org{href}"

        # Institution from index row
        inst_el = (
            row.select_one("td.institution")
            or row.select_one("span.institution")
            or row.select_one(".employer")
        )
        institution = inst_el.get_text(strip=True) if inst_el else self._extract_institution_from_row(row, title)

        # Deadline from index row
        deadline = self._extract_deadline(row)

        # Listing type from index row text, falling back to category default
        listing_type = default_type
        row_text = row.get_text().lower()
        for slug, ltype in self.TYPE_MAP.items():
            if slug in row_text:
                listing_type = ltype
                break

        # Fetch detail page for full description and structured fields
        detail = self._fetch_detail(href)

        return Listing(
            title=title,
            institution=detail.get("institution") or institution,
            url=href,
            source=self.name,
            deadline=detail.get("deadline") or deadline,
            description=detail.get("description", "")[:5000],
            location=detail.get("location", ""),
            duration=detail.get("duration", ""),
            start_date=detail.get("start_date", ""),
            aos_raw=detail.get("aos_raw", ""),
            salary=detail.get("salary", ""),
            listing_type=listing_type,
        )

    def _fetch_detail(self, url: str) -> dict:
        """Fetch a PhilJobs detail page and extract structured fields."""
        result = {}
        try:
            time.sleep(1)  # polite delay
            soup = self.fetch(url)
        except Exception as e:
            print(f"[{self.name}] Could not fetch detail {url}: {e}")
            return result

        # Full description text
        desc_el = (
            soup.select_one("div.job-description")
            or soup.select_one("div.listing-body")
            or soup.select_one("div.job-details")
            or soup.select_one("article")
            or soup.select_one("div#content")
        )
        if desc_el:
            result["description"] = desc_el.get_text(separator="\n", strip=True)

        # PhilJobs typically has a structured table/dl with fields like
        # "AOS", "Location", "Start Date", "Salary", "Duration", etc.
        self._extract_structured_fields(soup, result)

        return result

    def _extract_structured_fields(self, soup, result: dict):
        """Extract structured fields from PhilJobs detail page tables/definition lists."""
        # Try definition list (<dl><dt>...<dd>...)
        for dt in soup.select("dt"):
            label = dt.get_text(strip=True).lower().rstrip(":")
            dd = dt.find_next_sibling("dd")
            if not dd:
                continue
            value = dd.get_text(strip=True)
            self._map_field(label, value, result)

        # Try table rows (<tr><th>...<td>...) or (<tr><td>label<td>value)
        for tr in soup.select("tr"):
            cells = tr.select("th, td")
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True).lower().rstrip(":")
                value = cells[1].get_text(strip=True)
                self._map_field(label, value, result)

        # Try labeled spans/divs (e.g., <span class="label">AOS:</span> <span>value</span>)
        for label_el in soup.select("span.label, strong, b"):
            label = label_el.get_text(strip=True).lower().rstrip(":")
            sibling = label_el.next_sibling
            if sibling:
                value = sibling.get_text(strip=True) if hasattr(sibling, "get_text") else str(sibling).strip()
                if value:
                    self._map_field(label, value, result)

        # If no structured salary/duration found, try extracting from description
        desc = result.get("description", "")
        if not result.get("salary"):
            result["salary"] = self._extract_salary_from_text(desc)
        if not result.get("duration"):
            result["duration"] = self._extract_duration_from_text(desc)

    @staticmethod
    def _map_field(label: str, value: str, result: dict):
        """Map a label-value pair from structured data to our fields."""
        if not value:
            return
        if any(k in label for k in ["area of specialization", "aos", "area of spec"]):
            result["aos_raw"] = value
        elif any(k in label for k in ["area of competence", "aoc"]):
            # Append AOC to aos_raw if AOS already set
            existing = result.get("aos_raw", "")
            result["aos_raw"] = f"{existing}; AOC: {value}" if existing else f"AOC: {value}"
        elif "location" in label or "country" in label:
            existing = result.get("location", "")
            result["location"] = f"{existing}, {value}".lstrip(", ") if existing else value
        elif "start" in label and "date" in label:
            result["start_date"] = value
        elif "salary" in label or "compensation" in label or "pay" in label:
            result["salary"] = value
        elif "duration" in label or "term" in label or "length" in label:
            result["duration"] = value
        elif "deadline" in label or "closing" in label:
            parsed = PhilJobsScraper._parse_date(value)
            if parsed:
                result["deadline"] = parsed
        elif "institution" in label or "employer" in label or "university" in label:
            result["institution"] = value

    @staticmethod
    def _extract_salary_from_text(text: str) -> str:
        """Extract salary info from description text."""
        patterns = [
            r"(?:salary|compensation|pay|stipend)[:\s]*([^\n.]{5,80})",
            r"([\$€£]\s*[\d,]+(?:\s*[-–]\s*[\$€£]?\s*[\d,]+)?(?:\s*per\s+\w+)?)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    @staticmethod
    def _extract_duration_from_text(text: str) -> str:
        """Extract duration info from description text."""
        patterns = [
            r"(?:duration|term|appointment)[:\s]*([^\n.]{5,80})",
            r"(\d+[\s-]?years?(?:\s+renewable)?)",
            r"(\d+[\s-]?months?)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    def _extract_institution_from_row(self, row, title: str) -> str:
        """Best-effort institution extraction from row text."""
        cells = row.select("td")
        if len(cells) >= 2:
            return cells[1].get_text(strip=True)
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
        text = row.get_text()
        return self._parse_date(text)

    @staticmethod
    def _parse_date(text: str) -> str | None:
        """Extract an ISO date from text like 'April 8, 2026' or '2026-04-08'."""
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
    scraper = PhilJobsScraper()
    scraper.run()
