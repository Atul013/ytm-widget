"""Rolling observation log for weekly play counts.

There is no play-count API in YouTube Music. `get_history()` returns a flat
recency list with no counts and no timestamps, so counts have to be built from
our own repeated observations.

The workflow polls every 30 minutes and records the tracks it sees. A track is
counted once per *observation session* - if it is still the top entry on the
next poll, that is the same play, not a new one. Because polling is coarser
than listening, this undercounts: several tracks played inside one interval
collapse into whichever was most recent at poll time. Short tracks are missed
more often than long ones.

The numbers are therefore directionally right, not exact, and the card says so.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

WINDOW_DAYS = 7
# Cap retained observations so the file cannot grow without bound.
MAX_ENTRIES = 4000


def _parse(ts: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def load(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data.get("observations", []) if isinstance(data, dict) else []


def prune(observations: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    """Drop observations outside the window, and cap total size."""
    cutoff = now - timedelta(days=WINDOW_DAYS)
    kept = [
        o for o in observations
        if (seen := _parse(o.get("seen", ""))) is not None and seen >= cutoff
    ]
    return kept[-MAX_ENTRIES:]


def record(
    observations: list[dict[str, Any]],
    track: dict[str, Any],
    now: datetime,
) -> tuple[list[dict[str, Any]], bool]:
    """Append a track observation unless it repeats the most recent one.

    Returns (observations, was_new). A track still sitting at the top of history
    on the next poll is the same play we already counted.
    """
    video_id = track.get("videoId")
    if not video_id:
        return observations, False

    if observations and observations[-1].get("videoId") == video_id:
        return observations, False

    artists = track.get("artists") or []
    album = track.get("album")
    observations.append(
        {
            "videoId": video_id,
            "title": track.get("title", "Unknown"),
            "artist": ", ".join(
                a.get("name", "") for a in artists if isinstance(a, dict) and a.get("name")
            ) or "Unknown artist",
            "album": album.get("name") if isinstance(album, dict) else None,
            "thumbnail": _best_thumb(track.get("thumbnails")),
            "seen": now.isoformat(),
        }
    )
    return observations, True


def _best_thumb(thumbnails: list | None) -> str | None:
    if not thumbnails:
        return None
    usable = [t for t in thumbnails if isinstance(t, dict) and t.get("url")]
    if not usable:
        return None
    usable.sort(key=lambda t: t.get("width", 0))
    for thumb in usable:
        if thumb.get("width", 0) >= 120:
            return thumb["url"]
    return usable[-1]["url"]


def top_tracks(observations: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    """Rank tracks by observation count, most played first.

    Ties break by most recent play, so an equal-count track heard today ranks
    above one last heard six days ago.
    """
    tallies: dict[str, dict[str, Any]] = {}
    for obs in observations:
        video_id = obs.get("videoId")
        if not video_id:
            continue
        entry = tallies.setdefault(
            video_id,
            {
                "videoId": video_id,
                "title": obs.get("title", "Unknown"),
                "artist": obs.get("artist", "Unknown artist"),
                "album": obs.get("album"),
                "thumbnail": obs.get("thumbnail"),
                "count": 0,
                "last_seen": obs.get("seen", ""),
            },
        )
        entry["count"] += 1
        if obs.get("seen", "") > entry["last_seen"]:
            entry["last_seen"] = obs["seen"]
            # Prefer the most recent metadata; art URLs expire.
            if obs.get("thumbnail"):
                entry["thumbnail"] = obs["thumbnail"]

    ranked = sorted(tallies.values(), key=lambda e: (e["count"], e["last_seen"]), reverse=True)
    return ranked[:limit]


def save(path: Path, observations: list[dict[str, Any]], now: datetime) -> None:
    path.write_text(
        json.dumps(
            {
                "updated": now.isoformat(),
                "window_days": WINDOW_DAYS,
                "note": (
                    "Counts are derived from 30-minute polling, not from a play-count "
                    "API. Tracks played between polls are not observed, so these "
                    "undercount actual plays."
                ),
                "observations": observations,
            },
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
