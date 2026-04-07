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
    """Test parsing of PhilJobs search results page."""

    def test_parse_search_rows(self):
        soup = _load_fixture("philjobs_search.html")
        scraper = PhilJobsScraper()

        rows = soup.select("table.joblist tr.job-listing")
        assert len(rows) == 3

        # Parse first row (skip detail fetching)
        with patch.object(scraper, "_fetch_detail", return_value={}):
            listing = scraper._parse_row(rows[0])

        assert listing is not None
        assert listing.title == "Postdoctoral Research Fellow in Philosophy of Physics"
        assert listing.institution == "University of Oxford"
        assert listing.deadline == "2026-05-15"
        assert listing.url == "https://philjobs.org/job/show/12345"

    def test_parse_tenure_track(self):
        soup = _load_fixture("philjobs_search.html")
        scraper = PhilJobsScraper()
        rows = soup.select("table.joblist tr.job-listing")

        with patch.object(scraper, "_fetch_detail", return_value={}):
            listing = scraper._parse_row(rows[1])

        assert listing.title == "Assistant Professor of Philosophy (tenure-track)"
        assert listing.institution == "University of Pittsburgh"
        assert listing.listing_type == "job"  # "tenure" in text

    def test_parse_phd(self):
        soup = _load_fixture("philjobs_search.html")
        scraper = PhilJobsScraper()
        rows = soup.select("table.joblist tr.job-listing")

        with patch.object(scraper, "_fetch_detail", return_value={}):
            listing = scraper._parse_row(rows[2])

        assert "Formal Epistemology" in listing.title
        assert listing.institution == "Ludwig-Maximilians-Universität München"


class TestPhilJobsDetailParsing:
    """Test parsing of a PhilJobs detail page."""

    def test_extract_structured_fields(self):
        soup = _load_fixture("philjobs_listing.html")
        scraper = PhilJobsScraper()

        result = {}
        scraper._extract_structured_fields(soup, result)

        assert result["institution"] == "University of Oxford"
        assert "Philosophy of Physics" in result["aos_raw"]
        assert result["location"] == "Oxford, United Kingdom"
        assert result["start_date"] == "September 1, 2026"
        assert "£38,674" in result["salary"]
        assert result["duration"] == "3 years"
        assert result["deadline"] == "2026-05-15"

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
