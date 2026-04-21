"""Live-only tests that assert canonical listings are not silently dropped.

Skipped by default. Run with `pytest --live` (requires network access).

Current ground-truth check strategy: run the full end-to-end pipeline in
dry-run mode, then verify each ground-truth URL landed in the DB as
`active=1`. This catches both scraper-level FNs (URL missing entirely)
and LLM-level FNs (URL scraped but wrongly classified as non-posting).
"""

import os
from pathlib import Path

import pytest
import yaml


GROUND_TRUTH_PATH = Path(__file__).parent / "ground_truth.yaml"


def _load_entries() -> list[dict]:
    with open(GROUND_TRUTH_PATH) as f:
        data = yaml.safe_load(f) or {}
    entries = data.get("entries") or []
    # Skip commented-out placeholders — only yaml-parsed entries count
    return entries


@pytest.fixture
def ground_truth_entries() -> list[dict]:
    entries = _load_entries()
    if len(entries) < 10:
        pytest.skip(
            f"ground_truth.yaml has {len(entries)} entries (target: ≥10). "
            "Seed more before treating this as the real regression harness."
        )
    return entries


@pytest.mark.live
def test_each_ground_truth_url_lands_active(ground_truth_entries, tmp_path, monkeypatch):
    """Run the pipeline; assert every seeded URL ends up with active=1 in the DB."""
    from backend import models
    from scheduler import run_all as sched

    db_path = str(tmp_path / "live_gt.db")
    monkeypatch.setattr(models, "DB_PATH", db_path)
    monkeypatch.setenv("PHILTRACKER_DB", db_path)

    # Real pipeline, real scrapers, real LLM — just don't send email
    sched.pipeline(selected=None, dry_run=True)

    conn = models.get_db()
    try:
        rows = conn.execute("SELECT url, active FROM listings").fetchall()
    finally:
        conn.close()

    url_to_active = {row["url"]: row["active"] for row in rows}

    missing = []
    misclassified = []
    for entry in ground_truth_entries:
        url = entry["url"]
        if url not in url_to_active:
            missing.append(url)
        elif entry["expected_is_posting"] and url_to_active[url] != 1:
            misclassified.append(url)

    assert not missing, f"Scraper(s) dropped ground-truth URLs: {missing}"
    assert not misclassified, f"LLM rejected ground-truth postings: {misclassified}"
