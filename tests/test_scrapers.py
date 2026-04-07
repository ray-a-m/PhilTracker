"""Tests for scraper parsing logic using saved HTML fixtures."""

import os
from unittest.mock import patch, MagicMock
from bs4 import BeautifulSoup
from scrapers.philjobs import PhilJobsScraper
from scrapers.taking_up_spacetime import TakingUpSpacetimeScraper

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture(name):
    with open(os.path.join(FIXTURES, name)) as f:
        return BeautifulSoup(f.read(), "html.parser")


# ── PhilJobs tests ──────────────────────────────────────────


class TestPhilJobsSearchParsing:
    """Test parsing of PhilJobs search results page (div.job structure)."""

    def test_parse_job_divs(self):
        soup = _load_fixture("philjobs_search.html")
        scraper = PhilJobsScraper()

        divs = soup.select("div.job")
        assert len(divs) == 3

        listing = scraper._parse_job_div(divs[0], "job")

        assert listing is not None
        assert listing.title == "Postdoctoral Research Fellow in Philosophy of Physics"
        assert listing.institution == "University of Oxford"
        assert listing.deadline == "2026-05-15"
        assert listing.url == "https://philjobs.org/job/show/12345"
        assert "Philosophy of Physics" in listing.aos_raw

    def test_parse_tenure_track(self):
        soup = _load_fixture("philjobs_search.html")
        scraper = PhilJobsScraper()
        divs = soup.select("div.job")

        listing = scraper._parse_job_div(divs[1], "job")

        assert listing.title == "Assistant Professor of Philosophy"
        assert listing.institution == "University of Pittsburgh"
        assert listing.listing_type == "job"

    def test_parse_phd(self):
        soup = _load_fixture("philjobs_search.html")
        scraper = PhilJobsScraper()
        divs = soup.select("div.job")

        listing = scraper._parse_job_div(divs[2], "unknown")

        assert "Formal Epistemology" in listing.title
        assert listing.institution == "Ludwig-Maximilians-Universität München"


class TestPhilJobsDetailParsing:
    """Test parsing of a PhilJobs detail page HTML fixture."""

    def test_extract_structured_fields_from_dl(self):
        """Verify the detail page fixture has extractable structured data."""
        soup = _load_fixture("philjobs_listing.html")

        # Extract fields from definition list (dt/dd pairs)
        fields = {}
        for dt in soup.select("dt"):
            label = dt.get_text(strip=True).lower()
            dd = dt.find_next_sibling("dd")
            if dd:
                fields[label] = dd.get_text(strip=True)

        assert fields["institution"] == "University of Oxford"
        assert "Philosophy of Physics" in fields["area of specialization"]
        assert fields["location"] == "Oxford, United Kingdom"
        assert fields["start date"] == "September 1, 2026"
        assert "£38,674" in fields["salary"]
        assert fields["duration"] == "3 years"

    def test_extract_description(self):
        soup = _load_fixture("philjobs_listing.html")
        desc_el = soup.select_one("div.job-description")
        assert desc_el is not None
        text = desc_el.get_text(separator="\n", strip=True)
        assert "quantum gravity" in text
        assert "measurement problem" in text


# ── Taking Up Spacetime tests ───────────────────────────────


class TestTakingUpSpacetimeParsing:
    """Test parsing of Taking Up Spacetime blog posts."""

    def test_extract_job_posts(self):
        soup = _load_fixture("taking_up_spacetime_page.html")
        scraper = TakingUpSpacetimeScraper()
        listings = scraper._extract_posts(soup)

        # Should find 2 job posts, skip the conference announcement
        assert len(listings) == 2
        titles = [l.title for l in listings]
        assert "Postdoc Position at the Geneva Symmetry Group" in titles
        assert "Tenure-Track Position in History and Philosophy of Science at Cambridge" in titles

    def test_filters_non_job_posts(self):
        soup = _load_fixture("taking_up_spacetime_page.html")
        scraper = TakingUpSpacetimeScraper()
        listings = scraper._extract_posts(soup)

        titles = [l.title for l in listings]
        assert "Conference on Quantum Gravity and Spacetime" not in titles

    def test_extract_fields_from_post(self):
        soup = _load_fixture("taking_up_spacetime_page.html")
        scraper = TakingUpSpacetimeScraper()
        listings = scraper._extract_posts(soup)

        geneva = [l for l in listings if "Geneva" in l.title][0]
        assert "Geneva Symmetry Group" in geneva.institution
        assert geneva.listing_type == "postdoc"
        assert geneva.deadline == "2026-06-30"
        assert "Geneva" in geneva.location
        assert "2 years" in geneva.duration
        assert "CHF 85,000" in geneva.salary

    def test_extract_tenure_track(self):
        soup = _load_fixture("taking_up_spacetime_page.html")
        scraper = TakingUpSpacetimeScraper()
        listings = scraper._extract_posts(soup)

        cambridge = [l for l in listings if "Cambridge" in l.title][0]
        assert cambridge.listing_type == "job"
        assert cambridge.deadline == "2026-04-30"


# ── Date parsing tests ──────────────────────────────────────


class TestDateParsing:
    def test_iso_format(self):
        assert PhilJobsScraper._parse_date("2026-05-15") == "2026-05-15"

    def test_month_day_year(self):
        assert PhilJobsScraper._parse_date("May 15, 2026") == "2026-05-15"

    def test_month_day_year_no_comma(self):
        assert PhilJobsScraper._parse_date("December 1 2026") == "2026-12-01"

    def test_no_date(self):
        assert PhilJobsScraper._parse_date("no deadline listed") is None
