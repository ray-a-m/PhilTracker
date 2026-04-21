"""
Generic static page scraper for institutional sites.
Handles university/institutional pages that aren't WordPress.
More aggressive text search since static pages have less structure.
"""

import re
import time
from urllib.parse import urljoin
from scrapers.base import BaseScraper, Listing


class StaticScraper(BaseScraper):
    """Configurable scraper for static institutional pages."""

    def __init__(self, site_config: dict):
        self.name = site_config["name"]
        self.url = site_config["url"]
        self.keywords = site_config.get("keywords", [])
        self.secondary_url = site_config.get("secondary_url")
        self.subfield = site_config.get("subfield")

    def scrape(self) -> list[Listing]:
        listings = []

        listings.extend(self._scrape_page(self.url))

        if self.secondary_url:
            time.sleep(1)
            listings.extend(self._scrape_page(self.secondary_url))

        # Deduplicate by URL
        seen = set()
        unique = []
        for listing in listings:
            if listing.url not in seen:
                seen.add(listing.url)
                unique.append(listing)

        return unique

    def _scrape_page(self, url: str) -> list[Listing]:
        """Scrape a static page for job-related content."""
        try:
            soup = self.fetch(url)
        except Exception as e:
            print(f"[{self.name}] Error fetching {url}: {e}")
            return []

        listings = []

        # Strategy 1: Look for structured content blocks
        listings.extend(self._extract_from_sections(soup, url))

        # Strategy 2: Extract from links with surrounding context
        if not listings:
            listings.extend(self._extract_from_links(soup, url))

        # Strategy 3: If the page itself IS a job posting (e.g., a fellowship page)
        if not listings:
            listing = self._extract_single_listing(soup, url)
            if listing:
                listings.append(listing)

        return listings

    def _extract_from_sections(self, soup, page_url: str) -> list[Listing]:
        """Extract listings from structured content sections (divs, list items, etc.)."""
        listings = []

        # Try common content containers
        sections = soup.select(
            "div.vacancy, div.job, div.position, div.listing, "
            "li.vacancy, li.job, li.position, "
            "div.news-item, div.event-item, div.teaser, "
            "div.card, div.panel, div.item"
        )

        for section in sections:
            text = section.get_text(separator=" ", strip=True)
            if not self._matches_keywords(text):
                continue

            link = section.select_one("a[href]")
            if not link:
                continue

            title = link.get_text(strip=True)
            href = self._ensure_absolute(link.get("href", ""), page_url)

            if not title or len(title) < 5:
                # Try heading inside section
                heading = section.select_one("h2, h3, h4, h1")
                if heading:
                    title = heading.get_text(strip=True)

            if not title or len(title) < 5:
                continue

            listings.append(self._build_listing(title, href, text))

        return listings

    def _extract_from_links(self, soup, page_url: str) -> list[Listing]:
        """Extract listings from links whose text or surrounding context matches keywords."""
        listings = []
        seen_urls = set()

        # Check all links on the page
        for link in soup.select("a[href]"):
            href = link.get("href", "")
            text = link.get_text(strip=True)

            if not text or len(text) < 8 or not href:
                continue

            href = self._ensure_absolute(href, page_url)

            # Skip nav links, anchors, mailto, etc.
            if href in seen_urls or href.startswith("#") or href.startswith("mailto:"):
                continue
            if any(skip in href.lower() for skip in ["login", "signup", "contact", "privacy", "cookie"]):
                continue

            # Get surrounding context (parent text)
            parent = link.parent
            grandparent = parent.parent if parent else None
            context = ""
            if grandparent:
                context = grandparent.get_text(separator=" ", strip=True)[:500]
            elif parent:
                context = parent.get_text(separator=" ", strip=True)[:500]

            combined = f"{text} {context}"

            if not self._matches_keywords(combined):
                continue

            seen_urls.add(href)
            listings.append(self._build_listing(text, href, context))

        return listings

    def _extract_single_listing(self, soup, page_url: str) -> Listing | None:
        """Treat the entire page as a single listing (e.g., a dedicated fellowship page)."""
        # Get the main content area
        content = soup.select_one(
            "main, article, div#content, div.content, div.main-content, "
            "div.page-content, div.entry-content"
        )
        if not content:
            content = soup.select_one("body")
        if not content:
            return None

        page_text = content.get_text(separator="\n", strip=True)

        if not self._matches_keywords(page_text):
            return None

        # Page title
        title_el = soup.select_one("h1, title")
        title = title_el.get_text(strip=True) if title_el else self.name

        return self._build_listing(title, page_url, page_text)

    def _build_listing(self, title: str, url: str, text: str) -> Listing:
        """Build a Listing from extracted data."""
        listing_type = self._classify_type(f"{title} {text}".lower())
        deadline = self._extract_date_near_keyword(text, ["deadline", "due", "close", "submit by"])
        location = self._extract_field(text, ["location", "based in", "based at"])
        duration = self._extract_field(text, ["duration", "term", "length"])
        institution = self._extract_institution(title, text)

        return Listing(
            title=title,
            institution=institution if institution != "Unknown" else self.name,
            url=url,
            source=self.name,
            deadline=deadline,
            description=text[:5000],
            location=location,
            duration=duration,
            listing_type=listing_type,
        )

    def _matches_keywords(self, text: str) -> bool:
        """Check if text contains any of the configured keywords."""
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in self.keywords)

    @staticmethod
    def _ensure_absolute(href: str, page_url: str) -> str:
        if href.startswith("http"):
            return href
        return urljoin(page_url, href)

    @staticmethod
    def _extract_institution(title: str, content: str) -> str:
        for sep in [" at ", " @ "]:
            if sep in title:
                return title.split(sep, 1)[1].strip().rstrip(".")
        uni_match = re.search(
            r"(University of [\w\s]+|[\w\s]+ University|[\w\s]+ Institute|"
            r"[\w\s]+ College|ETH|MIT|CNRS|Max Planck)",
            content[:500],
        )
        if uni_match:
            return uni_match.group().strip()
        return "Unknown"

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
    def _extract_date_near_keyword(text: str, keywords: list[str]) -> str | None:
        for kw in keywords:
            pattern = (
                rf"(?:{kw})[:\s]*"
                r"(\w+ \d{1,2},?\s*\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2} \w+ \d{4})"
            )
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return _parse_date_string(match.group(1))
        return None

    @staticmethod
    def _extract_field(text: str, keywords: list[str]) -> str:
        for kw in keywords:
            pattern = rf"(?:{kw})[:\s]*([^\n]{{3,120}})"
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip().rstrip(".")
        return ""


def _parse_date_string(text: str) -> str | None:
    """Convert various date formats to ISO."""
    text = text.strip()
    if re.match(r"\d{4}-\d{2}-\d{2}$", text):
        return text

    month_names = {
        "january": "01", "february": "02", "march": "03", "april": "04",
        "may": "05", "june": "06", "july": "07", "august": "08",
        "september": "09", "october": "10", "november": "11", "december": "12",
    }

    match = re.match(
        r"(" + "|".join(month_names.keys()) + r")\s+(\d{1,2}),?\s+(\d{4})",
        text.lower(),
    )
    if match:
        return f"{match.group(3)}-{month_names[match.group(1)]}-{match.group(2).zfill(2)}"

    match = re.match(
        r"(\d{1,2})\s+(" + "|".join(month_names.keys()) + r")\s+(\d{4})",
        text.lower(),
    )
    if match:
        return f"{match.group(3)}-{month_names[match.group(2)]}-{match.group(1).zfill(2)}"

    return None
