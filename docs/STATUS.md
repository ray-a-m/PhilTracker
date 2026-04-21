# PhilTracker — Running Status

**Purpose:** Session-to-session continuity. Read this first when picking up work. Update it at the end of each session.

---

## Current state

**Phase:** v1 code complete (Phases 1–4 done; Phase 5 scaffolded). User-side seeding + first real send is all that remains.
**Last updated:** 2026-04-20
**Last commit:** `f2f90b4` — Phase 5 scaffold (example configs, live-test harness)
**Test suite:** 61 passed, 2 skipped (the 2 skips are `@pytest.mark.live` tests that opt in with `pytest --live`)

## What's done

- **Phase 1 — Foundation:** listings-only SQLite schema; `Listing` dataclass updated; `dedup.py` simplified; FastAPI/frontend/relevance code removed; 4 scrapers + 4 test files updated.
- **Phase 1.5 — Tag split:** `german-idealism` → separate `kant` + `hegel` slugs (Schelling/Fichte dropped; Naturphilosophie under `hegel`); 6 institutional sites relabeled.
- **Phase 2 — LLM pipeline (`llm/`):** `prompts.py` (SYSTEM_PROMPT built from `tags.yaml` at import), `client.py` (forced tool_choice + 1h ephemeral cache + retry-with-backoff + corrective retry), `extract.py` (single-call classify + extract); prompt snapshot committed; 10 tests.
- **Phase 3 — Rendering + sending (`mailer/`):** jinja2 with `select_autoescape`; shared `listing.html.j2` partial between digest and per-listing emails; `render.py` with interest-first section ordering; `send.py` with single-connection digest+per-listing dispatch and stdlib-only failure-notice path wrapped in its own try/except; 3 committed snapshots; 13 tests.
- **Phase 4 — Scheduler rewire:** `run_all.py` rewritten end-to-end; URL-cache filter is explicit before the LLM loop; top-level `try/except` dispatches `send_failure_notice` before re-raising; 4 integration tests.
- **Phase 5 scaffold (T11a/T12a/T13a):** `.env.example`, `config.example.yaml`, `tests/conftest.py` (`--live` flag), `tests/ground_truth.yaml` (Newton seeded + Pitt/UMinn placeholders), `tests/classifier_corpus.yaml` (schema + 30-item seeding checklist), plus their test files (skip until thresholds met).

## What remains — user-side only

The code is shipped. What's left cannot be automated; it requires credentials, real listing text, or browser/Fastmail interaction.

### 1. First live dry-run

```bash
cp .env.example .env                    # fill in ANTHROPIC_API_KEY, FASTMAIL_USERNAME, FASTMAIL_APP_PASSWORD
cp config.example.yaml config.local.yaml # replace with your real interests
python -m scheduler.run_all --dry-run   # prints digest + per-listing to stdout; no SMTP
```

Raymond's real interests per memory: `philosophy-of-physics`, `philosophy-of-science`, `kant`, `hegel`.

### 2. Seed `tests/ground_truth.yaml` to ≥10

Currently 1 seeded entry (Newton) + 2 commented-out placeholders (Pitt Center postdoc, Minnesota Center postdoc — user supplies real URLs). Target: ≥10 entries, at least one per active scraper (`philjobs`, `spacetime`, `academic_jobs_wiki`, `higheredjobs`, `institutional`).

Run: `pytest --live tests/test_ground_truth.py` (skips until ≥10).

### 3. Seed `tests/classifier_corpus.yaml` to ≥30 (15 positive / 15 negative)

Best source: copy real listing text from the dry-run's stdout, label each. Schema + seeding checklist are inline in the file.

Run: `pytest --live tests/test_classifier_corpus.py` (skips until ≥30). Asserts precision + recall ≥ 0.95.

### 4. Fastmail Sieve rule (one-time)

Fastmail → Settings → Filtering → new rule: `From contains "philtracker-listing" → Move to PhilTracker/Listings`.

### 5. First real send

```bash
python -m scheduler.run_all
```

Verify: digest lands in Inbox; per-listing emails in `PhilTracker/Listings`; starring one persists.

### 6. Optional (Phase 7, post-v1)

- `scheduler/com.philtracker.nightly.plist.example` — macOS `launchd` plist for nightly automation (not yet created)
- Per-scraper baseline alerting (drop to zero vs. 7-day median)
- Grow classifier_corpus toward ~200 as FPs/FNs show up in real use

### Definition of done (from SPEC)

1. ✅ `python -m scheduler.run_all` runs end-to-end on a fresh checkout
2. ⏳ A daily digest arrives via Fastmail (needs step 5)
3. ⏳ Per-listing emails routed to `PhilTracker/Listings` (needs step 4 + 5)
4. ✅ Empty-digest days send a receipt (tested)
5. ✅ Failed runs send a failure notice (tested)
6. ✅ `pytest` green without `--live`
7. ⏳ `pytest --live` green (needs step 2 + 3)
8. ⏳ LLM day-cost < $0.50 (measured in step 1 + 5)
9. ⏳ Repo owner uses it during a cycle and stops manually checking (outcome)

## Architecture decisions locked (don't reopen without flagging)

1. Destructive schema migration (`rm philtracker.db`)
2. `tagger/keywords.py` is a yaml loader only; LLM does all tagging
3. `mailer/send.py` handles digest + per-listing in one SMTP connection; failure-notice uses a minimal stdlib path
4. Snapshots: synthetic fixtures committed; real-data outputs stay local (`*.local.html`)
5. Corpus seeding happens post-first-dry-run
6. URL-cache filter is explicit in `scheduler/run_all.py` BEFORE the LLM loop
7. `send_failure_notice` wrapped in its own try/except; stderr fallback
8. `--live` flag via `conftest.py` (`@pytest.mark.live`, skipped by default)
9. No `rejection_reason` column — rejects are `active=0` rows for URL caching only
10. `duration` is LLM-extracted free-text
11. `kant` and `hegel` are separate slugs (not bundled under `german-idealism`)

## Blockers

None. Ball is in the user's court for steps 1–5 above.

## Session log (compressed)

- **2026-04-20 — Phase 5 scaffold:** example configs + conftest + ground_truth/corpus YAML + their test files. 61 passed, 2 skipped.
- **2026-04-20 — Phase 4:** scheduler rewired end-to-end; 4 integration tests; URL-cache filter before LLM loop.
- **2026-04-20 — Phase 3:** `mailer/` module; 13 tests; 3 committed snapshots; `<script>` escape verified.
- **2026-04-20 — Phase 2:** `llm/` module; prompt built from tags.yaml; 1h cache verified against SDK; 10 tests.
- **2026-04-20 — Phase 1:** schema listings-only; FastAPI/frontend purged; dedup simplified (no merge, no secondary_urls); Listing dataclass updated; 38 tests.
- **2026-04-20 — Planning:** idea-refine session locked the shape (silent reject, duration kept, plus-addressed From + Sieve rule, failure-notice, snapshot tests); `SPEC.md`, `PLAN.md`, `README.md` written.

## How to update this file

At end of each session:
1. **Current state** — bump phase/date/commit
2. **What's done** — keep as a compact per-phase summary
3. **What remains** — crisp, numbered, user-actionable
4. **Session log** — prepend one one-liner; compress older entries
5. Target ≤ 150 lines total
