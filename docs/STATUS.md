# PhilTracker — Running Status

**Purpose:** Session-to-session continuity. Read this first when picking up work. Update it at the end of each session.

---

## Current state

**Phase:** Pre-flight (before T1)
**Last updated:** 2026-04-20
**Last session:** Spec refinement + implementation plan authored

## What's done

- ✅ `SPEC.md` rewritten for email-digest MVP (no FastAPI, no frontend, no pin table)
- ✅ `SPEC.md` deltas applied: `duration` kept as LLM-extracted free-text; `rejection_reason` removed (silent reject via `active=0`)
- ✅ `SPEC.md` additions: plus-addressed From aliases + Sieve rule for per-listing routing; run-failure email; autoescape + `<script>` snapshot test; corpus seed thresholds (ground_truth ≥10, classifier_corpus ≥30)
- ✅ `docs/ideas/email-digest-mvp.md` updated to match spec
- ✅ `README.md` rewritten: new architecture, Fastmail setup, Sieve rule, star-to-pin workflow
- ✅ `docs/PLAN.md` authored (15 tasks, 6 phases, ~15 hrs weekend-shippable)
- ✅ `requirements.txt` updated: removed fastapi/uvicorn; added anthropic, jinja2, python-dotenv, black

## What's next

**Immediate:** Pre-flight checklist in `docs/PLAN.md`, then start **T1 (rewrite `backend/models.py` schema)**.

Pre-flight reminders:
- `rm philtracker.db` (no data to preserve — user confirmed)
- Confirm Anthropic API key + Fastmail app password in hand
- User provided ground-truth URLs to collect during T12: Pitt Center postdoc, Minnesota Center postdoc (add to `tests/ground_truth.yaml` alongside Newton — user will supply exact URLs at T12 time)

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
