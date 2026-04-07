"""
Generic WordPress scraper for institutional sites.
Handles blog-style pages: finds posts/articles, filters by job-related keywords,
and extracts listings. Works for any WordPress site in config.yaml.
"""

import re
import time
from scrapers.base import BaseScraper, Listing


class WordPressScraper(BaseScraper):
    """Configurable scraper for WordPress-based institutional sites."""

    def __init__(self, site_config: dict):
        self.name = site_config["name"]
        self.url = site_config["url"]
        self.keywords = site_config.get("keywords", [])
        self.secondary_url = site_config.get("secondary_url")
        self.subfield = site_config.get("subfield")

    def scrape(self) -> list[Listing]:
        listings = []

        # Scrape primary URL
        listings.extend(self._scrape_page(self.url))

        # Scrape secondary URL if configured
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
        """Scrape a single WordPress page for job-related posts."""
        try:
            soup = self.fetch(url)
        except Exception as e:
            print(f"[{self.name}] Error fetching {url}: {e}")
            return []

        listings = []

        # WordPress post selectors (broad to narrow)
        articles = soup.select("article")
        if not articles:
            articles = soup.select("div.post, div.entry, div[id^='post-']")
        if not articles:
            # Fall back to looking for any content blocks with links
            articles = soup.select("div.content, div.main, main, div#content")

        for article in articles:
            listing = self._parse_article(article, url)
            if listing:
                listings.append(listing)

        # If no articles found via selectors, try extracting from raw links
        if not listings:
            listings = self._extract_from_links(soup, url)

        return listings

    def _parse_article(self, article, page_url: str) -> Listing | None:
        """Parse a single WordPress article/post into a Listing."""
        # Find title link
        title_el = article.select_one(
            "h2 a, h1 a, h3 a, .entry-title a, .post-title a"
        )
        if not title_el:
            heading = article.select_one("h2, h1, h3, .entry-title, .post-title")
            if not heading:
                return None
            link = heading.find("a")
            if not link:
                return None
            title_el = link

        title = title_el.get_text(strip=True)
        href = title_el.get("href", "")
        if not title or not href:
            return None

        href = self._ensure_absolute(href, page_url)

        # Get content text
        content_el = article.select_one(
            ".entry-content, .entry-summary, .post-content, .post-excerpt"
        )
        content_text = content_el.get_text(separator="\n", strip=True) if content_el else ""
        combined = f"{title} {content_text}".lower()

        # Filter by job-related keywords
        if not any(kw.lower() in combined for kw in self.keywords):
            return None

        # Extract fields
        institution = self._extract_institution(title, content_text)
        listing_type = self._classify_type(combined)
        deadline = self._extract_date_near_keyword(content_text, ["deadline", "due", "close", "submit by"])
        start_date = self._extract_date_near_keyword(content_text, ["start", "begin", "commence"])
        location = self._extract_field(content_text, ["location", "based in", "based at", "situated in"])
        duration = self._extract_field(content_text, ["duration", "term", "length", "appointment period"])
        salary = self._extract_field(content_text, ["salary", "stipend", "compensation", "pay", "remuneration"])
        aos_raw = self._extract_field(content_text, ["area of specialization", "AOS", "specialization"])

        return Listing(
            title=title,
            institution=institution,
            url=href,
            source=self.name,
            deadline=deadline,
            description=content_text[:5000],
            location=location,
            duration=duration,
            start_date=start_date or "",
            aos_raw=aos_raw,
            salary=salary,
            listing_type=listing_type,
        )

    def _extract_from_links(self, soup, page_url: str) -> list[Listing]:
        """Fall back: extract listings from links on the page."""
        listings = []
        seen_urls = set()

        for link in soup.select("a[href]"):
            text = link.get_text(strip=True)
            href = link.get("href", "")
            if not text or len(text) < 10 or not href:
                continue

            href = self._ensure_absolute(href, page_url)
            if href in seen_urls:
                continue

            # Check surrounding text (parent element)
            parent = link.parent
            context = parent.get_text(strip=True) if parent else text
            combined = f"{text} {context}".lower()

            if not any(kw.lower() in combined for kw in self.keywords):
                continue

            seen_urls.add(href)
            listings.append(Listing(
                title=text,
                institution=self.name,
                url=href,
                source=self.name,
                description=context[:5000],
                listing_type=self._classify_type(combined),
            ))

        return listings

    @staticmethod
    def _ensure_absolute(href: str, page_url: str) -> str:
        """Ensure a URL is absolute."""
        if href.startswith("http"):
            return href
        from urllib.parse import urljoin
        return urljoin(page_url, href)

    @staticmethod
    def _extract_institution(title: str, content: str) -> str:
        """Best-effort institution extraction."""
        for sep in [" at ", " @ "]:
            if sep in title:
                return title.split(sep, 1)[1].strip().rstrip(".")
        for sep in [" – ", " - ", " — "]:
            if sep in title:
                parts = title.split(sep)
                return min(parts, key=len).strip()

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
        """Find a date near one of the given keywords."""
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
        """Extract a field value that follows one of the keywords."""
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
