"""
Scraper for Taking Up Spacetime (https://takingupspacetime.wordpress.com).
A blog focused on philosophy of physics that posts job and fellowship announcements.
"""

import re
from scrapers.base import BaseScraper, Listing


class TakingUpSpacetimeScraper(BaseScraper):
    name = "Taking Up Spacetime"
    url = "https://takingupspacetime.wordpress.com"

    # Common category/tag slugs used for job-related posts
    JOB_CATEGORIES = ["jobs", "job", "positions", "cfp", "call-for-papers", "fellowships", "opportunities"]

    def scrape(self) -> list[Listing]:
        listings = []

        # Try the jobs/positions category first, then fall back to recent posts
        for category in self.JOB_CATEGORIES:
            cat_url = f"{self.url}/category/{category}/"
            try:
                soup = self.fetch(cat_url)
                posts = self._extract_posts(soup)
                if posts:
                    listings.extend(posts)
            except Exception:
                continue  # category doesn't exist, try next

        # If no category pages worked, scrape the main page
        if not listings:
            try:
                soup = self.fetch()
                listings = self._extract_posts(soup)
            except Exception as e:
                print(f"[{self.name}] Error fetching main page: {e}")

        # Deduplicate by URL
        seen = set()
        unique = []
        for listing in listings:
            if listing.url not in seen:
                seen.add(listing.url)
                unique.append(listing)

        return unique

    def _extract_posts(self, soup) -> list[Listing]:
        """Extract job-related posts from a WordPress page."""
        listings = []

        articles = soup.select("article, div.post, div.entry")
        if not articles:
            articles = soup.select("div[id^='post-']")

        for article in articles:
            listing = self._parse_article(article)
            if listing:
                listings.append(listing)

        return listings

    def _parse_article(self, article) -> Listing | None:
        """Parse a single blog post into a Listing if it looks job-related."""
        # Find the post title link
        title_el = article.select_one("h2 a, h1 a, h3 a, .entry-title a")
        if not title_el:
            title_heading = article.select_one("h2, h1, h3, .entry-title")
            if not title_heading:
                return None
            link = title_heading.find("a")
            if not link:
                return None
            title_el = link

        title = title_el.get_text(strip=True)
        url = title_el.get("href", "")
        if not title or not url:
            return None

        # Filter: only keep posts that look like job/fellowship announcements
        job_keywords = [
            "position", "postdoc", "fellowship", "tenure", "lecturer",
            "professor", "phd", "doctoral", "job", "call for", "cfp",
            "applications", "vacancy", "hiring", "appointment", "opening",
        ]
        content_el = article.select_one(".entry-content, .entry-summary, .post-content")
        content_text = content_el.get_text(separator="\n", strip=True) if content_el else ""
        combined = f"{title.lower()} {content_text.lower()}"

        if not any(kw in combined for kw in job_keywords):
            return None

        # Extract all fields from post content
        institution = self._extract_institution(title, content_text)
        listing_type = self._classify_type(combined)
        deadline = self._extract_deadline(content_text)
        location = self._extract_location(content_text)
        duration = self._extract_duration(content_text)

        return Listing(
            title=title,
            institution=institution,
            url=url,
            source=self.name,
            deadline=deadline,
            description=content_text[:5000],
            location=location,
            duration=duration,
            listing_type=listing_type,
        )

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
        """Classify listing type from text."""
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
    def _extract_deadline(text: str) -> str | None:
        """Try to find a deadline date in the post content."""
        deadline_pattern = re.search(
            r"(?:deadline|due|closes?|applications? due|submit by)[:\s]*"
            r"(\w+ \d{1,2},?\s*\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2} \w+ \d{4})",
            text.lower(),
        )
        if deadline_pattern:
            return _parse_date_string(deadline_pattern.group(1))

        iso_match = re.search(r"\d{4}-\d{2}-\d{2}", text)
        if iso_match:
            return iso_match.group()

        return None

    @staticmethod
    def _extract_location(text: str) -> str:
        """Extract location from post text."""
        patterns = [
            r"(?:location|based (?:in|at)|situated (?:in|at))[:\s]*([^\n.]{3,80})",
            r"(?:in\s+)((?:[A-Z][\w]+(?:\s+[A-Z][\w]+)*),\s*(?:Germany|UK|USA|France|Netherlands|"
            r"Canada|Australia|Switzerland|Austria|Italy|Sweden|Norway|Denmark|Belgium|Spain))",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip().rstrip(".")
        return ""

    @staticmethod
    def _extract_duration(text: str) -> str:
        """Extract duration from post text."""
        patterns = [
            r"(?:duration|term|length of appointment)[:\s]*([^\n.]{3,80})",
            r"(\d+[\s-]?years?(?:\s+renewable)?)",
            r"(\d+[\s-]?months?)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
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


if __name__ == "__main__":
    scraper = TakingUpSpacetimeScraper()
    scraper.run()
