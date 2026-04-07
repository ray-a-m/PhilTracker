"""
PhilTracker API server and frontend host.
Run: python backend/app.py
Opens at: http://localhost:8000
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

from backend.models import get_db, init_db
from backend.relevance import score_listings
from tagger.keywords import load_tags

app = FastAPI(title="PhilTracker", version="0.1")

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")


class ProfileCreate(BaseModel):
    name: str = ""
    email: str = ""
    interests: list[str] = []
    preferred_types: list[str] = []
    preferred_locations: list[str] = []
    digest_frequency: str = "weekly"


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

    if q:
        q_lower = q.lower()
        results = [
            r for r in results
            if q_lower in r["title"].lower()
            or q_lower in r["institution"].lower()
            or q_lower in (r["description"] or "").lower()
        ]

    if listing_type:
        results = [r for r in results if r["listing_type"] == listing_type]

    if tag:
        results = [
            r for r in results
            if tag in json.loads(r.get("aos", "[]"))
        ]

    if location:
        loc_lower = location.lower()
        results = [
            r for r in results
            if loc_lower in (r.get("location", "") or "").lower()
        ]

    valid_sorts = {"deadline", "institution", "date_first_seen", "title", "date_scraped"}
    sort_key = sort if sort in valid_sorts else "deadline"
    reverse = order.lower() == "desc"

    results.sort(key=lambda item: item.get(sort_key) or "", reverse=reverse)

    return results


@app.get("/api/listings/relevant/{profile_id}")
def get_relevant_listings(
    profile_id: int,
    q: str = Query("", description="Text search"),
    listing_type: str = Query("", description="Filter by type"),
    location: str = Query("", description="Filter by location"),
):
    # Load profile
    conn = get_db()
    profile = conn.execute(
        "SELECT * FROM user_profiles WHERE id = ?", (profile_id,)
    ).fetchone()
    if not profile:
        conn.close()
        return JSONResponse({"error": "Profile not found"}, status_code=404)

    profile = dict(profile)
    interests = set(json.loads(profile["interests"]))
    pref_types = set(json.loads(profile["preferred_types"]))
    pref_locations = json.loads(profile["preferred_locations"])

    rows = conn.execute("SELECT * FROM listings WHERE active = 1").fetchall()
    conn.close()
    results = [dict(row) for row in rows]

    # Apply text search
    if q:
        q_lower = q.lower()
        results = [
            r for r in results
            if q_lower in r["title"].lower()
            or q_lower in r["institution"].lower()
            or q_lower in (r["description"] or "").lower()
        ]

    # Filter by preferred types (if set)
    if listing_type:
        results = [r for r in results if r["listing_type"] == listing_type]
    elif pref_types:
        results = [r for r in results if r["listing_type"] in pref_types]

    # Filter by preferred locations (if set)
    if location:
        loc_lower = location.lower()
        results = [r for r in results if loc_lower in (r.get("location", "") or "").lower()]
    elif pref_locations:
        results = [
            r for r in results
            if any(
                pl.lower() in (r.get("location", "") or "").lower()
                for pl in pref_locations
            )
            or not r.get("location")  # keep listings with no location info
        ]

    # Score and sort by relevance
    results = score_listings(interests, results)

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


@app.post("/api/profile")
def create_or_update_profile(profile: ProfileCreate):
    conn = get_db()
    # Check if profile with this email exists
    if profile.email:
        existing = conn.execute(
            "SELECT id FROM user_profiles WHERE email = ?", (profile.email,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE user_profiles SET name=?, interests=?, preferred_types=?,
                   preferred_locations=?, digest_frequency=? WHERE id=?""",
                (
                    profile.name,
                    json.dumps(profile.interests),
                    json.dumps(profile.preferred_types),
                    json.dumps(profile.preferred_locations),
                    profile.digest_frequency,
                    existing["id"],
                ),
            )
            conn.commit()
            profile_id = existing["id"]
            conn.close()
            return {"id": profile_id, "status": "updated"}

    cursor = conn.execute(
        """INSERT INTO user_profiles (name, email, interests, preferred_types,
           preferred_locations, digest_frequency, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            profile.name,
            profile.email,
            json.dumps(profile.interests),
            json.dumps(profile.preferred_types),
            json.dumps(profile.preferred_locations),
            profile.digest_frequency,
            date.today().isoformat(),
        ),
    )
    conn.commit()
    profile_id = cursor.lastrowid
    conn.close()
    return {"id": profile_id, "status": "created"}


@app.get("/api/profile/{profile_id}")
def get_profile(profile_id: int):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM user_profiles WHERE id = ?", (profile_id,)
    ).fetchone()
    conn.close()
    if not row:
        return JSONResponse({"error": "Profile not found"}, status_code=404)
    result = dict(row)
    result["interests"] = json.loads(result["interests"])
    result["preferred_types"] = json.loads(result["preferred_types"])
    result["preferred_locations"] = json.loads(result["preferred_locations"])
    return result


if __name__ == "__main__":
    print("Starting PhilTracker at http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
