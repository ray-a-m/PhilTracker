"""
PhilTracker API server and frontend host.
Run: python backend/app.py
Opens at: http://localhost:8000
"""

import json
import os
import sys

# Add project root to path so imports work when run as script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from backend.models import get_db, init_db
from tagger.keywords import load_tags

app = FastAPI(title="PhilTracker", version="0.1")

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")


@app.on_event("startup")
def startup():
    init_db()


@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/api/listings")
def get_listings(
    q: str = Query("", description="Text search"),
    listing_type: str = Query("", description="Filter by type"),
    tag: str = Query("", description="Filter by AOS tag"),
    location: str = Query("", description="Filter by location"),
    sort: str = Query("deadline", description="Sort field"),
    order: str = Query("asc", description="Sort order"),
    active_only: bool = Query(True, description="Only active listings"),
):
    conn = get_db()
    if active_only:
        rows = conn.execute("SELECT * FROM listings WHERE active = 1").fetchall()
    else:
        rows = conn.execute("SELECT * FROM listings").fetchall()
    conn.close()

    results = [dict(row) for row in rows]

    # Text search
    if q:
        q_lower = q.lower()
        results = [
            r for r in results
            if q_lower in r["title"].lower()
            or q_lower in r["institution"].lower()
            or q_lower in (r["description"] or "").lower()
        ]

    # Filter by listing type
    if listing_type:
        results = [r for r in results if r["listing_type"] == listing_type]

    # Filter by tag
    if tag:
        results = [
            r for r in results
            if tag in json.loads(r.get("aos", "[]"))
        ]

    # Filter by location
    if location:
        loc_lower = location.lower()
        results = [
            r for r in results
            if loc_lower in (r.get("location", "") or "").lower()
        ]

    # Sort
    valid_sorts = {"deadline", "institution", "date_first_seen", "title", "date_scraped"}
    sort_key = sort if sort in valid_sorts else "deadline"
    reverse = order.lower() == "desc"

    def sort_fn(item):
        val = item.get(sort_key) or ""
        return val

    results.sort(key=sort_fn, reverse=reverse)

    return results


@app.get("/api/tags")
def get_tags():
    tags = load_tags()
    return sorted(tags.keys())


@app.get("/api/stats")
def get_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    active = conn.execute("SELECT COUNT(*) FROM listings WHERE active = 1").fetchone()[0]
    sources = conn.execute("SELECT DISTINCT source FROM listings").fetchall()
    conn.close()
    return {
        "total_listings": total,
        "active_listings": active,
        "sources": [row[0] for row in sources],
    }


if __name__ == "__main__":
    print("Starting PhilTracker at http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
