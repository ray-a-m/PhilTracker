"""
Database models for PhilTracker.
Uses SQLite via sqlite3 for simplicity. Migrate to Postgres when needed.
"""

import sqlite3
import os
import json
from datetime import date

DB_PATH = os.environ.get("PHILTRACKER_DB", "philtracker.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            institution TEXT NOT NULL,
            url TEXT UNIQUE NOT NULL,
            source TEXT NOT NULL,
            deadline TEXT,
            description TEXT DEFAULT '',
            date_scraped TEXT NOT NULL,
            date_first_seen TEXT NOT NULL,
            aos TEXT DEFAULT '[]',
            listing_type TEXT DEFAULT 'unknown',
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT DEFAULT '',
            interests TEXT DEFAULT '[]',
            digest_frequency TEXT DEFAULT 'weekly',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS user_listing_status (
            user_id INTEGER,
            listing_id INTEGER,
            status TEXT DEFAULT 'new',
            updated_at TEXT NOT NULL,
            PRIMARY KEY (user_id, listing_id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (listing_id) REFERENCES listings(id)
        );

        CREATE INDEX IF NOT EXISTS idx_listings_source ON listings(source);
        CREATE INDEX IF NOT EXISTS idx_listings_deadline ON listings(deadline);
        CREATE INDEX IF NOT EXISTS idx_listings_active ON listings(active);
    """)
    conn.commit()
    conn.close()


def insert_listing(listing) -> bool:
    """
    Insert a listing if it doesn't already exist (by URL).
    Returns True if inserted, False if duplicate.
    """
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO listings
               (title, institution, url, source, deadline, description,
                date_scraped, date_first_seen, aos, listing_type)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                listing.title,
                listing.institution,
                listing.url,
                listing.source,
                listing.deadline,
                listing.description,
                listing.date_scraped,
                date.today().isoformat(),
                json.dumps(listing.aos),
                listing.listing_type,
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # duplicate URL
    finally:
        conn.close()


def get_active_listings(tags: list[str] = None) -> list[dict]:
    """Get active listings, optionally filtered by AOS tags."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM listings WHERE active = 1 ORDER BY deadline ASC"
    ).fetchall()
    conn.close()

    results = [dict(row) for row in rows]

    if tags:
        filtered = []
        for r in results:
            listing_tags = json.loads(r["aos"])
            if any(t in listing_tags for t in tags):
                filtered.append(r)
        return filtered

    return results


def deactivate_expired():
    """Mark listings with passed deadlines as inactive."""
    conn = get_db()
    today = date.today().isoformat()
    conn.execute(
        "UPDATE listings SET active = 0 WHERE deadline < ? AND deadline IS NOT NULL",
        (today,),
    )
    conn.commit()
    conn.close()
