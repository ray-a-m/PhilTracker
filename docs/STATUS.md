# PhilTracker — Running Status

**Purpose:** Session-to-session continuity. Read this first when picking up work. Update it at the end of each session.

---

## Current state

**Phase:** Phase 1 complete; ready for Phase 2 (LLM pipeline)
**Last updated:** 2026-04-20
**Last session:** T1–T3 executed as one coordinated batch; 38 tests green

## What's done

### Planning (2026-04-20 early session)
- ✅ `SPEC.md` rewritten for email-digest MVP
- ✅ Deltas: `duration` kept as LLM free-text; `rejection_reason` removed (silent `active=0` reject); plus-addressed From + Sieve rule for per-listing routing; run-failure email path; autoescape + `<script>` snapshot test; corpus seed thresholds
- ✅ `README.md` rewritten; `docs/PLAN.md` authored; `docs/STATUS.md` created
- ✅ `requirements.txt` updated (fastapi/uvicorn → anthropic, jinja2, python-dotenv, black)
- ✅ Stale `docs/CONTRIBUTING.md` deleted

### Phase 1 — Foundation (2026-04-20 execution session)
- ✅ **T1:** `backend/models.py` rewritten to listings-only schema; added helpers `get_known_urls`, `get_new_active_listings`, `count_rejected_today` for T10
- ✅ **T2:** Deleted `backend/app.py`, `backend/relevance.py`, `frontend/`, `tests/test_relevance.py`; rewrote `tests/test_models.py` for new schema
- ✅ **T3:** `Listing` dataclass dropped `start_date`/`aos_raw`/`salary`, added `summary`/`confidence`/`active`; updated 4 scrapers (`philjobs`, `taking_up_spacetime`, institutional `static_scraper` + `wordpress_scraper`) to stop passing removed kwargs; `backend/dedup.py` simplified — no more `secondary_urls`, no merge logic (fuzzy match returns "duplicate"); `tests/test_dedup.py` + `tests/test_scrapers.py` updated
- ✅ `.gitignore` adds `config.local.yaml`, `.DS_Store`

### Checkpoint 1 verification
- ✅ Fresh `init_db()` shows `listings` only
- ✅ `pytest` → 38 passed, 0 failed
- ✅ No dangling imports of deleted modules
- ✅ `scheduler.run_all` still imports cleanly (breaks expected in T4 when tagger is rewritten; bundled T4 fixes it)

## What's next

**Immediate:** **T4 — `llm/prompts.py` + trim `tagger/keywords.py` to yaml-loader-only.**

**Before T5 (client wrapper):** verify Anthropic prompt-caching 1-hour TTL API syntax against current SDK docs. Don't guess.

**Pre-flight items already satisfied:**
- Working tree was clean
- No `philtracker.db` to delete
- User confirmed Anthropic API key + Fastmail app password in hand

**Ground-truth URLs to collect before T12:** Pitt Center for Philosophy of Science postdoc, Minnesota Center postdoc (user to supply exact URLs).

## Architecture decisions locked (don't reopen without flagging)

From the refine session:

1. Destructive schema migration (`rm philtracker.db`)
2. `tagger/keywords.py` becomes a ~10-line `tags.yaml` loader (consumed by `llm/prompts.py`)
3. `mailer/send.py` handles digest + per-listing in one SMTP connection; failure-notice uses a minimal stdlib path
4. Snapshots: synthetic fixtures committed; real-data outputs stay local (`*.local.html`)
5. Corpus seeding happens post-first-dry-run (Phase 5, after T11)
6. URL-cache filter is explicit in `scheduler/run_all.py` (before LLM loop); `llm/extract.py` assumes fresh input
7. `send_failure_notice` wrapped in its own try/except; stderr fallback
8. `--live` flag via `conftest.py` (`@pytest.mark.live`, skipped by default)
9. `rejection_reason` column does not exist; rejects are `active=0` rows for URL caching only
10. `duration` is LLM-extracted free-text, rendered in digest when non-empty

## Known stale / to-handle items

- `tests/test_relevance.py` — deleted in T2 (module gone)
- `tests/test_models.py` — rewritten in T2 (new schema)
- `tests/test_dedup.py`, `test_tagger.py`, `test_scrapers.py` — fields updated in T2
- `.env.example`, `config.example.yaml` — created in T11 (previously missing)

## Blockers / open questions

- None active. Ready to execute T1 on next action.

## Session log (most recent first)

### 2026-04-20 — Phase 1 execution
- T1+T2+T3 merged into one coordinated batch (tight coupling: Listing dataclass changes ripple through 4 scrapers + dedup + 3 test files)
- Destructive dedup decision: dropped secondary_urls + merge logic entirely; fuzzy matches return "duplicate". LLM-canonicalized title/institution should make this cleaner in practice, and the merge path had no visible consumers post-refactor.
- `test_init_db_listings_only` initially failed due to SQLite's auto-created `sqlite_sequence` table (side effect of AUTOINCREMENT); fixed by excluding `sqlite_%` from the table check
- `.gitignore` extended for `config.local.yaml` + `.DS_Store`
- 38 tests green, no dangling imports

### 2026-04-20 — Planning + docs refresh
- Idea-refine session: flipped `rejection_reason` → silent reject; added `duration` as LLM-extracted free-text; converged on plus-addressed From + Sieve rule for per-listing pinning
- Locked minimal-but-useful additions: run-failure email, autoescape test, corpus seed thresholds, shared `listing.html.j2` partial. Dropped urgent-deadline highlight at user's request.
- Stress-tested the refactor plan; accepted 5 substantive issues (URL-cache explicit, failure-notice inner try/except, corpus-seed reorder, committed synthetic snapshots, 1-hour cache TTL verification)
- Wrote `docs/PLAN.md`, `docs/STATUS.md`; rewrote `README.md`; updated `requirements.txt`
- Identified and flagged stale docs/tests

---

## How to update this file

At end of each session, update:
1. **Current state** — bump phase/task/date
2. **What's done** — add completed tasks (ticked)
3. **What's next** — replace with the actual next action, not a generic "continue"
4. **Blockers / open questions** — add anything waiting on user input
5. **Session log** — prepend one ~3-line entry summarizing what landed

Keep the file under ~200 lines. If it balloons, trim old session-log entries and fold completed items into "What's done" as a one-line summary.
