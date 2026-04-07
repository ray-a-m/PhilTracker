# PhilTracker

**PhilJobs tells you what exists. PhilTracker tells you what matters to you.**

PhilTracker is an open source job and fellowship aggregator for academic philosophers. It pulls listings from multiple sources, tags them by subfield, and surfaces what's relevant to your research profile — with deadline tracking and configurable digests.

## Why?

The philosophy job market runs on [PhilJobs](https://philjobs.org), but PhilJobs is only one source. Fellowships at places like the Pittsburgh Center for Philosophy of Science, the Geneva Symmetry Group, or the Descartes Centre often appear on institutional pages, blogs, or general academic job boards — not on PhilJobs. Philosophers end up manually checking half a dozen sites every week.

PhilTracker fixes this by:

- **Aggregating** listings from PhilJobs, Taking Up Spacetime, HigherEdJobs, PSA Calendar, and institutional fellowship pages
- **Tagging** listings with granular subfield labels (not just "Philosophy of Science" but "philosophy of physics," "foundations of quantum mechanics," "formal epistemology," etc.)
- **Learning your profile** so you see what's relevant to you first
- **Tracking deadlines** with countdowns, calendar views, and reminders
- **Sending digests** at whatever frequency you choose — daily, weekly, or immediately when a match appears

## Status

🚧 **Early development.** We're building the initial scrapers and core infrastructure. Contributions welcome.

## Sources

Currently planned:

| Source | Type | Status |
|---|---|---|
| PhilJobs | Job board | Planned |
| Taking Up Spacetime | Blog (philosophy of physics) | Planned |
| HigherEdJobs | General academic job board | Planned |
| PSA Calendar | Events and calls | Planned |
| Geneva Symmetry Group | Institutional page | Planned |
| Pittsburgh Center for Phil of Science | Institutional page | Planned |
| Rotman Institute | Institutional page | Planned |
| Philosophy of Physics Society | News/jobs | Planned |

Want to add a source? See [CONTRIBUTING.md](docs/CONTRIBUTING.md).

## Subfield Tags

PhilTracker uses a granular tagging system. Examples:

- `philosophy-of-physics`
- `philosophy-of-biology`
- `formal-epistemology`
- `history-and-philosophy-of-science`
- `foundations-of-quantum-mechanics`
- `philosophy-of-cosmology`
- `philosophy-of-chemistry`
- `metaphysics-of-science`
- `german-idealism`
- `social-epistemology`

Tags are assigned automatically by keyword matching, with optional LLM refinement. The full tag list is in `tagger/tags.yaml`.

## Architecture

```
scrapers/       One script per source. Each outputs standardized listings.
tagger/         Assigns subfield tags to listings.
backend/        API server, database models, digest scheduler, deduplication.
frontend/       Web interface for browsing, filtering, and profile setup.
scheduler/      Cron jobs that run scrapers daily via GitHub Actions.
```

## Tech Stack

- **Python** (scrapers, backend)
- **FastAPI** (API server)
- **SQLite** (to start; Postgres when needed)
- **HTML/CSS** (frontend — deliberately simple)
- **GitHub Actions** (scheduler)
- **Hosted on Render or Railway** (free tier)

## Getting Started (Development)

```bash
git clone https://github.com/yourname/philtracker.git
cd philtracker
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python backend/app.py
```

## Contributing

See [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) for how to add a scraper, improve tagging, or work on the frontend.

The most valuable contributions right now are **new scrapers**. If you know a site where philosophy jobs or fellowships get posted, we want to pull from it.

## License

MIT. Do whatever you want with this.
