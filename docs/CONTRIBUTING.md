# Contributing to PhilTracker

Thanks for wanting to help. PhilTracker is built by philosophers for philosophers — you don't need to be a professional developer to contribute.

## What We Need Most

In rough priority order:

1. **New scrapers.** Each source we add makes PhilTracker more useful. If you know a site where philosophy jobs or fellowships appear, write a scraper for it.
2. **Better tagging.** Our keyword lists for subfield tagging are incomplete. If you notice mistagged listings, open an issue or improve the keyword lists in `tagger/tags.yaml`.
3. **Bug reports.** Scrapers break when websites change. If you notice a source returning bad data or nothing at all, open an issue.
4. **Frontend improvements.** Design, usability, accessibility.

## How to Add a Scraper

This is the most common contribution. Here's how.

### 1. Create a new file in `scrapers/`

If it's a major job board or blog, put it in `scrapers/` directly (e.g., `scrapers/daily_nous.py`). If it's an institutional page, put it in `scrapers/institutional/` (e.g., `scrapers/institutional/mcmp_munich.py`).

### 2. Follow the base interface

Every scraper must implement one function: `scrape()`, which returns a list of `Listing` objects.

```python
from scrapers.base import Listing, BaseScraper

class DailyNousScraper(BaseScraper):
    name = "Daily Nous"
    url = "https://dailynous.com/category/philosophy-job-market/"

    def scrape(self) -> list[Listing]:
        # Fetch the page
        # Parse the HTML
        # Return a list of Listing objects
        listings = []
        # ... your parsing logic ...
        return listings
```

### 3. The Listing object

Every listing must have these fields:

```python
Listing(
    title="PostDoc in Philosophy of Science",
    institution="University of Salzburg",
    url="https://philjobs.org/job/show/31113",
    source="PhilJobs",              # which scraper found it
    deadline="2026-04-08",          # ISO format, or None if unknown
    description="...",              # full text of the listing
    date_scraped="2026-04-07",      # auto-filled
    aos=[],                         # left empty; the tagger fills this in
)
```

### 4. Test your scraper

```bash
python -m scrapers.your_scraper
```

It should print a list of listings. Check that titles, institutions, and deadlines look right.

### 5. Submit a pull request

Push your branch and open a PR. In the description, include:
- What source you're scraping
- How many listings it currently returns
- Any quirks (e.g., "this site doesn't list deadlines in a consistent format")

## How to Improve Tagging

The file `tagger/tags.yaml` contains keyword lists for each subfield tag. For example:

```yaml
philosophy-of-physics:
  - "philosophy of physics"
  - "foundations of physics"
  - "quantum mechanics"
  - "spacetime"
  - "quantum gravity"
  - "philosophy of cosmology"
  - "symmetry"
  - "gauge theory"
```

If you think a keyword is missing or misplaced, edit the YAML file and submit a PR.

## Code Style

- Python, formatted with `black`.
- Keep scrapers simple. BeautifulSoup for HTML parsing, `requests` for fetching. No Selenium unless absolutely necessary (some sites need JavaScript rendering — flag this in your PR).
- No unnecessary dependencies.

## Reporting Broken Scrapers

Open a GitHub Issue with:
- Which source is broken
- What you expected to see vs. what you got
- A screenshot if helpful

That's enough for someone to diagnose and fix it.

## Code of Conduct

Be kind. This is a community tool for a small discipline. We're all on the same job market.
