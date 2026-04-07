"""
Scraper for Academic Jobs Wiki (https://academicjobs.fandom.com).
Parses wiki pages that track philosophy job listings by year.
"""

import re
from scrapers.base import BaseScraper, Listing


class AcademicJobsWikiScraper(BaseScraper):
    name = "Academic Jobs Wiki"
    url = "https://academicjobs.fandom.com"

    # Pages to scrape — update the year suffix each cycle
    PAGES = [
        "/wiki/Philosophy_2025-2026",
        "/wiki/Humanities_and_Social_Sciences_Postdocs_2025-2026",
    ]

    def scrape(self) -> list[Listing]:
        listings = []

        for page_path in self.PAGES:
            page_url = f"{self.url}{page_path}"
            try:
                soup = self.fetch(page_url)
                page_listings = self._parse_wiki_page(soup, page_url)
                listings.extend(page_listings)
            except Exception as e:
                print(f"[{self.name}] Error fetching {page_url}: {e}")

        # Deduplicate by URL
        seen = set()
        unique = []
        for listing in listings:
            if listing.url not in seen:
                seen.add(listing.url)
                unique.append(listing)

        return unique

    def _parse_wiki_page(self, soup, page_url: str) -> list[Listing]:
        """Parse a wiki page for job listings."""
        listings = []

        # The wiki uses a combination of headers (h2/h3) for categories
        # and lists (ul/ol) or tables for individual entries
        content = soup.select_one("div.mw-parser-output, div#mw-content-text, div.page-content")
        if not content:
            return []

        # Strategy 1: Parse list items (most common wiki format)
        listings.extend(self._parse_list_entries(content, page_url))

        # Strategy 2: Parse table rows
        listings.extend(self._parse_table_entries(content, page_url))

        return listings

    def _parse_list_entries(self, content, page_url: str) -> list[Listing]:
        """Parse list-based entries (ul/ol > li)."""
        listings = []
        current_section = "General"

        for element in content.children:
            if not hasattr(element, "name"):
                continue

            # Track section headers
            if element.name in ("h2", "h3", "h4"):
                current_section = element.get_text(strip=True)
                continue

            if element.name in ("ul", "ol"):
                for li in element.select("li"):
                    listing = self._parse_list_item(li, current_section, page_url)
                    if listing:
                        listings.append(listing)

        return listings

    def _parse_list_item(self, li, section: str, page_url: str) -> Listing | None:
        """Parse a single list item into a Listing."""
        text = li.get_text(separator=" ", strip=True)
        if len(text) < 15:
            return None

        # Find the primary link (usually to the institution or job posting)
        links = li.select("a[href]")
        url = page_url  # default: link to the wiki page itself
        for link in links:
            href = link.get("href", "")
            # Prefer external links over wiki links
            if href.startswith("http") and "fandom.com" not in href:
                url = href
                break
            elif href.startswith("http"):
                url = href

        # Extract title: usually the bold text or first link text
        bold = li.select_one("b, strong")
        title = bold.get_text(strip=True) if bold else ""
        if not title and links:
            title = links[0].get_text(strip=True)
        if not title:
            # Use first ~80 chars of the item text
            title = text[:80].rstrip(".")

        # Extract institution
        institution = self._extract_institution_from_wiki(text, links)

        # Extract deadline
        deadline = self._extract_deadline(text)

        # Classify
        combined = f"{section} {text}".lower()
        listing_type = self._classify_type(combined)

        # Location
        location = self._extract_location(text)

        return Listing(
            title=title,
            institution=institution,
            url=url,
            source=self.name,
            deadline=deadline,
            description=text[:5000],
            location=location,
            listing_type=listing_type,
        )

    def _parse_table_entries(self, content, page_url: str) -> list[Listing]:
        """Parse table-based entries."""
        listings = []

        for table in content.select("table"):
            headers = []
            for th in table.select("tr:first-child th, thead th"):
                headers.append(th.get_text(strip=True).lower())

            for row in table.select("tr")[1:]:  # skip header row
                cells = row.select("td")
                if not cells:
                    continue

                listing = self._parse_table_row(cells, headers, page_url)
                if listing:
                    listings.append(listing)

        return listings

    def _parse_table_row(self, cells, headers: list[str], page_url: str) -> Listing | None:
        """Parse a single table row into a Listing."""
        data = {}
        for i, cell in enumerate(cells):
            key = headers[i] if i < len(headers) else f"col{i}"
            data[key] = cell

        # Try to find title and URL
        title = ""
        url = page_url
        for cell in cells:
            link = cell.select_one("a[href]")
            if link:
                href = link.get("href", "")
                if href.startswith("http"):
                    url = href
                    title = link.get_text(strip=True)
                    break

        if not title:
            title = cells[0].get_text(strip=True) if cells else ""
        if not title or len(title) < 5:
            return None

        # Institution
        inst_text = ""
        for key in ["institution", "university", "school", "employer"]:
            if key in data:
                inst_text = data[key].get_text(strip=True)
                break
        if not inst_text and len(cells) >= 2:
            inst_text = cells[1].get_text(strip=True)

        # Deadline
        deadline = None
        for key in ["deadline", "due", "date", "closing"]:
            if key in data:
                deadline = self._parse_date(data[key].get_text(strip=True))
                if deadline:
                    break

        # Full row text for description
        row_text = " | ".join(c.get_text(strip=True) for c in cells)

        return Listing(
            title=title,
            institution=inst_text or "Unknown",
            url=url,
            source=self.name,
            deadline=deadline,
            description=row_text[:5000],
            listing_type=self._classify_type(row_text.lower()),
        )

    @staticmethod
    def _extract_institution_from_wiki(text: str, links) -> str:
        """Extract institution from wiki entry text."""
        # Wiki entries often format as "University of X - Position Title"
        uni_match = re.search(
            r"(University of [\w\s]+|[\w\s]+ University|[\w\s]+ College|"
            r"[\w\s]+ Institute|ETH|MIT|CNRS|Max Planck|[\w\s]+ School)",
            text[:200],
        )
        if uni_match:
            return uni_match.group().strip()

        # Try link text
        for link in links:
            link_text = link.get_text(strip=True)
            if re.search(r"university|college|institute|school", link_text, re.IGNORECASE):
                return link_text
        return "Unknown"

    @staticmethod
    def _extract_location(text: str) -> str:
        loc_match = re.search(
            r"(?:in\s+)((?:[A-Z][\w]+(?:\s+[A-Z][\w]+)*),\s*"
            r"(?:USA|UK|Canada|Germany|France|Netherlands|Australia|Switzerland|"
            r"Austria|Italy|Sweden|Norway|Denmark|Belgium|Spain|"
            r"[A-Z]{2}))",
            text,
        )
        return loc_match.group(1).strip() if loc_match else ""

    @staticmethod
    def _extract_deadline(text: str) -> str | None:
        # Look for common deadline patterns
        deadline_match = re.search(
            r"(?:deadline|due|review of applications begins?|closes?)[:\s]*"
            r"(\w+ \d{1,2},?\s*\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2} \w+ \d{4})",
            text,
            re.IGNORECASE,
        )
        if deadline_match:
            return AcademicJobsWikiScraper._parse_date(deadline_match.group(1))

        # Standalone date in parentheses often = deadline
        paren_date = re.search(
            r"\((\w+ \d{1,2},?\s*\d{4}|\d{1,2} \w+ \d{4})\)",
            text,
        )
        if paren_date:
            return AcademicJobsWikiScraper._parse_date(paren_date.group(1))

        return None

    @staticmethod
    def _classify_type(text: str) -> str:
        if any(kw in text for kw in ["postdoc", "post-doc", "postdoctoral"]):
            return "postdoc"
        if any(kw in text for kw in ["fellowship", "fellow"]):
            return "fellowship"
        if any(kw in text for kw in ["phd", "doctoral", "graduate"]):
            return "phd"
        if any(kw in text for kw in ["tenure", "professor", "lecturer", "faculty"]):
            return "job"
        return "unknown"

    @staticmethod
    def _parse_date(text: str) -> str | None:
        text = text.strip()
        iso_match = re.match(r"\d{4}-\d{2}-\d{2}$", text)
        if iso_match:
            return text

        month_names = {
            "january": "01", "february": "02", "march": "03", "april": "04",
            "may": "05", "june": "06", "july": "07", "august": "08",
            "september": "09", "october": "10", "november": "11", "december": "12",
        }

        match = re.search(
            r"(" + "|".join(month_names.keys()) + r")\s+(\d{1,2}),?\s+(\d{4})",
            text.lower(),
        )
        if match:
            return f"{match.group(3)}-{month_names[match.group(1)]}-{match.group(2).zfill(2)}"

        match = re.search(
            r"(\d{1,2})\s+(" + "|".join(month_names.keys()) + r")\s+(\d{4})",
            text.lower(),
        )
        if match:
            return f"{match.group(3)}-{month_names[match.group(2)]}-{match.group(1).zfill(2)}"

        return None


if __name__ == "__main__":
    scraper = AcademicJobsWikiScraper()
    scraper.run()
