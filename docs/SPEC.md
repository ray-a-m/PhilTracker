# Spec: PhilTracker v1 — Email Digest MVP

**Status:** ACCEPTED
**Last updated:** 2026-04-20
**Related:** [docs/ideas/email-digest-mvp.md](ideas/email-digest-mvp.md)

## Objective

A local nightly script that scrapes philosophy job/fellowship sources, runs each new listing through a Claude LLM for classification + extraction + tagging + summarization, and emails a subfield-grouped HTML digest to the user via Fastmail SMTP. No web UI, no backend server, no pin functionality. Triage happens in the user's email client (star to pin, archive to dismiss).

**Primary persona:** one philosopher running their own instance during their own job search.
**Secondary persona:** other philosophers forking the repo for personal use.
**Not a v1 persona:** hosted multi-tenant users.

### v1 is done when

1. A scrape run (`python -m scheduler.run_all`, or scheduled via `launchd`) completes end-to-end: scrape → classify/extract/tag/summarize via LLM → dedupe → email.
2. The digest arrives daily via Fastmail, grouped by subfield, with deadlines shown (including a "no deadline listed" label for listings without one).
3. Results are overwhelmingly real job/fellowship/postdoc/TT postings. No blog announcements, no unrelated CFPs, no dead pages.
4. Known targets (e.g. Newton International Fellowship) are caught, not missed.
5. The repo owner uses it during a real application cycle and stops checking job sites manually.

### Explicitly NOT in v1

- Web UI, FastAPI server, `/api/*` endpoints
- Pin table, pin endpoint, pin UX (Gmail-equivalent star in Fastmail replaces this)
- `user_profiles`, `users`, `user_listing_status` tables
- Profile-based relevance scoring (`backend/relevance.py`)
- Calendar integration, reminders, RSS output
- Multi-user accounts, authentication
- Hosted deployment

## Tech Stack

- Python 3.11+
- `requests` + `beautifulsoup4`; Playwright only where JS rendering is unavoidable
- `anthropic` SDK — Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) for structured LLM calls, with prompt caching enabled
- `python-dotenv` for loading secrets
- `smtplib` + `email.mime` (stdlib) for Fastmail SMTP delivery
- `jinja2` for the HTML email template
- SQLite (via `sqlite3`, no ORM) — minimal schema, just what the pipeline needs
- GitHub Actions for CI (tests + classifier corpus eval) — never for scraping
- `launchd` (macOS) plist sample for optional nightly runs

## Commands

```
pip install -r requirements.txt
playwright install chromium                 # only for JS-based scrapers

python -m scheduler.run_all                 # scrape → LLM → dedupe → email
python -m scheduler.run_all --dry-run       # run pipeline, print digest to stdout instead of emailing
python -m scrapers.philjobs                 # debug a single scraper (no LLM, no email)

python -m pytest                            # unit + scraper-fixture tests
python -m pytest tests/test_classifier.py   # classifier corpus eval (mocked LLM)
python -m pytest --live                     # run ground-truth + classifier against live services
black .

# Optional nightly trigger (macOS):
cp scheduler/com.philtracker.nightly.plist.example ~/Library/LaunchAgents/com.philtracker.nightly.plist
launchctl load ~/Library/LaunchAgents/com.philtracker.nightly.plist
```

## Project Structure

```
config.example.yaml             Interests template — committed
config.local.yaml               Interests + per-section priority — GITIGNORED
.env.example                    API-key + SMTP template — committed
.env                            ANTHROPIC_API_KEY, FASTMAIL_* — GITIGNORED

scrapers/
  base.py                       Listing dataclass + BaseScraper
  philjobs.py, higheredjobs.py, taking_up_spacetime.py, academic_jobs_wiki.py
  institutional/
    config.yaml                 per-site config (url, type, subfield)
    runner.py                   driver that reads config and dispatches
    static_scraper.py, wordpress_scraper.py

llm/
  client.py                     NEW: anthropic client wrapper with prompt-caching on system prompt
  extract.py                    NEW: the single structured call — classify + extract + tag + summarize
  prompts.py                    NEW: system + user prompt templates; tag definitions pulled from tagger/tags.yaml

tagger/
  tags.yaml                     canonical subfield slug list + definitions/keywords (fed into LLM prompt)
  keywords.py                   thin loader for tags.yaml (LLM-free; keyword-matching logic removed)

backend/
  models.py                     SQLite schema + CRUD — listings table only, no users/profiles/pins
  dedup.py                      URL + (title, institution) near-duplicate collapse across sources
  config.py                     loads config.local.yaml (interests, subfield ordering)

mailer/
  render.py                     NEW: renders digest + per-listing HTML via jinja2
  send.py                       NEW: Fastmail SMTP via smtplib (sends digest + N per-listing emails in one connection); minimal plaintext failure-notice path
  templates/
    digest.html.j2              NEW: digest email — subfield sections, interest-aligned first
    listing.html.j2             NEW: single-listing partial, shared by digest entries and per-listing emails

scheduler/
  run_all.py                    main pipeline: scrape → LLM → dedupe → insert → render → send
  com.philtracker.nightly.plist.example   sample launchd agent

tests/
  fixtures/                     frozen HTML samples
  ground_truth.yaml             listings that must be caught (seeded with Newton)
  classifier_corpus.yaml        ~200 labelled pos/neg examples for precision/recall
  mocked_llm_responses/         recorded LLM outputs for CI replay

docs/
  SPEC.md
  PLAN.md
  STATUS.md
  ideas/email-digest-mvp.md
```

## Listing contract

```
id                  int         auto
url                 str         required, unique  (canonical key)
source              str         required          (e.g. "PhilJobs")
title               str         LLM-canonicalized
institution         str         LLM-canonicalized
deadline            str | null  ISO-8601 date; null if no deadline listed
location            str
duration            str         LLM-extracted free-text (e.g. "2 years", "9-month visiting"); empty if absent
description         str         raw text snippet from the source
summary             str         LLM-generated 1-sentence summary
aos                 list[str]   subfield tag slugs (LLM-assigned)
listing_type        str         "job" | "fellowship" | "postdoc" | "phd" | "unknown"
confidence          float       LLM-reported 0.0–1.0 for is_posting
active              bool        true = real + current; false = expired or rejected
date_scraped        str         ISO-8601
date_first_seen     str         ISO-8601 — used for "new today" selection
```

**New vs. v0 schema:** adds `summary`, `confidence`. Keeps `duration` (now LLM-extracted rather than scraper-populated). Drops `start_date`, `aos_raw`, `salary` (unused). Drops `users`, `user_listing_status`, `user_profiles` tables entirely.

## LLM pipeline

**Single call per new listing.** Combines classification + extraction + tagging + summarization.

- **Model:** Claude Haiku 4.5 (`claude-haiku-4-5-20251001`). Escalate to Sonnet 4.6 only if corpus eval drops below threshold.
- **Prompt caching:** system prompt (schema + tag list + tag definitions + classification rules) is cached. Repeated calls within one scheduler run pay only for the user-message (listing text) portion.
- **Security:** listing text is untrusted third-party content. Wrap it in delimited `<listing_text>...</listing_text>` tags in the user message; system prompt explicitly instructs the model to treat everything inside those tags as data, not instructions. Never execute or shell-out anything the LLM returns.
- **Structured output:** use Anthropic tool-use / JSON schema to force a response shape:
  ```json
  {
    "is_posting": true,
    "confidence": 0.94,
    "posting_type": "fellowship",
    "title": "Newton International Fellowship 2026",
    "institution": "Royal Society",
    "deadline": "2026-03-25",
    "location": "United Kingdom",
    "duration": "2 years",
    "aos": ["philosophy-of-physics", "philosophy-of-science"],
    "summary": "Two-year postdoctoral fellowship for early-career researchers..."
  }
  ```
- **Cache behavior:** a listing URL already in the DB is not re-sent to the LLM (regardless of `active`). The prior classification stands. This keeps daily cost near zero after the first warm-up and prevents rejected URLs from being re-classified every day.
- **Rejects:** `is_posting == false` → insert with `active=0`. The URL is cached so it won't be re-classified tomorrow; the row never appears in the digest (which filters `active=1`). No separate audit column — diagnose false negatives by re-running the classifier on the offending URL with verbose logging.
- **Cost budget:** <$0.50/day once warm.
- **Retries:** on transient API failure, retry 3× with exponential backoff. On schema validation failure, retry once with a corrective hint.

## Email digest

**Delivery:** Fastmail SMTP (`smtp.fastmail.com:465` SSL). Credentials in `.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
FASTMAIL_USERNAME=you@fastmail.com
FASTMAIL_APP_PASSWORD=...         # Fastmail → Settings → Password & Security → App passwords
DIGEST_RECIPIENT=you@fastmail.com
DIGEST_SENDER=you+philtracker-digest@fastmail.com
LISTING_SENDER=you+philtracker-listing@fastmail.com
```

**Per-run email shape:** each nightly run sends two kinds of email, both via the same SMTP connection:

1. **One digest** from `DIGEST_SENDER` → lands in Inbox. The daily receipt.
2. **N per-listing emails** (one per new `active=1` listing) from `LISTING_SENDER` → filtered into a `PhilTracker/Listings` folder by a user-configured Fastmail Sieve rule. Each is an independently starrable message; Fastmail's star *is* the pin. No bespoke pin code.

**One-time user setup (documented in README):** Fastmail → Settings → Filtering → new rule: `From contains "philtracker-listing" → Move to PhilTracker/Listings`.

The per-listing email uses the same entry partial as the digest (shared `templates/listing.html.j2`), so rendering logic isn't duplicated. Expiration of a pinned listing (`active → 0`) does not touch the starred Fastmail message — that staleness is acceptable.

**Cadence:** daily. The scheduler runs nightly; digest arrives the next morning.

**Contents:**
- Subject: `[PhilTracker] 2026-04-21 — 7 new listings (2 matching your interests)`
- Sections ordered: subfields matching `config.local.yaml` interests first, others below
- Each entry: title (linked), institution, deadline (or "no deadline listed"), location, duration (when non-empty), 1-sentence summary, source attribution
- Footer: total counts, rejected-today count (from `SELECT COUNT(*) FROM listings WHERE active=0 AND date_first_seen=?`), `launchd` status reminder

**What goes in a digest:**
- Listings inserted today (`date_first_seen == today`) with `active == 1`
- Listings with no detected deadline are included with a "no deadline listed" label
- Rejected listings never appear in the digest; they sit in the DB with `active=0` purely to keep the URL cached (so tomorrow's scrape doesn't re-classify them)

**Empty-digest rule:** if no new listings today, still send an email: `[PhilTracker] 2026-04-21 — no new listings`. The receipt matters more than the content. Skipping the email would reintroduce the "did it run?" anxiety.

**Run-failure rule:** `scheduler.run_all` wraps its top-level work in `try/except`. On any unhandled exception, send a plaintext `[PhilTracker] FAILED <date> — <short reason>` email to `DIGEST_RECIPIENT` via a minimal SMTP path that does not depend on the LLM client or the jinja renderer (so failures in those modules still produce a notification). Same anti-anxiety principle as the empty-digest rule: silence is the failure mode to avoid.

## Code Style

```python
class NewtonFellowshipScraper(BaseScraper):
    name = "Newton International Fellowship"
    url = "https://royalsociety.org/grants/schemes/newton-international/"

    def scrape(self) -> list[Listing]:
        soup = self.fetch()
        listings: list[Listing] = []
        for block in soup.select(".listing"):
            listings.append(
                Listing(
                    url=block.select_one("a")["href"],
                    source=self.name,
                    title=block.select_one("h3").get_text(strip=True),
                    description=block.get_text(" ", strip=True),
                )
            )
        return listings
```

Scrapers extract what they can — URL + whatever raw text they have. The LLM canonicalizes. If a scraper's selector breaks, the LLM still works from `description`.

- Formatted with `black` (88-char line)
- Type hints on all public functions
- No comments unless the *why* is non-obvious
- BeautifulSoup + `requests` first; Playwright only when JS is required

## Testing Strategy

- **Framework:** pytest
- **Unit tests:** dedup, date parsing, digest rendering (snapshot against `templates/digest.html.j2`), LLM prompt construction
- **Scraper tests:** frozen HTML fixtures in `tests/fixtures/`. No live HTTP in CI.
- **Classifier corpus** (`tests/classifier_corpus.yaml`): ≥30 labelled pos/neg listing texts (15 positive / 15 negative) before first live run; grow toward ~200 over normal use. Mocked Anthropic client replays recorded responses in CI. Precision ≥ 95%, recall ≥ 95%.
- **Ground truth** (`tests/ground_truth.yaml`): listings that must appear in a live scrape. Run only with `--live` flag (requires network + API key). ≥10 entries before first live run, at least one per scraper where possible. Seeded with Newton International Fellowship.
- **Email render snapshot:** given a fixed listings list, rendered HTML matches a checked-in snapshot.
- **HTML escaping:** `templates/*.html.j2` rely on jinja2 autoescape (default-on for `.html` family). Snapshot test includes a listing whose `summary` contains `<script>alert(1)</script>` — rendered output must show the literal text, not execute it. Defense against prompt-injection via listing text surviving the LLM.
- **SMTP dry-run:** `python -m scheduler.run_all --dry-run` prints the digest + per-listing emails to stdout instead of sending. Must work without SMTP credentials.
- **Coverage target:** 80% for `backend/`, `llm/`, `mailer/`.

## Boundaries

**Always:**
- Run `pytest` before merging
- When fixing a false negative, pin the listing into `ground_truth.yaml`
- When fixing a false positive, add its text to `classifier_corpus.yaml` as a labelled negative
- Update this spec when scope or architecture changes

**Ask first:**
- SQLite schema changes
- Adding a dependency
- Bulk edits to `institutional/config.yaml`
- Changing the LLM model default
- Any new GitHub Actions workflow

**Never:**
- Commit `philtracker.db`, `config.local.yaml`, `.env`, or any scraped data
- Silently drop listings — rejects keep `active=0` + `rejection_reason`
- Run the scraper from CI
- Send email from CI
- Execute anything the LLM returns as code

## Success Criteria (testable)

1. Classifier precision ≥ 95% on labelled corpus
2. Classifier recall ≥ 95% on labelled corpus
3. Ground-truth set returns 100% on a live scrape
4. `python -m scheduler.run_all` runs end-to-end on a fresh checkout without exceptions
5. A daily digest arrives in the Fastmail inbox, grouped by subfield, with interest-matched sections first, including a "no deadline listed" label where applicable
6. Empty-digest days still send a receipt email
7. LLM daily cost stays under $0.50 after cache warm-up
8. Source-coverage audit: every site in `institutional/config.yaml` either returns ≥1 listing within 30 days, or is removed from the config
9. Repo owner uses it during one real job-market cycle and stops manually checking sites

## Decisions (resolved 2026-04-20)

1. **Shape:** email-digest MVP. No web UI, no backend server, no pin. See [docs/ideas/email-digest-mvp.md](ideas/email-digest-mvp.md).
2. **LLM pipeline:** single structured call per new listing (classify + extract + tag + summarize), prompt caching on the system portion, Haiku 4.5 default.
3. **Email:** Fastmail SMTP via app password, stdlib `smtplib`. Daily cadence. Empty days still get a receipt.
4. **No-deadline listings:** included in the digest with a "no deadline listed" label (hiding them risks silent FNs).
5. **Schema:** listings table only. Drop `users`, `user_listing_status`, `user_profiles`. Add `summary`, `confidence` columns. Keep `duration` (now LLM-extracted free-text); drop unused `start_date`, `aos_raw`, `salary`. No `rejection_reason` column — rejects are silent (`active=0`); diagnose false negatives by re-classifying the URL manually.
6. **Deployment:** fully local. Scraping never runs in CI. No scraped data in the repo.
7. **Security:** listing text wrapped in `<listing_text>` tags in the LLM user message; system prompt instructs the model not to follow embedded instructions. LLM outputs are never executed.

## Comprehensive coverage — how we get there

- **LLM catches FPs** — structured classification with confidence + reason strips non-postings.
- **Ground-truth catches FNs** — missed listings get pinned into `ground_truth.yaml` (Newton seeded).
- **Source audit catches dead sources** — sites returning zero listings for 30 days are flagged for removal.
- **Scraper-quality degrades gracefully** — because the LLM re-extracts canonical fields, a broken selector yields a still-usable digest entry instead of a garbage row.

---

*Spec accepted → proceed to PLAN phase.*
