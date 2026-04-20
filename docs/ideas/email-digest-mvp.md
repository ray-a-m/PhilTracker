# PhilTracker — Email Digest MVP

*Produced 2026-04-20 via `idea-refine`.*

## Problem Statement

How might a philosopher on the job market feel confident they've seen every relevant opportunity, without the burden of manually checking a dozen sites?

## Recommended Direction

A local script that scrapes configured sources nightly, filters results with an LLM classifier, and emails the user an HTML digest of new listings grouped by subfield. Triage happens in the user's email client — star to pin, archive to dismiss. No web UI, no backend server, no pin endpoint.

This directly targets the real pain (anxiety about missing things): **the email is a daily receipt that the tool did its job.** A UI offers a place to go but offers no receipt, so anxiety returns on any day the user forgets to visit. Email keeps arriving regardless, and that's the anti-anxiety mechanism.

It also front-loads shipping. One weekend to a useful v1, versus several weekends for the FastAPI + frontend path. The project already paused once — the biggest risk isn't wrong features, it's never shipping again.

## Key Assumptions to Validate

- [ ] **The user actually reads the digest.** Validate by: using it for 2 weeks of real job-search activity and tracking whether you open each day's email.
- [ ] **Classifier ≥95% precision.** Validate by: scoring a labelled corpus of ~200 examples against Claude Haiku 4.5 output.
- [ ] **Classifier ≥95% recall.** Validate by: `tests/ground_truth.yaml` that must never regress (seeded with Newton International Fellowship).
- [ ] **Gmail star/archive is enough for "pin" behavior.** Validate by: 4 weeks of real use. If you find yourself copy-pasting listings into a separate doc, that's a genuine signal to add a UI.
- [ ] **Daily is the right cadence.** Validate by: starting daily, switching to weekly if it feels noisy.

## MVP Scope

**In:**
- Scrapers — existing 4 standalone + institutional config runner (no changes to their shape)
- Classifier — Claude Haiku 4.5 post-pass, URL-cached, rejects silently marked `active=0` (row kept only to cache the URL)
- Tagger — existing keyword matching against `tags.yaml`
- Dedup against a `seen_urls` table so a listing appears in at most one digest
- HTML email renderer, grouped by subfield tag, deadlines highlighted, "new since last digest" framing
- SMTP delivery via Gmail app password (stdlib `smtplib` — no third-party dep)
- `launchd` sample plist for nightly trigger
- Source-coverage audit: sites returning zero listings for 30 days get flagged
- Ground-truth test (`tests/ground_truth.yaml`) seeded with Newton
- Classifier precision/recall corpus (`tests/classifier_corpus.yaml`)
- GitHub Actions runs tests only — never the scrape

**Out of v1:**
- FastAPI server, frontend, `/api/*` endpoints
- `pinned_listings` table and pin endpoint
- `user_profiles`, `users`, `user_listing_status` tables
- `backend/relevance.py` — no profile-based scoring
- Hosted deployment
- RSS output (trivial to add later if wanted)

## Not Doing (and Why)

- **Web UI.** The anxiety pain is solved by the daily receipt. UI adds build cost without adding receipts. Revisit only if you genuinely miss it after 4 weeks of real use.
- **Pin table and endpoint.** Gmail's star *is* a pin. Don't rebuild Gmail.
- **Relevance scoring.** Subfield grouping in the digest is structure enough. If it's in your interest section, it's relevant.
- **Publishing scrape output to GitHub.** Decided last round — stays local.
- **Multi-user / auth.** Solved by open-source fork, not built-in.
- **Deadline reminders, calendar integration.** The deadline is printed next to each listing. A dedicated calendar is not this tool's job.

## Resolved (2026-04-20)

- **Cadence:** daily. Empty-digest days still send a receipt email (no-news is also information).
- **Email provider:** Fastmail SMTP (`smtp.fastmail.com:465`), app password in `.env`. stdlib `smtplib` — no third-party dep.
- **No-deadline listings:** included, with a "no deadline listed" label. Hiding risks silent FNs.
- **Subject line:** `[PhilTracker] 2026-04-21 — N new listings (K matching your interests)`.
- **LLM scope:** one structured call per new listing does classification + field extraction (incl. free-text `duration`) + subfield tagging + 1-sentence summary. Replaces the previous "thin yes/no classifier + regex extraction + keyword tagger" pipeline. Haiku 4.5 default, prompt caching on the system prompt.
- **Rejects:** silent. `is_posting=false` → `active=0` row, URL cached, no stored reason. False negatives surface via `ground_truth.yaml` and get diagnosed by re-classifying the URL with verbose logging.

---

*`docs/SPEC.md` has been rewritten to match this direction.*
