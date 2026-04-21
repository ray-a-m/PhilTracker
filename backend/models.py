"""
SQLite schema + CRUD for PhilTracker.

Single listings table — no users, no profiles, no pins. Triage happens in Fastmail.
"""

import json
import os
import sqlite3
from datetime import date

DB_PATH = os.environ.get("PHILTRACKER_DB", "philtracker.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the listings table + indexes if they don't exist."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS listings (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            url             TEXT UNIQUE NOT NULL,
            source          TEXT NOT NULL,
            title           TEXT DEFAULT '',
            institution     TEXT DEFAULT '',
            deadline        TEXT,
            location        TEXT DEFAULT '',
            duration        TEXT DEFAULT '',
            description     TEXT DEFAULT '',
            summary         TEXT DEFAULT '',
            aos             TEXT DEFAULT '[]',
            listing_type    TEXT DEFAULT 'unknown',
            confidence      REAL DEFAULT 0.0,
            active          INTEGER DEFAULT 1,
            date_scraped    TEXT NOT NULL,
            date_first_seen TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_listings_source     ON listings(source);
        CREATE INDEX IF NOT EXISTS idx_listings_deadline   ON listings(deadline);
        CREATE INDEX IF NOT EXISTS idx_listings_active     ON listings(active);
        CREATE INDEX IF NOT EXISTS idx_listings_first_seen ON listings(date_first_seen);
    """)
    conn.commit()
    conn.close()


def insert_listing(listing) -> bool:
    """
    Insert a listing. Returns True if inserted, False if the URL already exists.

    `listing.active` controls digest visibility; LLM-classified rejects set it to 0
    so the row exists (URL is cached) but the listing never appears in a digest.
    """
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO listings
               (url, source, title, institution, deadline, location,
                duration, description, summary, aos, listing_type,
                confidence, active, date_scraped, date_first_seen)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                listing.url,
                listing.source,
                listing.title,
                listing.institution,
                listing.deadline,
                listing.location,
                listing.duration,
                listing.description,
                listing.summary,
                json.dumps(listing.aos),
                listing.listing_type,
                listing.confidence,
                1 if listing.active else 0,
                listing.date_scraped,
                date.today().isoformat(),
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_known_urls() -> set[str]:
    """All URLs already in the DB, regardless of active state. Used by the scheduler
    to skip re-classifying listings we've already seen."""
    conn = get_db()
    rows = conn.execute("SELECT url FROM listings").fetchall()
    conn.close()
    return {row["url"] for row in rows}


def get_new_active_listings(today: str) -> list[dict]:
    """Listings first seen today that are currently active — the digest contents."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM listings WHERE date_first_seen = ? AND active = 1 "
        "ORDER BY deadline IS NULL, deadline ASC",
        (today,),
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def count_rejected_today(today: str) -> int:
    """For the digest footer — count of listings first seen today with active=0."""
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM listings WHERE date_first_seen = ? AND active = 0",
        (today,),
    ).fetchone()
    conn.close()
    return row["n"]


def deactivate_expired():
    """Mark listings whose deadline has passed as inactive."""
    conn = get_db()
    today = date.today().isoformat()
    conn.execute(
        "UPDATE listings SET active = 0 "
        "WHERE active = 1 AND deadline IS NOT NULL AND deadline < ?",
        (today,),
    )
    conn.commit()
    conn.close()


def _row_to_dict(row) -> dict:
    d = dict(row)
    d["aos"] = json.loads(d["aos"]) if d.get("aos") else []
    return d
