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

### Standalone scrapers

| Source | Type | Status |
|---|---|---|
| PhilJobs (all categories) | Job board | Implemented |
| Taking Up Spacetime | Blog (philosophy of physics) | Implemented |
| HigherEdJobs | General academic job board (Playwright) | Implemented |
| Academic Jobs Wiki | Wiki (Philosophy & Humanities postdocs) | Implemented |

### Institutional sites (configurable — `scrapers/institutional/config.yaml`)

Add new sites by editing the config file — no new code needed. Currently **72 sites** across all subfields:

**Philosophy of Physics / Foundations (7):** Geneva Symmetry Group, Geneva Symmetry Group Blog, Cambridge Philosophy of Physics, Bonn Lichtenberg Group, Oxford Philosophy of Physics, Perimeter Institute, Rutgers Philosophy (foundations)

**Philosophy of Science (21):** Pittsburgh Center for Phil of Science, Rotman Institute, Minnesota Center for Phil of Science, CPNSS (LSE), Descartes Centre (Utrecht), Tilburg TiLPS, IHPST Paris, MPIWG Berlin, Bristol Philosophy of Science, Ghent Centre for Logic and Phil of Science, Vienna Circle Institute, Helsinki Philosophy of Science, ANU School of Philosophy, Toronto HPS, Sydney Centre Foundations of Science, Hannover FARE group

**Formal / Mathematical Philosophy & Logic (6):** MCMP Munich, ILLC Amsterdam, Arché (St Andrews), LOGOS (Barcelona), Carnegie Mellon Pure and Applied Logic, Leeds Logic Group

**Philosophy of Biology (2):** Konrad Lorenz Institute, Egenis (Exeter)

**Ethics / Political (9):** Oxford Uehiro Centre, Princeton Center for Human Values, Harvard Safra Center for Ethics, Georgetown Kennedy Institute, Oxford Institute for Ethics in AI, Cambridge CSER, Hastings Center, Stanford HAI, Yale EPE

**Epistemology (3):** Edinburgh Epistemology, Cologne Epistemology, KU Leuven Epistemology

**Philosophy of Mind / Cognitive Science (6):** NYU Center for Mind Brain Consciousness, Berlin School of Mind and Brain, ANU Consciousness Group, Monash Consciousness Centre, Sussex Centre for Consciousness Science, Antwerp Centre Philosophical Psychology

**Continental / History of Philosophy (8):** Husserl Archives (Leuven), Hegel-Archiv (Bochum), Warwick Post-Kantian Philosophy, Wuppertal Hegel Research, Jena German Idealism, Heidelberg German Idealism, Villanova Phenomenology, New School Philosophy, Freiburg Husserl-Archiv, Copenhagen Centre for Subjectivity Research, Essex Phenomenology

**Philosophy of Language (3):** LOGOS (Barcelona), MIT Linguistics and Philosophy, Institut Jean Nicod Paris

**Asian / Non-Western Philosophy (2):** NTU Singapore Philosophy, Hawaii Philosophy

**Major Departments (6):** NYU Philosophy, Pittsburgh HPS, Michigan Philosophy, Oxford Faculty of Philosophy, Cambridge Faculty of Philosophy, Edinburgh Philosophy

**News / Blog Aggregators (2):** Philosophy of Physics Society, Daily Nous Job Market

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
