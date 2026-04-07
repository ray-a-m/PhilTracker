"""
Scraper for PhilJobs (https://philjobs.org).
Scrapes all job category pages: fixedTerm, tt (tenure-track), senior, other.
Each page shows all listings (no pagination needed).
"""

import re
import time
from scrapers.base import BaseScraper, Listing


class PhilJobsScraper(BaseScraper):
    name = "PhilJobs"
    url = "https://philjobs.org/jobQuery/fixedTerm"

    # PhilJobs category pages and their default listing types
    CATEGORIES = {
        "https://philjobs.org/jobQuery/fixedTerm": "job",
        "https://philjobs.org/jobQuery/tt": "job",
        "https://philjobs.org/jobQuery/senior": "job",
        "https://philjobs.org/jobQuery/other": "unknown",
    }

    # Map PhilJobs tenure labels to our listing types
    TYPE_MAP = {
        "fixed term": "job",
        "tenure-track": "job",
        "tenured": "job",
        "senior": "job",
        "postdoc": "postdoc",
        "graduate": "phd",
        "fellowship": "fellowship",
    }

    def scrape(self) -> list[Listing]:
        listings = []
        seen_urls = set()

        for cat_url, default_type in self.CATEGORIES.items():
            try:
                soup = self.fetch(cat_url)
            except Exception as e:
                print(f"[{self.name}] Error fetching {cat_url}: {e}")
                continue

            job_divs = soup.select("div.job")
            print(f"[{self.name}] {cat_url.split('/')[-1]}: {len(job_divs)} jobs")

            for div in job_divs:
                listing = self._parse_job_div(div, default_type)
                if listing and listing.url not in seen_urls:
                    seen_urls.add(listing.url)
                    listings.append(listing)

            time.sleep(1)

        return listings

    def _parse_job_div(self, div, default_type: str) -> Listing | None:
        """Parse a PhilJobs div.job element into a Listing."""
        # Institution + URL from div.jobOrg > a.jobLine
        org_link = div.select_one("div.jobOrg a.jobLine")
        if not org_link:
            return None

        institution = org_link.get_text(strip=True)
        href = org_link.get("href", "")
        if not href:
            return None
        if href.startswith("/"):
            href = f"https://philjobs.org{href}"

        # Title from span.jobTitle
        title_el = div.select_one("span.jobTitle")
        title = title_el.get_text(strip=True) if title_el else institution

        # Listing type from span.tenure
        listing_type = default_type
        tenure_el = div.select_one("span.tenure")
        if tenure_el:
            tenure_text = tenure_el.get_text(strip=True).lower().strip("()")
            for slug, ltype in self.TYPE_MAP.items():
                if slug in tenure_text:
                    listing_type = ltype
                    break

        # AOS and AOC from div.jobLine text
        aos_raw = ""
        job_lines = div.select("div.jobLine")
        for line in job_lines:
            text = line.get_text(strip=True)
            if text.startswith("AOS:"):
                aos_raw = text[4:].strip()
            elif text.startswith("AOC:"):
                aoc = text[4:].strip()
                aos_raw = f"{aos_raw}; AOC: {aoc}" if aos_raw else f"AOC: {aoc}"

        # Deadline from table.jobDates
        deadline = self._extract_deadline_from_div(div)

        # Description: combine what's visible on the index page
        desc_parts = [title, f"at {institution}"]
        if aos_raw:
            desc_parts.append(f"AOS: {aos_raw}")
        description = ". ".join(desc_parts)

        return Listing(
            title=title,
            institution=institution,
            url=href,
            source=self.name,
            deadline=deadline,
            description=description,
            aos_raw=aos_raw,
            listing_type=listing_type,
        )

    def _extract_deadline_from_div(self, div) -> str | None:
        """Extract deadline from the jobDates table in a job div."""
        # The table has headers in first row, values in second
        date_table = div.select_one("table.jobDates")
        if not date_table:
            return self._parse_date(div.get_text())

        # Find the "Deadline" column
        headers = date_table.select("tr:first-child td.inlineLabel")
        values = date_table.select("tr:last-child td.inlineDetails")

        for i, header in enumerate(headers):
            if "deadline" in header.get_text(strip=True).lower():
                if i < len(values):
                    deadline_text = values[i].get_text(strip=True)
                    return self._parse_date(deadline_text)
        return None

    @staticmethod
    def _parse_date(text: str) -> str | None:
        """Extract an ISO date from text like 'Apr 22, 00:00am EST' or 'May 15, 2026'."""
        # ISO format already
        iso_match = re.search(r"\d{4}-\d{2}-\d{2}", text)
        if iso_match:
            return iso_match.group()

        month_names = {
            "january": "01", "february": "02", "march": "03", "april": "04",
            "may": "05", "june": "06", "july": "07", "august": "08",
            "september": "09", "october": "10", "november": "11", "december": "12",
            "jan": "01", "feb": "02", "mar": "03", "apr": "04",
            "jun": "06", "jul": "07", "aug": "08", "sep": "09",
            "oct": "10", "nov": "11", "dec": "12",
        }

        # "Month Day, Year" or "Month Day Year"
        pattern = r"(" + "|".join(month_names.keys()) + r")\s+(\d{1,2}),?\s+(\d{4})"
        match = re.search(pattern, text.lower())
        if match:
            month = month_names[match.group(1)]
            day = match.group(2).zfill(2)
            year = match.group(3)
            return f"{year}-{month}-{day}"

        # PhilJobs sometimes shows "Apr 22, 00:00am" without year — assume current year
        pattern_no_year = r"(" + "|".join(month_names.keys()) + r")\s+(\d{1,2})"
        match = re.search(pattern_no_year, text.lower())
        if match:
            from datetime import date
            month = month_names[match.group(1)]
            day = match.group(2).zfill(2)
            year = str(date.today().year)
            # If the month has passed, assume next year
            candidate = f"{year}-{month}-{day}"
            if candidate < date.today().isoformat():
                year = str(date.today().year + 1)
            return f"{year}-{month}-{day}"

        return None


if __name__ == "__main__":
    scraper = PhilJobsScraper()
    scraper.run()
