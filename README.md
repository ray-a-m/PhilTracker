# PhilTracker

**PhilJobs tells you what exists. PhilTracker tells you what matters to you.**

PhilTracker is a local nightly script that scrapes philosophy job and fellowship sources, runs each new listing through Claude Haiku 4.5 for classification + extraction + tagging + summarization, and emails you a subfield-grouped HTML digest via Fastmail. Triage happens in your email client — star to pin, archive to dismiss. No web UI, no backend server.

## Why?

The philosophy job market runs on [PhilJobs](https://philjobs.org), but PhilJobs is only one source. Fellowships at the Pittsburgh Center for Philosophy of Science, Rotman, Minnesota Center, Geneva Symmetry Group, Descartes Centre — these show up on institutional pages, blogs, or general academic job boards, not on PhilJobs. You end up manually checking half a dozen sites every week.

PhilTracker fixes this by:

- **Aggregating** listings from PhilJobs, Taking Up Spacetime, HigherEdJobs, Academic Jobs Wiki, and ~70 institutional fellowship pages
- **Classifying + extracting** each new listing via Claude Haiku 4.5 — filters out blog chatter, canonicalizes title/institution, extracts deadline + duration, assigns subfield tags, and writes a one-sentence summary
- **Sending a daily digest** grouped by subfield, with your interest-matched sections first
- **Star-to-pin via Fastmail:** each listing is also delivered as an individual email to a `PhilTracker/Listings` folder. Starring one there = pinning it. Your email client is the triage UI.

The email is a daily receipt that the tool ran. No news is also news — empty days still send a "no new listings today" email. Failed runs send a plaintext failure notice. Silence is the failure mode to avoid.

## Status

🚧 **Rewriting toward v1.** A daily-digest MVP replaces the earlier web-app design. Canonical scope: [`docs/SPEC.md`](docs/SPEC.md). Implementation plan: [`docs/PLAN.md`](docs/PLAN.md).

## How it works

```
scrape → classify/extract/tag/summarize (Haiku 4.5, one call per new listing)
       → dedup → insert → render digest + per-listing emails → Fastmail SMTP
```

- One structured LLM call per new listing (prompt-cached system prompt, 1-hour TTL)
- URL cache: a listing URL already in the DB is never re-sent to the LLM, so daily cost stays near zero after warm-up
- Rejects silently marked `active=0` — row exists only to keep the URL cached
- Nightly run always ends with an email: digest, "no new listings," or `[PhilTracker] FAILED` notice

## Sources

### Standalone scrapers

| Source | Type | Status |
|---|---|---|
| PhilJobs (all categories) | Job board | Implemented |
| Taking Up Spacetime | Blog (philosophy of physics) | Implemented |
| HigherEdJobs | General academic job board (Playwright) | Implemented |
| Academic Jobs Wiki | Wiki (Philosophy & Humanities postdocs) | Implemented |

### Institutional sites (configurable — `scrapers/institutional/config.yaml`)

Add new sites by editing the config file — no new code needed. Currently ~70 sites across all subfields. The categories (Philosophy of Physics / Foundations, Philosophy of Science, Formal / Mathematical, Philosophy of Biology, Ethics / Political, Epistemology, Mind / Cognitive Science, Continental / History, Language, Non-Western, Major Departments, Aggregators) are broken down in `scrapers/institutional/config.yaml`.

## Subfield tags

PhilTracker uses a granular tagging system. The canonical list lives in [`tagger/tags.yaml`](tagger/tags.yaml); each tag has a slug, human label, and short definition. Examples:

- `philosophy-of-physics`
- `foundations-of-quantum-mechanics`
- `philosophy-of-cosmology`
- `philosophy-of-biology`
- `formal-epistemology`
- `history-and-philosophy-of-science`
- `metaphysics-of-science`
- `german-idealism`
- `social-epistemology`

The LLM reads the tag list + definitions at classification time and assigns one or more tags per listing. Want a new tag? Edit `tags.yaml`; it's live the next run.

## Getting started

### Prerequisites

- Python 3.11+
- An Anthropic API key ([console.anthropic.com](https://console.anthropic.com))
- A Fastmail account with an app password (Fastmail → Settings → Password & Security → App passwords)

### Install

```bash
git clone https://github.com/yourname/philtracker.git
cd philtracker
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium   # only needed for Playwright-based scrapers (HigherEdJobs)
```

### Configure

```bash
cp .env.example .env
cp config.example.yaml config.local.yaml
```

Fill in `.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
FASTMAIL_USERNAME=you@fastmail.com
FASTMAIL_APP_PASSWORD=...
DIGEST_RECIPIENT=you@fastmail.com
DIGEST_SENDER=you+philtracker-digest@fastmail.com
LISTING_SENDER=you+philtracker-listing@fastmail.com
```

Edit `config.local.yaml` with your subfield interests (format documented in `config.example.yaml`).

### Fastmail Sieve rule (one-time setup)

So per-listing emails land in a dedicated folder instead of your inbox:

1. Fastmail → **Settings** → **Filtering** → **New rule**
2. Condition: `From` contains `philtracker-listing`
3. Action: **Move to folder** `PhilTracker/Listings` (create it)
4. Save

Without this rule, per-listing emails clutter your inbox.

### First run

```bash
python -m scheduler.run_all --dry-run    # prints everything to stdout, no SMTP
python -m scheduler.run_all               # real send
python -m scrapers.philjobs               # debug a single scraper (no LLM, no email)
```

### Nightly automation (macOS)

```bash
cp scheduler/com.philtracker.nightly.plist.example ~/Library/LaunchAgents/com.philtracker.nightly.plist
launchctl load ~/Library/LaunchAgents/com.philtracker.nightly.plist
```

## How to use

- **Morning:** read the digest in your inbox. It's the daily receipt — you don't need to check job sites.
- **Triage:** open `PhilTracker/Listings`, find tonight's interesting items, star them. `folder:PhilTracker/Listings is:starred` = your pinned applications.
- **Dismiss:** leave it unstarred. It stays in the folder for reference but is out of sight.
- **Expired pinned listings:** Fastmail doesn't know a listing expired — that's on you to re-check when applying.

## Architecture

```
scrapers/     One class per source; each outputs raw Listing (URL + raw description).
llm/          Single structured Claude call per new listing.
tagger/       Loads subfield definitions from tags.yaml (LLM-free — just a yaml loader).
backend/      SQLite schema + CRUD (listings table only; no users, no auth).
mailer/       jinja2 renderer + Fastmail SMTP sender (digest + per-listing in one connection).
scheduler/    Entry point; chains scrape → LLM → dedup → render → send, with failure-notice catch.
```

## Tech stack

- Python 3.11+
- `requests` + `beautifulsoup4`; Playwright only where JS rendering is unavoidable
- `anthropic` SDK — Claude Haiku 4.5 (`claude-haiku-4-5-20251001`)
- `jinja2` for HTML templates
- `smtplib` + `email.mime` (stdlib) for Fastmail SMTP
- SQLite via `sqlite3` (no ORM)
- GitHub Actions for CI (tests only — **never** for scraping)

## Contributing

Scope is "one philosopher on the job market." Adding a scraper or subfield tag is the highest-value contribution. File an issue first to avoid duplicated work.

## License

MIT. Do whatever you want with this.
